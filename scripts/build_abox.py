"""Convert the AMLTRIX beta.4 CSV export into RDF instance data (ABox) that
follows the AMLO schema in ontology/amlo.ttl.

Run:  .venv/bin/python scripts/build_abox.py
Out:  data/amltrix.ttl
"""
import csv
import glob
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "vendor" / "amltrix"
OUT = ROOT / "data" / "amltrix.ttl"
VERSION = "1.0-beta.4"

AMLO = Namespace("https://example.org/amlo#")
AMX = Namespace("https://example.org/amltrix/")

csv.field_size_limit(10**9)


def load(name):
    path = glob.glob(str(SRC / f"*{VERSION}-{name}.csv"))[0]
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# table -> (class, name column, id column)
CATALOGUES = {
    "tactics": (AMLO.Tactic, "Tactic Name", "external_id"),
    "techniques": (AMLO.Technique, "Technique Name", "External ID"),
    "indicators": (AMLO.Indicator, "Indicator Name", "Indicator Name"),
    "mitigations": (AMLO.Mitigation, "Mitigation Name", "External ID"),
    "actors": (AMLO.Actor, "Actor Name", "External ID"),
    "value-instruments": (AMLO.ValueInstrument, "Instrument Name", "External ID"),
    "products-service": (AMLO.ProductService, "Product/Service Name", "External ID"),
    "datasources": (AMLO.DataSource, "Data Source Name", "External ID"),
    "risks": (AMLO.RiskType, "Risk Name", "External ID"),
}

# relationship type -> (direct property, link class, link's own property)
# link class None = no Link node (text is redundant or empty)
RELATIONS = {
    "is-achieved-by": (AMLO.isAchievedBy, AMLO.TacticLink, AMLO.tactic),
    "mitigates": (AMLO.mitigates, AMLO.MitigationLink, AMLO.mitigation),
    "engages-in": (AMLO.engagesIn, AMLO.ActorLink, AMLO.actor),
    "is-used-by": (AMLO.isUsedBy, AMLO.InstrumentLink, AMLO.instrument),
    "is-exploited-by": (AMLO.isExploitedBy, AMLO.ProductServiceLink, AMLO.productService),
    "is-associated-with": (AMLO.isAssociatedWith, AMLO.RiskLink, AMLO.riskType),
    "is-identified-in": (AMLO.isIdentifiedIn, AMLO.DataSourceLink, AMLO.dataSource),
    "is-indicated-by": (AMLO.isIndicatedBy, None, None),
}
# relationships whose Source is the technique (others have it as Target)
TECHNIQUE_IS_SOURCE = {"is-identified-in", "is-indicated-by"}


def dt(value):
    return Literal(value, datatype=XSD.dateTime) if value else None


def main():
    g = Graph()
    for p, ns in [("amlo", AMLO), ("amx", AMX), ("skos", SKOS), ("dct", DCTERMS), ("owl", OWL)]:
        g.bind(p, ns)

    scheme = AMX["scheme/amltrix-ml"]
    g.add((scheme, RDF.type, SKOS.ConceptScheme))
    g.add((scheme, SKOS.prefLabel, Literal(f"AMLTRIX Money Laundering matrix ({VERSION})", lang="en")))
    g.add((scheme, DCTERMS.source, URIRef("https://framework.amltrix.com")))
    g.add((scheme, DCTERMS.license, URIRef("https://framework.amltrix.com/license")))
    g.add((scheme, DCTERMS.rights, Literal(
        "Derived from AMLTRIX by UAB Amlyze (https://framework.amltrix.com), used under the AMLTRIX "
        "License Terms. Not endorsed by AMLTRIX. Derivative works must keep this attribution and be "
        "distributed under the same terms.", lang="en")))

    stix_to_uri = {}
    technique_rows = {}
    for table, (cls, name_col, id_col) in CATALOGUES.items():
        rows = load(table)
        # The source export is not guaranteed to have unique IDs (beta.4 gives
        # T0098 to two different techniques). Colliding IDs get the first 8
        # characters of the STIX UUID appended so they stay distinct nodes.
        id_counts = {}
        for row in rows:
            id_counts[row[id_col]] = id_counts.get(row[id_col], 0) + 1
        for row in rows:
            ext_id = row[id_col]
            collides = id_counts[ext_id] > 1
            uri = AMX[f"{ext_id}-{row['STIX ID'].split('--', 1)[1][:8]}"] if collides else AMX[ext_id]
            if collides:
                print(f"ID collision in {table}: {ext_id} ({row[name_col]}) -> {uri}")
                g.add((uri, SKOS.editorialNote, Literal(
                    f"The source export assigns the ID {ext_id} to more than one entry; "
                    "this node is disambiguated by its STIX UUID.", lang="en")))
            stix_to_uri[row["STIX ID"]] = uri
            is_sub = table == "techniques" and row["Is Subtechnique"] == "True"
            g.add((uri, RDF.type, AMLO.SubTechnique if is_sub else cls))
            g.add((uri, SKOS.inScheme, scheme))
            g.add((uri, SKOS.notation, Literal(ext_id)))
            g.add((uri, SKOS.prefLabel, Literal(row[name_col], lang="en")))
            g.add((uri, AMLO.stixId, Literal(row["STIX ID"])))
            if row["Description"].strip():
                g.add((uri, SKOS.definition, Literal(row["Description"].strip(), lang="en")))
            short = row.get("Short Description") or row.get("x_amltrix_short_description") or ""
            if short.strip():
                g.add((uri, AMLO.shortDescription, Literal(short.strip(), lang="en")))
            url = row.get("URL") or row.get("external_url") or ""
            if url:
                g.add((uri, RDFS.seeAlso, URIRef(url)))
            for key, prop in (("Created", DCTERMS.created), ("Modified", DCTERMS.modified)):
                if dt(row[key]):
                    g.add((uri, prop, dt(row[key])))
            for alias in (row.get("Aliases") or "").split(";"):
                if alias.strip():
                    g.add((uri, SKOS.altLabel, Literal(alias.strip(), lang="en")))
            if table == "techniques":
                technique_rows[row["STIX ID"]] = row

    # Sub-technique hierarchy: taken from the Parent Technique column, then
    # cross-checked against the subtechnique-of relationship rows.
    for stix, row in technique_rows.items():
        if row["Is Subtechnique"] == "True":
            g.add((stix_to_uri[stix], SKOS.broader, stix_to_uri[row["Parent Technique"]]))

    counts = {}
    for rel in load("relationships"):
        rtype = rel["Relationship Type"]
        src, tgt = stix_to_uri[rel["Source"]], stix_to_uri[rel["Target"]]
        counts[rtype] = counts.get(rtype, 0) + 1
        if rtype == "subtechnique-of":
            assert (src, SKOS.broader, tgt) in g, f"hierarchy mismatch for {src}"
            continue
        direct, link_cls, link_prop = RELATIONS[rtype]
        tech, other = (src, tgt) if rtype in TECHNIQUE_IS_SOURCE else (tgt, src)
        g.add((src, direct, tgt))
        if link_cls is not None:
            link = AMX["link/" + rel["Relationship ID"].split("--", 1)[1]]
            g.add((link, RDF.type, link_cls))
            g.add((link, AMLO.technique, tech))
            g.add((link, link_prop, other))
            if rel["Description"].strip():
                g.add((link, DCTERMS.description, Literal(rel["Description"].strip(), lang="en")))

    OUT.parent.mkdir(exist_ok=True)
    g.serialize(OUT, format="turtle")
    print(f"{len(g):,} triples -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1e6:.1f} MB)")
    print("relationship rows by type:", counts)


if __name__ == "__main__":
    main()

"""Paths, pinned versions and runtime settings for the demo.

Anything specific to one machine comes from environment variables, never from the repository.
"""
import os
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DEMO_DIR.parent

# Pinned: the files in ontology/ and data/ were built from this AMLTRIX release.
AMLTRIX_VERSION = "1.0-beta.4"
AMLO_TTL = REPO_DIR / "ontology" / "amlo.ttl"
AMLTRIX_TTL = REPO_DIR / "data" / "amltrix.ttl"

# The Investigation Ontology (Demo): an extension that lives inside demo/, never in ontology/.
INVESTIGATION_TTL = DEMO_DIR / "vocab" / "investigation.ttl"
INVESTIGATION_SHAPES = DEMO_DIR / "shapes" / "investigation-shapes.ttl"
MAPPING_DIR = DEMO_DIR / "mapping"
SAMPLES_DIR = DEMO_DIR / "samples"
GENERATED_DIR = DEMO_DIR / "generated"

# Read-only transaction database. It lives outside this repository (set AML_DB to its path);
# when unset or missing, the demo falls back to the small bundled sample.
AML_DB = Path(os.environ["AML_DB"]) if os.environ.get("AML_DB") else None
SAMPLE_DB = DEMO_DIR / "samples" / "mini.duckdb"

# LLM settings. "mock" runs the demo with recorded responses and needs no key.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

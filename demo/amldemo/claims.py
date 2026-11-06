"""Checks, made by code, that a sentence a model wrote does not claim more than the text it rests on says.

The data of the demo is thin on purpose, and models read more into it than it holds. Three habits are caught here, each by what the sentence says
and what the text it rests on (the evidence, the alert's facts, the findings it cites) does not:

  1. unstated place: a sentence that says the evidence "shows" or "indicates" something cross-border, international, foreign, offshore or about
     jurisdictions or countries, when the text it rests on never mentions it. The data has no country field: a currency is not a country and a payment
     between two banks is not a cross-border payment.
  2. added-up amounts: a sentence that totals, sums or combines amounts, when the text it rests on does not. The amounts of three payments in a cycle are
     the flow of three payments, not one sum that left and came back.
  3. proxy taken for the thing: evidence that is only a proxy (a currency used in place of the missing country) cited for an indicator about places.
  4. admitted absence: a reason that fully supports an indicator ("yes") while saying itself that the evidence does not show it ("...are not shown"). A partial
     support may say what is missing, so scenario 4 applies this one to "yes" only.

Words are matched as written; whether the wording is otherwise faithful is NOT checked. Each function returns a list of problems, empty if the sentence is fine.
"""
import re

PLACE_STEMS = ("cross-border", "cross border", "international", "foreign", "overseas", "offshore", "jurisdiction", "countr")
PLACE_PLURALS = re.compile(r"\b(?:multiple|several|different|various|many)\s+(?:jurisdictions|countries)\b", re.I)
PLACE_STEM = re.compile("|".join(re.escape(s) for s in PLACE_STEMS), re.I)
ASSERTS = re.compile(r"\b(?:indicat\w*|show\w*|reveal\w*|confirm\w*|demonstrat\w*|evidenc\w*|establish\w*|prove\w*)\b", re.I)
ADDED_UP = re.compile(r"\b(?:total(?:s|ed|ing|ling|led)?|sum(?:s|med|ming)?|combined|aggregate[sd]?|altogether|cumulative)\b", re.I)
ADMITS_ABSENCE = re.compile(
    r"\b(?:not\s+(?:shown|provided|available|present|visible|stated|known|evident|confirmed)|no\s+(?:evidence|indication|information|data)|"
    r"(?:cannot|can't|could\s+not|can\s+not)\s+(?:by\s+itself\s+)?(?:be\s+)?(?:assessed|determined|verified|confirmed|seen|establish\w*|show|prove|confirm|demonstrate)|"
    r"unverified|unconfirmed|(?:are|is)\s+not\s+clearly|"
    r"(?:lacks?|lacking|without)\s+(?:any\s+)?(?:evidence|data|information)|"
    r"(?:does|do)\s+not\s+(?:clearly\s+)?(?:show|state|say|indicate|provide|contain|include|demonstrate|establish)|is\s+not\s+(?:shown|stated|known|given))\b", re.I)


MODAL = re.compile(r"\b(?:would|could|may|might|should|can|will|to|whether|if)\s+(?:\w+\s+)?$", re.I)


def _asserts(sentence):
    """True if the sentence states something as shown ("the evidence shows ..."), not as something a record would show ("records would show ...")."""
    return any(not MODAL.search(sentence[:m.start()]) for m in ASSERTS.finditer(sentence))


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


def unstated_place(text, basis):
    """Sentences of `text` that assert something about places (see 1) which `basis`, the text it rests on, never mentions."""
    problems, source = [], basis.lower()
    for sentence in _sentences(text):
        if not _asserts(sentence):
            continue
        for m in PLACE_STEM.finditer(sentence):
            if m.group(0).lower() not in source:
                problems.append(f"says the evidence shows something about '{m.group(0).lower()}', which the evidence it rests on does not mention "
                                "(the data has no country field: a currency is not a country, and a payment between two banks is not cross-border)")
                break
        else:
            m = PLACE_PLURALS.search(sentence)
            if m and m.group(0).lower() not in source:
                problems.append(f"says '{m.group(0).lower()}', which the evidence it rests on does not say")
    return problems


def added_up(text, basis):
    """Sentences of `text` that total or combine amounts when `basis` does not."""
    return [f"adds the amounts up ('{m.group(0).lower()}'): list each amount on its own, a cycle of payments is the flow of each payment, not one sum"
            for m in (ADDED_UP.search(s) for s in _sentences(text)) if m and m.group(0).lower() not in basis.lower()][:1]


def proxy_for_place(indicator_text, cited_texts):
    """An indicator about places, supported by evidence that is only a proxy: the data says so itself ("used as a jurisdiction proxy"). A proxy is not
    the thing it stands for, so a currency cannot show that a payment went to, or came from, a country, a jurisdiction or abroad."""
    if PLACE_STEM.search(indicator_text or "") and any("proxy" in c.lower() for c in cited_texts):
        return ["the indicator is about places (countries, jurisdictions, cross-border), and the evidence it cites is only a proxy for them (a currency): "
                "a proxy does not show it, so leave the indicator out"]
    return []


def admitted_absence(reason):
    """A reason for support that says the evidence does not show it."""
    m = ADMITS_ABSENCE.search(reason)
    return [f"the reason says '{m.group(0).lower()}': evidence that does not show an indicator does not support it, so leave the indicator out "
            "and say in not_shown that the data cannot show it"] if m else []

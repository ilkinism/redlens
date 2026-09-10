"""The three stories from the design brief, walked end to end through the API.

These are written as the user's job, not as unit assertions: find what moved,
decide about each, reply.
"""

from __future__ import annotations

import base64

import pytest

from redlens.api import RedlensAPI
from redlens.config import Config
from support import RETURNED, SENT, UNRELATED, docx


@pytest.fixture
def api():
    return RedlensAPI(Config())


def bundle(before, after):
    return {"before": base64.b64encode(docx(before)).decode("ascii"),
            "before_name": "round-two.docx",
            "after": base64.b64encode(docx(after)).decode("ascii"),
            "after_name": "round-three.docx"}


def test_story_one_reads_four_paragraphs_instead_of_forty(api):
    """First use: a returned contract with no tracked changes."""
    compared = api.compare(bundle(SENT, RETURNED))
    assert compared.status == 200
    summary = compared.body["summary"]

    # The reader is asked to look at far less than the document.
    assert summary["changes"] < summary["paragraphs_before"]
    # Formatting noise is accounted for rather than silently dropped.
    assert summary["set_aside"] > 0
    # The aha moment is present and states both figures.
    liability = next(c for c in compared.body["changes"] if c["clause"] == "9.2")
    assert liability["kind"] == "money"
    assert "£1,000,000" in liability["headline"]
    assert "£250,000" in liability["headline"]

    # Money and durations come before wording.
    kinds = [c["kind"] for c in compared.body["changes"] if c["nature"] == "edited"]
    assert kinds.index("money") < kinds.index("wording")

    # They query two of them and send the note.
    queried = [liability["index"],
               next(c["index"] for c in compared.body["changes"] if c["clause"] == "2")]
    note = api.note(dict(bundle(SENT, RETURNED), queried=queried))
    assert note.status == 200
    assert note.body["note"].count("Clause") >= 2
    assert "round-three.docx" in note.body["note"]


def test_story_two_round_four_has_one_thing_in_it(api):
    """Repeat use: one figure moved, seen in a second."""
    later = list(RETURNED)
    changed = [p.replace("£90,000", "£95,000") if "£90,000" in p else p for p in later]
    if changed == later:                      # keep the fixture honest
        changed = [p.replace("36 months", "48 months") for p in later]
    compared = api.compare(bundle(RETURNED, changed))
    assert compared.body["summary"]["changes"] == 1
    only = compared.body["changes"][0]
    assert only["nature"] == "edited"
    note = api.note(dict(bundle(RETURNED, changed), queried=[only["index"]]))
    assert "1 change:" in note.body["note"]


def test_story_three_unrelated_files_are_a_question_not_a_hundred_findings(api):
    compared = api.compare(bundle(SENT, UNRELATED))
    assert compared.body["unrelated"] is True
    # The information needed to ask the question honestly is present.
    assert compared.body["summary"]["matched"] < compared.body["summary"]["paragraphs_before"]


def test_a_settled_document_says_nothing_moved(api):
    cosmetic = [p.replace("'", "’") for p in SENT]
    compared = api.compare(bundle(SENT, cosmetic))
    assert compared.body["summary"]["changes"] == 0
    assert compared.body["summary"]["set_aside"] > 0
    assert compared.body["unrelated"] is False


def test_the_wrong_format_names_the_format_and_what_is_supported(api):
    body = bundle(SENT, RETURNED)
    body["after"] = base64.b64encode(b"%PDF-1.7 ...").decode("ascii")
    body["after_name"] = "round-three.pdf"
    reply = api.compare(body)
    assert reply.status == 422
    assert "PDF" in reply.body["error"]
    assert ".docx" in reply.body["error"]

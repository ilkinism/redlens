"""The API, exercised the way the browser exercises it."""

from __future__ import annotations

import base64

import pytest

from redlens.api import RedlensAPI
from redlens.config import Config
from support import RETURNED, SENT, UNRELATED, docx, plain


@pytest.fixture
def api():
    return RedlensAPI(Config())


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def both(before=SENT, after=RETURNED, writer=docx):
    return {"before": b64(writer(before)), "before_name": "sent.docx",
            "after": b64(writer(after)), "after_name": "returned.docx"}


def test_health(api):
    assert api.health().status == 200


def test_compare_returns_the_changes_and_the_summary(api):
    reply = api.compare(both())
    assert reply.status == 200
    assert reply.body["summary"]["changes"] == len(reply.body["changes"])
    assert reply.body["summary"]["set_aside"] == 2
    assert reply.body["before_name"] == "sent.docx"


def test_every_change_carries_its_marked_runs(api):
    reply = api.compare(both())
    for change in reply.body["changes"]:
        assert isinstance(change["marked_before"], list)
        assert isinstance(change["marked_after"], list)
        for run in change["marked_before"] + change["marked_after"]:
            assert run["mark"] in {"same", "removed", "added"}


def test_marked_runs_rejoin_into_the_paragraph(api):
    """The page renders runs with a space between them, so joining them back
    with a space must reproduce the paragraph -- otherwise the reader is shown
    text the document does not contain."""
    reply = api.compare(both())
    for change in reply.body["changes"]:
        for side, runs in (("before", change["marked_before"]),
                           ("after", change["marked_after"])):
            if not runs:
                continue
            rejoined = " ".join(run["text"] for run in runs)
            assert rejoined == " ".join(change[side].split())


def test_a_missing_document_is_refused_by_name(api):
    reply = api.compare({"after": b64(docx(RETURNED))})
    assert reply.status == 400
    assert "version you sent" in reply.body["error"]


def test_undecodable_base64_is_refused(api):
    body = both()
    body["after"] = "not base64 !!!"
    reply = api.compare(body)
    assert reply.status == 400


def test_a_pdf_is_refused_with_a_useful_message(api):
    body = both()
    body["after"] = b64(b"%PDF-1.7 whatever")
    body["after_name"] = "returned.pdf"
    reply = api.compare(body)
    assert reply.status == 422
    assert "PDF" in reply.body["error"]


def test_an_oversized_document_is_refused(api):
    small = RedlensAPI(Config(max_document_bytes=200))
    reply = small.compare(both())
    assert reply.status == 422
    assert "MB" in reply.body["error"]


def test_unrelated_documents_are_flagged_not_diffed_into_noise(api):
    reply = api.compare(both(after=UNRELATED))
    assert reply.status == 200
    assert reply.body["unrelated"] is True


def test_identical_documents_report_nothing_substantive(api):
    reply = api.compare(both(after=SENT))
    assert reply.body["summary"]["changes"] == 0
    assert reply.body["unrelated"] is False


def test_plain_text_works_as_well_as_docx(api):
    reply = api.compare(both(writer=plain))
    assert reply.status == 200
    assert reply.body["summary"]["changes"] > 0


def test_the_note_covers_only_what_was_queried(api):
    compared = api.compare(both())
    liability = next(c for c in compared.body["changes"] if c["clause"] == "9.2")
    body = both()
    body["queried"] = [liability["index"]]
    reply = api.note(body)
    assert reply.status == 200
    assert "Clause 9.2" in reply.body["note"]
    assert reply.body["queried"] == 1
    other = next(c for c in compared.body["changes"] if c["clause"] == "4")
    assert other["after"] not in reply.body["note"]


def test_a_note_with_nothing_queried_says_so(api):
    body = both()
    body["queried"] = []
    reply = api.note(body)
    assert reply.status == 409
    assert "Nothing has been queried" in reply.body["error"]


def test_a_note_needs_a_list_of_numbers(api):
    body = both()
    body["queried"] = ["clause nine"]
    reply = api.note(body)
    assert reply.status == 400


def test_a_note_without_a_queried_field_is_refused(api):
    reply = api.note(both())
    assert reply.status == 400


def test_the_change_cap_is_honoured(api):
    capped = RedlensAPI(Config(max_changes=2))
    reply = capped.compare(both())
    assert reply.body["summary"]["changes"] == 2


def test_the_paragraph_cap_is_honoured(api):
    capped = RedlensAPI(Config(max_paragraphs=3))
    reply = capped.compare(both())
    assert reply.status == 422
    assert "paragraphs" in reply.body["error"]

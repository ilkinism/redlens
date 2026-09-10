"""The claim Redlens rests on.

Comparison tools present a moved comma and a halved liability cap as equal
differences. If Redlens cannot separate the two, name the values that moved,
and account for what it set aside, there is nothing here worth building.
"""

import pytest

from redlens.compare import compare, is_cosmetic, normalise
from redlens.documents import read
from support import RETURNED, SENT, UNRELATED, docx, plain

pytestmark = pytest.mark.slice


def comparison(before=SENT, after=RETURNED, writer=docx):
    return compare(read(writer(before), "sent.docx"),
                   read(writer(after), "returned.docx"))


# ------------------------------------- it separates substance from typing

def test_formatting_changes_are_set_aside_not_reported_as_changes() -> None:
    """Smart quotes and a double space are not changes to a deal."""
    result = comparison()
    assert len(result.cosmetic) == 2, [c[0][:40] for c in result.cosmetic]
    reported = " ".join(c.after for c in result.changes)
    assert "Definitions" not in reported, "the quote-mark paragraph was reported"
    assert "invoiced quarterly" not in reported, "the double-space paragraph was reported"


def test_what_was_set_aside_is_counted_and_never_silently_dropped() -> None:
    result = comparison()
    assert result.cosmetic, "a silent drop is the failure mode to avoid"
    for before, after in result.cosmetic:
        assert before != after, "only genuinely differing paragraphs are set aside"
        assert is_cosmetic(before, after)


@pytest.mark.parametrize("before,after", [
    ("The 'Services' are provided.", "The “Services” are provided."),
    ("Payable within 30 days.", "Payable  within   30 days."),
    ("A dash - here", "A dash – here"),
    ("Ends 2026.", "ends 2026."),
])
def test_typing_differences_are_cosmetic(before, after) -> None:
    assert is_cosmetic(before, after)


@pytest.mark.parametrize("before,after", [
    ("Payable within 30 days.", "Payable within 60 days."),
    ("Not exceed £1,000,000.", "Not exceed £250,000."),
    ("Governed by England and Wales.", "Governed by Delaware."),
])
def test_real_differences_are_not_cosmetic(before, after) -> None:
    assert not is_cosmetic(before, after)


# ---------------------------------------- it names the values that moved

def test_the_money_change_is_found_and_both_figures_named() -> None:
    result = comparison()
    money = [c for c in result.changes if c.kind == "money"]
    assert money, [c.headline for c in result.changes]
    change = money[0]
    assert change.clause == "9.2"
    assert "£1,000,000" in change.values[0].removed
    assert "£250,000" in change.values[0].added
    assert "Clause 9.2: £1,000,000 → £250,000" == change.headline


def test_duration_changes_are_found_and_reported_as_durations() -> None:
    result = comparison()
    durations = {c.clause: c for c in result.changes if c.kind == "duration"}
    assert set(durations) == {"2", "4"}, [c.headline for c in result.changes]
    assert "24 months" in durations["2"].values[0].removed
    assert "36 months" in durations["2"].values[0].added
    assert "60 days" in durations["4"].values[0].added


def test_a_money_change_is_not_also_reported_as_a_number_change() -> None:
    """Reporting '000, 1,000 → 250,000' beside it buries the real finding."""
    result = comparison()
    money = [c for c in result.changes if c.kind == "money"][0]
    assert [v.kind for v in money.values] == ["money"]


def test_a_wording_change_with_no_figures_is_reported_as_wording() -> None:
    result = comparison()
    wording = [c for c in result.changes if c.clause == "12"]
    assert wording and wording[0].kind == "wording"
    assert "Delaware" in wording[0].after


# ---------------------------------- it separates structure from editing

def test_an_inserted_clause_is_reported_as_an_insertion() -> None:
    result = comparison()
    inserted = [c for c in result.changes if c.nature == "inserted"]
    assert inserted, [f"{c.nature}:{c.clause}" for c in result.changes]
    assert "Termination for convenience" in inserted[0].after
    assert inserted[0].headline.endswith("was added")


def test_a_deleted_clause_is_reported_as_a_deletion() -> None:
    result = comparison()
    deleted = [c for c in result.changes if c.nature == "deleted"]
    assert deleted, [f"{c.nature}:{c.clause}" for c in result.changes]
    assert "Confidentiality" in deleted[0].before


def test_structural_changes_are_available_separately() -> None:
    result = comparison()
    assert len(result.structural) == 2
    assert {c.nature for c in result.structural} == {"inserted", "deleted"}


# --------------------------------------------- it puts money first

def test_the_most_consequential_kind_is_reported_first() -> None:
    result = comparison()
    kinds = [c.kind for c in result.changes]
    assert kinds[0] == "money", kinds
    assert kinds.index("money") < kinds.index("duration") < kinds.index("wording")


# ---------------------------------------------- it reads real documents

def test_a_real_docx_is_read_with_no_dependency() -> None:
    document = read(docx(SENT), "sent.docx")
    assert document.kind == "docx"
    assert len(document.paragraphs) == len(SENT)
    assert document.paragraphs[5].clause == "9.2"


def test_plain_text_works_the_same_way() -> None:
    result = comparison(writer=plain)
    assert [c.kind for c in result.changes][0] == "money"
    assert len(result.cosmetic) == 2


# --------------------------------- it notices two unrelated documents

def test_two_unrelated_documents_are_recognised_rather_than_diffed() -> None:
    """A hundred findings is not an answer; a question is."""
    result = compare(read(docx(SENT), "a.docx"), read(docx(UNRELATED), "b.docx"))
    assert result.looks_unrelated is True


def test_two_versions_of_one_document_are_not_called_unrelated() -> None:
    assert comparison().looks_unrelated is False


# ------------------------------------------------------ marked up text

def test_the_changed_words_themselves_are_marked() -> None:
    result = comparison()
    money = [c for c in result.changes if c.kind == "money"][0]
    removed = [text for text, mark in money.marked_before if mark == "removed"]
    added = [text for text, mark in money.marked_after if mark == "added"]
    assert any("1,000,000" in t for t in removed), removed
    assert any("250,000" in t for t in added), added
    assert any(mark == "same" for _, mark in money.marked_before), (
        "unchanged words must stay unmarked, or everything looks changed")


def test_nothing_reports_a_confidence_score() -> None:
    result = comparison()
    assert not hasattr(result, "score")
    for change in result.changes:
        assert not hasattr(change, "confidence")

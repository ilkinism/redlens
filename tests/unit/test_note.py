"""The note is the deliverable. If it is wrong, the product is wrong."""

from __future__ import annotations

import base64

import pytest

from redlens.compare import compare
from redlens.documents import read
from redlens.note import compose
from support import RETURNED, SENT, docx


@pytest.fixture
def result():
    before = read(docx(SENT), "sent.docx")
    after = read(docx(RETURNED), "returned.docx")
    return compare(before, after)


def _find(result, clause):
    for change in result.changes:
        if change.clause == clause:
            return change
    raise AssertionError(f"no change on clause {clause}")


def test_nothing_queried_produces_nothing(result):
    assert compose(result.changes, set()) == ""


def test_the_note_names_the_clause_and_both_values(result):
    liability = _find(result, "9.2")
    text = compose(result.changes, {liability.index})
    assert "Clause 9.2" in text
    assert "£1,000,000" in text
    assert "£250,000" in text


def test_the_note_counts_its_own_queries(result):
    picked = {c.index for c in result.changes[:3]}
    text = compose(result.changes, picked)
    assert "3 changes" in text
    assert text.strip().endswith("Please confirm whether these were intended.")


def test_a_single_query_is_not_pluralised(result):
    text = compose(result.changes, {result.changes[0].index})
    assert "1 change:" in text


def test_queries_are_listed_in_document_order(result):
    picked = {c.index for c in result.changes}
    text = compose(result.changes, picked)
    positions = [text.index(f"\n{n}. ") if n > 1 else text.index("1. ")
                 for n in range(1, len(result.changes) + 1)]
    assert positions == sorted(positions)


def test_an_insertion_is_described_as_added(result):
    inserted = [c for c in result.changes if c.nature == "inserted"]
    assert inserted, "the fixture is meant to contain an inserted clause"
    text = compose(result.changes, {inserted[0].index})
    assert "has been added" in text
    assert inserted[0].after in text


def test_a_deletion_is_described_as_removed(result):
    deleted = [c for c in result.changes if c.nature == "deleted"]
    assert deleted, "the fixture is meant to contain a deleted clause"
    text = compose(result.changes, {deleted[0].index})
    assert "has been removed" in text
    assert deleted[0].before in text


def test_the_note_names_the_two_files(result):
    text = compose(result.changes, {result.changes[0].index},
                   before_name="round-two.docx", after_name="round-three.docx")
    assert "round-two.docx" in text
    assert "round-three.docx" in text


def test_a_duration_change_is_called_a_period(result):
    term = _find(result, "2")
    text = compose(result.changes, {term.index})
    assert "the period has changed" in text
    assert "24 months" in text and "36 months" in text


def test_unknown_indexes_are_ignored_rather_than_crashing(result):
    text = compose(result.changes, {9999})
    assert text == ""

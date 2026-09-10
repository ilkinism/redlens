"""Telling a changed deal from a changed keystroke.

Every comparison tool can list differences. The complaint behind this product
is that a moved comma and a halved liability cap arrive as equal entries in
that list, so the reader still has to read everything to find the four things
that matter.

So comparison happens twice, on two different texts:

- **Aligned on normalised text**, so a paragraph whose quote marks changed
  lines up with itself and does not present as an edit at all.
- **Judged on the original text**, so the difference is still *known about* and
  can be counted. Nothing is silently dropped; the report says how many
  differences were set aside and can show them.

What makes a change substantive is deliberately narrow and checkable: the money,
dates, durations or numbers it contains changed, or its words did. There is no
model, no score and no guess. A classification this product cannot justify is
one a reader would have to double-check, which would defeat the point.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal

from redlens.documents import Document, Paragraph

Kind = Literal["money", "date", "duration", "number", "wording"]
Nature = Literal["edited", "inserted", "deleted"]

# The order a reviewer checks things in, and the order findings are reported.
KIND_ORDER = ("money", "duration", "date", "number", "wording")

MONEY = re.compile(
    r"(?:[£$€]|\b(?:GBP|USD|EUR)\s?)\s?[\d,]+(?:\.\d{1,2})?"
    r"(?:\s?(?:million|billion|m|bn|k))?", re.I)
DATE = re.compile(
    r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", re.I)
DURATION = re.compile(
    r"\b\d+\s*(?:business\s+)?(?:day|days|week|weeks|month|months|year|years)\b",
    re.I)
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\s?%|\b\d[\d,]*(?:\.\d+)?\b")

# Every quote and dash folds to one form. A counterparty's editor turning
# 'Services' into "Services" is not a change to the deal, and treating it as
# one is exactly the noise this product exists to remove.
FOLD = str.maketrans({
    "’": "'", "‘": "'", "“": "'", "”": "'", '"': "'",
    "–": "-", "—": "-", "−": "-", " ": " ",
    "…": "...",
})
WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """What a paragraph says, ignoring how it was typed."""
    return WHITESPACE.sub(" ", text.translate(FOLD)).strip()


def is_cosmetic(before: str, after: str) -> bool:
    return normalise(before).casefold() == normalise(after).casefold()


@dataclass(frozen=True)
class ValueChange:
    kind: Kind
    removed: tuple
    added: tuple

    @property
    def sentence(self) -> str:
        was = ", ".join(self.removed) or "nothing"
        now = ", ".join(self.added) or "nothing"
        return f"{self.kind}: {was} → {now}"


@dataclass(frozen=True)
class Change:
    index: int
    nature: Nature
    kind: Kind
    before: str
    after: str
    clause: str
    values: tuple

    @property
    def headline(self) -> str:
        """One line naming the clause and what moved.

        The kind is shown beside this on the page, so it is deliberately not
        repeated here -- "MONEY  9.2 money: ..." reads as a stutter.
        """
        where = f"Clause {self.clause}" if self.clause else "An unnumbered clause"
        if self.nature == "inserted":
            return f"{where} was added"
        if self.nature == "deleted":
            return f"{where} was removed"
        if self.values:
            value = self.values[0]
            was = ", ".join(value.removed) or "nothing"
            now = ", ".join(value.added) or "nothing"
            return f"{where}: {was} \u2192 {now}"
        return f"{where}: the wording changed"

    @property
    def marked_before(self) -> list:
        return _mark(self.before, self.after)[0]

    @property
    def marked_after(self) -> list:
        return _mark(self.before, self.after)[1]


@dataclass(frozen=True)
class Comparison:
    changes: tuple
    cosmetic: tuple            # (before, after) pairs set aside as formatting
    paragraphs_before: int
    paragraphs_after: int
    unchanged: int

    @property
    def substantive(self) -> int:
        return len(self.changes)

    @property
    def by_kind(self) -> dict:
        counts: dict = {}
        for change in self.changes:
            counts[change.kind] = counts.get(change.kind, 0) + 1
        return counts

    @property
    def structural(self) -> tuple:
        return tuple(c for c in self.changes if c.nature != "edited")

    @property
    def matched(self) -> int:
        """Paragraphs that are recognisably the same paragraph in both files.

        An edited clause is matched -- it is still itself, differently worded.
        Only an insertion or a deletion is a paragraph with no counterpart.
        """
        edited = sum(1 for c in self.changes if c.nature == "edited")
        return self.unchanged + len(self.cosmetic) + edited

    @property
    def looks_unrelated(self) -> bool:
        """Whether these two files look like versions of the same document.

        Two unrelated documents share almost no paragraph with each other.
        Saying so is far more useful than presenting a hundred findings.
        """
        total = max(self.paragraphs_before, self.paragraphs_after)
        if total < 5:
            return False
        return self.matched / total < 0.25


def _values(before: str, after: str) -> tuple:
    """Which kinds of value moved, most consequential first.

    A bare number is only reported when nothing more specific explains it:
    £1,000,000 becoming £250,000 is a money change, and also reporting it as
    a number change buries the finding it belongs to.
    """
    found = []
    for kind, pattern in (("money", MONEY), ("duration", DURATION), ("date", DATE)):
        was = tuple(dict.fromkeys(m.strip() for m in pattern.findall(before)))
        now = tuple(dict.fromkeys(m.strip() for m in pattern.findall(after)))
        if set(was) != set(now):
            found.append(ValueChange(
                kind=kind, removed=tuple(v for v in was if v not in now),
                added=tuple(v for v in now if v not in was)))
    if not found:
        was = tuple(dict.fromkeys(NUMBER.findall(before)))
        now = tuple(dict.fromkeys(NUMBER.findall(after)))
        if set(was) != set(now):
            found.append(ValueChange(
                kind="number", removed=tuple(v for v in was if v not in now),
                added=tuple(v for v in now if v not in was)))
    return tuple(found)


def _mark(before: str, after: str) -> tuple:
    """The two paragraphs as runs of (text, mark), for proof-reading marks."""
    old, new = before.split(), after.split()
    matcher = difflib.SequenceMatcher(
        None, [w.translate(FOLD).casefold() for w in old],
        [w.translate(FOLD).casefold() for w in new], autojunk=False)
    left, right = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "delete", "replace") and i1 != i2:
            left.append((" ".join(old[i1:i2]),
                         "same" if tag == "equal" else "removed"))
        if tag in ("equal", "insert", "replace") and j1 != j2:
            right.append((" ".join(new[j1:j2]),
                          "same" if tag == "equal" else "added"))
    return left, right


# Below this, two paragraphs are different paragraphs rather than one edited
# one. Set where an edited clause still reads as itself but a replaced clause
# does not.
SAME_PARAGRAPH = 0.55


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(
        None, normalise(left).casefold(), normalise(right).casefold(),
        autojunk=False).ratio()


def _pair(old_paragraphs, new_paragraphs) -> list:
    """Match paragraphs across a replaced block, in document order.

    A clause number is the strongest signal there is -- 9.2 in both documents
    is the same clause however much its words moved -- so those are matched
    first. The rest are matched on similarity, best pair first, and anything
    unmatched is an insertion or a deletion.
    """
    pairs: list = []
    remaining_old = list(old_paragraphs)
    remaining_new = list(new_paragraphs)

    by_clause: dict = {}
    for paragraph in remaining_new:
        if paragraph.clause:
            by_clause.setdefault(paragraph.clause, []).append(paragraph)

    matched_old, matched_new = set(), set()
    for paragraph in remaining_old:
        candidates = by_clause.get(paragraph.clause) if paragraph.clause else None
        if candidates:
            partner = candidates.pop(0)
            pairs.append((paragraph, partner))
            matched_old.add(paragraph.index)
            matched_new.add(partner.index)

    left_over_old = [p for p in remaining_old if p.index not in matched_old]
    left_over_new = [p for p in remaining_new if p.index not in matched_new]

    scored = sorted(
        ((_similarity(a.text, b.text), a, b)
         for a in left_over_old for b in left_over_new),
        key=lambda item: -item[0])
    for score, a, b in scored:
        if score < SAME_PARAGRAPH:
            break
        if a.index in matched_old or b.index in matched_new:
            continue
        pairs.append((a, b))
        matched_old.add(a.index)
        matched_new.add(b.index)

    for paragraph in left_over_old:
        if paragraph.index not in matched_old:
            pairs.append((paragraph, None))
    for paragraph in left_over_new:
        if paragraph.index not in matched_new:
            pairs.append((None, paragraph))

    # Report in the order the reader will meet them in the document.
    return sorted(pairs, key=lambda pair: (
        pair[1].index if pair[1] is not None else pair[0].index))


def compare(before: Document, after: Document, *, max_changes: int = 2000) -> Comparison:
    old = [normalise(p.text).casefold() for p in before.paragraphs]
    new = [normalise(p.text).casefold() for p in after.paragraphs]
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)

    changes: list = []
    cosmetic: list = []
    unchanged = 0

    def add(nature: Nature, before_text: str, after_text: str) -> None:
        if len(changes) >= max_changes:
            return
        values = _values(before_text, after_text) if nature == "edited" else ()
        kind: Kind = values[0].kind if values else "wording"
        source = after_text or before_text
        clause = Paragraph(index=0, text=source).clause
        changes.append(Change(
            index=len(changes), nature=nature, kind=kind,
            before=before_text, after=after_text, clause=clause, values=values))

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                left = before.paragraphs[i1 + offset].text
                right = after.paragraphs[j1 + offset].text
                if left == right:
                    unchanged += 1
                else:
                    # Same words, different typing. Counted, never hidden.
                    cosmetic.append((left, right))
            continue

        if tag == "replace":
            # Pairing positionally inside a replaced block is wrong the moment
            # one clause is deleted and another inserted: everything after it
            # shifts, and clause 5 gets compared against clause 9.2. Paragraphs
            # are matched to each other instead, clause number first and text
            # similarity second, and whatever is left over really was inserted
            # or deleted.
            for left, right in _pair(
                    [before.paragraphs[i] for i in range(i1, i2)],
                    [after.paragraphs[j] for j in range(j1, j2)]):
                if left is not None and right is not None:
                    add("edited", left.text, right.text)
                elif left is not None:
                    add("deleted", left.text, "")
                else:
                    add("inserted", "", right.text)
        elif tag == "delete":
            for i in range(i1, i2):
                add("deleted", before.paragraphs[i].text, "")
        elif tag == "insert":
            for j in range(j1, j2):
                add("inserted", "", after.paragraphs[j].text)

    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    ranked = sorted(changes, key=lambda c: (order.get(c.kind, 99), c.index))
    ranked = tuple(
        Change(index=position, nature=c.nature, kind=c.kind, before=c.before,
               after=c.after, clause=c.clause, values=c.values)
        for position, c in enumerate(ranked))

    return Comparison(
        changes=ranked, cosmetic=tuple(cosmetic),
        paragraphs_before=len(before.paragraphs),
        paragraphs_after=len(after.paragraphs), unchanged=unchanged)

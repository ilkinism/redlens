"""What the browser can ask for.

Both documents travel with the request and neither is kept. A contract is the
most confidential thing this Factory has handled, and the safest place to store
it is nowhere.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from redlens.compare import compare
from redlens.config import Config
from redlens.documents import DocumentUnreadable, read
from redlens.note import compose


@dataclass(frozen=True)
class Reply:
    status: int
    body: dict


def _change_json(change) -> dict:
    return {
        "index": change.index,
        "nature": change.nature,
        "kind": change.kind,
        "clause": change.clause,
        "headline": change.headline,
        "before": change.before,
        "after": change.after,
        "marked_before": [{"text": t, "mark": m} for t, m in change.marked_before],
        "marked_after": [{"text": t, "mark": m} for t, m in change.marked_after],
        "values": [{"kind": v.kind, "removed": list(v.removed),
                    "added": list(v.added), "sentence": v.sentence}
                   for v in change.values],
    }


class RedlensAPI:
    def __init__(self, config: Config) -> None:
        self._config = config

    def _document(self, body: dict, field: str, label: str):
        raw = body.get(field)
        if not isinstance(raw, str) or not raw.strip():
            return None, Reply(400, {"error": f"There is no {label} to read."})
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            return None, Reply(400, {"error": f"The {label} could not be decoded."})
        name = str(body.get(f"{field}_name") or label)
        try:
            return read(data, name,
                        max_bytes=self._config.max_document_bytes,
                        max_paragraphs=self._config.max_paragraphs), None
        except DocumentUnreadable as exc:
            return None, Reply(422, {"error": str(exc)})

    def compare(self, body: dict) -> Reply:
        before, problem = self._document(body, "before", "version you sent")
        if problem:
            return problem
        after, problem = self._document(body, "after", "version that came back")
        if problem:
            return problem

        result = compare(before, after, max_changes=self._config.max_changes)
        return Reply(200, {
            "before_name": before.name, "after_name": after.name,
            "unrelated": result.looks_unrelated,
            "summary": {
                "changes": result.substantive,
                "set_aside": len(result.cosmetic),
                "unchanged": result.unchanged,
                "matched": result.matched,
                "by_kind": result.by_kind,
                "paragraphs_before": result.paragraphs_before,
                "paragraphs_after": result.paragraphs_after,
                "structural": len(result.structural),
            },
            "changes": [_change_json(c) for c in result.changes],
            "set_aside": [{"before": b, "after": a} for b, a in result.cosmetic],
        })

    def note(self, body: dict) -> Reply:
        before, problem = self._document(body, "before", "version you sent")
        if problem:
            return problem
        after, problem = self._document(body, "after", "version that came back")
        if problem:
            return problem

        queried = body.get("queried")
        if not isinstance(queried, list):
            return Reply(400, {"error": "There are no queries to write up."})
        try:
            wanted = {int(index) for index in queried}
        except (TypeError, ValueError):
            return Reply(400, {"error": "A query has to name a change by number."})

        result = compare(before, after, max_changes=self._config.max_changes)
        text = compose(result.changes, wanted,
                       before_name=before.name, after_name=after.name)
        if not text:
            return Reply(409, {"error": (
                "Nothing has been queried yet. Mark the changes you want to "
                "raise and the note will write itself.")})
        return Reply(200, {"note": text, "queried": len(wanted)})

    def health(self) -> Reply:
        return Reply(200, {"status": "ok"})

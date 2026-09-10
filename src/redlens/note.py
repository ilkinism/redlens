"""The note that goes back to the other side.

The output of a review is not a report, it is a reply. Turning the queried
changes into the paragraph a person actually sends is the last step of the job
and the reason this is a workflow rather than a diff.
"""

from __future__ import annotations

ORDINAL = {"money": "the figure", "duration": "the period",
           "date": "the date", "number": "the number"}


def compose(changes, queried, *, before_name="the version we sent",
            after_name="the version returned") -> str:
    """A plain note listing what is being queried, in document order."""
    picked = [c for c in changes if c.index in queried]
    if not picked:
        return ""

    lines = [
        f"Comparing {before_name} with {after_name}, we have queries on "
        f"{len(picked)} change{'s' if len(picked) != 1 else ''}:",
        "",
    ]
    for position, change in enumerate(sorted(picked, key=lambda c: c.index), 1):
        where = f"Clause {change.clause}" if change.clause else "An unnumbered clause"
        if change.nature == "inserted":
            lines.append(f"{position}. {where} has been added:")
            lines.append(f"   \"{change.after}\"")
        elif change.nature == "deleted":
            lines.append(f"{position}. {where} has been removed:")
            lines.append(f"   \"{change.before}\"")
        else:
            if change.values:
                value = change.values[0]
                what = ORDINAL.get(value.kind, "the wording")
                lines.append(
                    f"{position}. {where}: {what} has changed from "
                    f"{', '.join(value.removed) or 'nothing'} to "
                    f"{', '.join(value.added) or 'nothing'}.")
            else:
                lines.append(f"{position}. {where}: the wording has changed.")
            lines.append(f"   Was: \"{change.before}\"")
            lines.append(f"   Now: \"{change.after}\"")
        lines.append("")
    lines.append("Please confirm whether these were intended.")
    return "\n".join(lines)

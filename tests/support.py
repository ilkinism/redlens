"""Contract fixtures, written as real .docx files with the standard library."""

from __future__ import annotations

import io
import zipfile

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.document.main+xml"/></Types>')
RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def docx(paragraphs) -> bytes:
    """A real .docx: a zip of XML, as Word writes it."""
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{_escape(p)}</w:t></w:r></w:p>'
        for p in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body></w:document>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def plain(paragraphs) -> bytes:
    return "\n\n".join(paragraphs).encode("utf-8")


SENT = (
    "1. Definitions. 'Services' means the services described in Schedule 1.",
    "2. Term. This Agreement commences on 1 January 2026 and continues for 24 months.",
    "3. Fees. The Customer shall pay £120,000 per annum, invoiced quarterly.",
    "4. Payment terms. Invoices are payable within 30 days of receipt.",
    "5. Confidentiality. Each party shall keep the other's information confidential.",
    "9.2 Liability. The Supplier's total liability shall not exceed £1,000,000.",
    "12. Governing law. This Agreement is governed by the laws of England and Wales.",
    "14. Notices. Notices shall be sent to the addresses set out in Schedule 2.",
)

# What came back: four substantive edits, one inserted clause, one deleted
# clause, and two paragraphs whose only difference is how they were typed.
RETURNED = (
    "1. Definitions. “Services” means the services described in Schedule 1.",
    "2. Term. This Agreement commences on 1 January 2026 and continues for 36 months.",
    "3. Fees. The Customer shall pay £120,000  per annum, invoiced quarterly.",
    "4. Payment terms. Invoices are payable within 60 days of receipt.",
    "9.2 Liability. The Supplier's total liability shall not exceed £250,000.",
    "12. Governing law. This Agreement is governed by the laws of Delaware.",
    "13. Termination for convenience. Either party may terminate on 90 days' notice.",
    "14. Notices. Notices shall be sent to the addresses set out in Schedule 2.",
)

UNRELATED = (
    "Minutes of the quarterly meeting held on 3 March 2026.",
    "Present: the operations team and two members of the board.",
    "The renewal of the office lease was discussed at length.",
    "A decision on the new supplier was deferred to the next meeting.",
    "The meeting closed at 15:40.",
    "Next meeting: 3 June 2026.",
)

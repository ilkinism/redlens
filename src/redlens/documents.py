"""Getting the words out of a document, and refusing what cannot be read.

A .docx is a zip holding XML, which the standard library reads without help.
That matters here beyond tidiness: a contract is confidential, and every
dependency is another party with a copy of the code that touches it.

Only the text is taken. Fonts, spacing, colours and comments are all deliberately
discarded -- the question this product answers is what the document *says*, and
carrying presentation around would only make it harder to tell a changed clause
from a changed style.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# A .docx is a zip; a stray .doc or PDF is not, and each gets its own answer.
PDF_MAGIC = b"%PDF"
OLE_MAGIC = b"\xd0\xcf\x11\xe0"          # the old binary .doc container
ZIP_MAGIC = b"PK\x03\x04"


class DocumentUnreadable(Exception):
    """The file cannot be read as a document. The message says why."""


@dataclass(frozen=True)
class Paragraph:
    """One paragraph of a document, and where it sat."""

    index: int
    text: str

    @property
    def clause(self) -> str:
        """The clause number this paragraph opens with, if it has one.

        Contracts are argued about by number, so a change is far more useful
        reported as '9.2 Liability' than as 'paragraph 47'.
        """
        match = re.match(r"^\s*((?:\d+|[A-Z])(?:\.\d+)*)[.)]?\s", self.text)
        return match.group(1) if match else ""


@dataclass(frozen=True)
class Document:
    name: str
    paragraphs: tuple
    kind: str                       # "docx" | "text"

    @property
    def words(self) -> int:
        return sum(len(p.text.split()) for p in self.paragraphs)


# A .docx is a zip, and a zip can claim to be small and unpack to gigabytes.
# The size limit on the file that arrives says nothing about the size of the
# XML inside it, so the unpacked document is capped separately. Real contracts
# are far below this: a hundred-page agreement is a few megabytes of XML.
MAX_UNPACKED_BYTES = 134_217_728

DOCTYPE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)


def _from_docx(data: bytes, name: str,
               max_unpacked: int = MAX_UNPACKED_BYTES) -> tuple:
    too_big = DocumentUnreadable(
        f"The document inside {name} unpacks to more than "
        f"{max_unpacked // 1_048_576} MB, which no contract does. Redlens has "
        f"stopped rather than trying to read it.")
    try:
        with zipfile.ZipFile(_BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise DocumentUnreadable(
                    f"{name} is a zip file but not a Word document — there is "
                    f"no document inside it.")
            # The header's claim is checked first because it is free, and then
            # the read itself is capped, because the header can lie.
            if archive.getinfo("word/document.xml").file_size > max_unpacked:
                raise too_big
            with archive.open("word/document.xml") as member:
                xml = member.read(max_unpacked + 1)
            if len(xml) > max_unpacked:
                raise too_big
    except zipfile.BadZipFile:
        raise DocumentUnreadable(f"{name} could not be opened.") from None

    # Word never writes a document type declaration, and the only things one
    # can do here are harmful: a chain of entity definitions turns a kilobyte
    # into a hundred megabytes when parsed, and an external entity asks the
    # parser to read a file off this machine. Both are refused by refusing the
    # declaration itself, which costs a genuine document nothing.
    if DOCTYPE.search(xml[:8192]):
        raise DocumentUnreadable(
            f"{name} carries a document type declaration, which Word does not "
            f"write and which can be used to attack whoever opens the file. "
            f"Redlens will not read it.")

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        raise DocumentUnreadable(
            f"The text of {name} could not be read. If Word can still open it, "
            f"saving a fresh copy usually repairs this.") from None

    found = []
    for node in root.iter(f"{WORD}p"):
        # Deleted runs (w:delText) are what a tracked deletion leaves behind.
        # They are not part of what the document says, so they are dropped.
        text = "".join(t.text or "" for t in node.iter(f"{WORD}t"))
        if text.strip():
            found.append(text.strip())
    return tuple(found)


def _from_text(data: bytes, name: str) -> tuple:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError:
            raise DocumentUnreadable(
                f"{name} is not text that could be decoded.") from None
    # A blank line separates paragraphs; a single newline inside one is a wrap.
    blocks = re.split(r"\n\s*\n", text)
    found = []
    for block in blocks:
        joined = " ".join(line.strip() for line in block.splitlines()).strip()
        if joined:
            found.append(joined)
    return tuple(found)


class _BytesIO:
    """A tiny shim so zipfile can read bytes without importing io here."""

    def __init__(self, data: bytes) -> None:
        import io
        self._buffer = io.BytesIO(data)

    def __getattr__(self, name):
        return getattr(self._buffer, name)


def read(data: bytes, name: str = "the document", *,
         max_bytes: int = 20_971_520, max_paragraphs: int = 20_000,
         max_unpacked_bytes: int = MAX_UNPACKED_BYTES) -> Document:
    """Read a document, or refuse it in terms its owner would use."""
    if not data:
        raise DocumentUnreadable(f"{name} is empty.")
    if len(data) > max_bytes:
        raise DocumentUnreadable(
            f"{name} is larger than {max_bytes // 1_048_576} MB. A contract is "
            f"rarely that big — check it is the right file.")

    if data.startswith(PDF_MAGIC):
        raise DocumentUnreadable(
            f"{name} is a PDF. Redlens reads .docx and plain text, because "
            f"that is what contracts are negotiated in — the PDF is usually "
            f"the signed end of it. Ask for the Word version.")
    if data.startswith(OLE_MAGIC):
        raise DocumentUnreadable(
            f"{name} is an old .doc file. Open it in Word and save it as "
            f".docx, and Redlens can read it.")

    if data.startswith(ZIP_MAGIC):
        paragraphs = _from_docx(data, name, max_unpacked_bytes)
        kind = "docx"
    else:
        paragraphs = _from_text(data, name)
        kind = "text"

    if not paragraphs:
        raise DocumentUnreadable(f"There is no text in {name}.")
    if len(paragraphs) > max_paragraphs:
        raise DocumentUnreadable(
            f"{name} has {len(paragraphs)} paragraphs, more than the "
            f"{max_paragraphs} Redlens handles.")

    return Document(name=name, kind=kind, paragraphs=tuple(
        Paragraph(index=i, text=t) for i, t in enumerate(paragraphs)))

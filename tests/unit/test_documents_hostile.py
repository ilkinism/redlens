"""A contract arrives from the other side. Assume the file is not friendly.

Each of these is a way a .docx can attack the machine that opens it, found by
building the hostile file and watching what the reader did with it.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from redlens.documents import DocumentUnreadable, read
from support import CONTENT_TYPES, RELS

BODY = ('<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>%s</w:body></w:document>')


def paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def package(document_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_a_decompression_bomb_is_refused_before_it_is_unpacked():
    """A megabyte on the wire, a gigabyte in memory."""
    bomb = package(BODY % (paragraph("A" * 1_000_000) * 1000))
    assert len(bomb) < 2_000_000
    with pytest.raises(DocumentUnreadable) as refused:
        read(bomb, "hostile.docx")
    assert "unpacks to more than" in str(refused.value)


def test_entity_expansion_is_refused():
    """A kilobyte of entity definitions expands without limit when parsed."""
    document = (
        '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
        '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">'
        '<!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">'
        '<!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;">'
        '<!ENTITY f "&e;&e;&e;&e;&e;&e;&e;&e;&e;&e;">]>'
        + BODY % paragraph("&f;"))
    with pytest.raises(DocumentUnreadable) as refused:
        read(package(document), "hostile.docx")
    assert "document type declaration" in str(refused.value)


def test_an_external_entity_cannot_read_a_file_off_this_machine():
    document = ('<?xml version="1.0"?>'
                '<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
                + BODY % paragraph("&x;"))
    with pytest.raises(DocumentUnreadable):
        read(package(document), "hostile.docx")


def test_a_zip_that_is_not_a_word_document_says_so():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "hi")
    with pytest.raises(DocumentUnreadable) as refused:
        read(buffer.getvalue(), "spreadsheet.xlsx")
    assert "not a Word document" in str(refused.value)


def test_broken_xml_suggests_the_repair_that_works():
    with pytest.raises(DocumentUnreadable) as refused:
        read(package("<<< not xml >>>"), "damaged.docx")
    assert "saving a fresh copy" in str(refused.value)


def test_a_document_with_no_text_is_refused():
    with pytest.raises(DocumentUnreadable) as refused:
        read(package(BODY % ""), "blank.docx")
    assert "no text" in str(refused.value)


def test_markup_in_the_text_stays_text():
    """The page renders with textContent, and the reader must see the words."""
    document = read(package(BODY % paragraph(
        "&lt;script&gt;alert(1)&lt;/script&gt; is the clause heading")), "odd.docx")
    assert document.paragraphs[0].text.startswith("<script>alert(1)</script>")


def test_a_genuine_document_is_still_read():
    """The guards must not cost an ordinary contract anything."""
    document = read(package(BODY % (paragraph("1. Definitions.")
                                    + paragraph("2. Term. 24 months."))), "fine.docx")
    assert [p.text for p in document.paragraphs] == ["1. Definitions.", "2. Term. 24 months."]

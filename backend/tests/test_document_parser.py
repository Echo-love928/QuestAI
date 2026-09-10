from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import docx2txt
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.knowledge.parsers import DocumentParseError, DocumentParser, LegacyDocParser


@pytest.mark.anyio
async def test_markdown_is_parsed_and_control_characters_removed(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("# 标题\n有效\x00内容\n## 第二节\n更多内容", encoding="utf-8")
    pages = await DocumentParser(max_chars=1000).parse(path, "md")
    assert "\x00" not in pages[0].page_content
    assert pages[0].metadata["source_type"] == "markdown"


@pytest.mark.anyio
async def test_text_pdf_is_parsed_with_page_location(tmp_path: Path) -> None:
    path = tmp_path / "guide.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Customer service policy content) Tj ET")
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as output:
        writer.write(output)

    pages = await DocumentParser(max_chars=1000).parse(path, "pdf")
    assert "Customer service policy" in pages[0].page_content
    assert pages[0].metadata["page"] == 1


@pytest.mark.anyio
async def test_empty_pdf_is_reported_as_scanned_or_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as output:
        writer.write(output)
    with pytest.raises(DocumentParseError, match="扫描|文本"):
        await DocumentParser(max_chars=1000).parse(path, "pdf")


@pytest.mark.anyio
async def test_encrypted_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    with path.open("wb") as output:
        writer.write(output)
    with pytest.raises(DocumentParseError, match="加密"):
        await DocumentParser(max_chars=1000).parse(path, "pdf")


@pytest.mark.anyio
async def test_docx_parser_uses_extracted_text(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "guide.docx"
    path.write_bytes(b"placeholder")
    monkeypatch.setattr(docx2txt, "process", lambda _: "客服流程\n先确认用户诉求，再处理。")
    pages = await DocumentParser(max_chars=1000).parse(path, "docx")
    assert "确认用户诉求" in pages[0].page_content


@pytest.mark.anyio
async def test_real_minimal_docx_is_parsed(tmp_path: Path) -> None:
    path = tmp_path / "guide.docx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
        archive.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>客服流程：先确认用户诉求，再按权限处理。</w:t></w:r></w:p></w:body></w:document>""")
    pages = await DocumentParser(max_chars=1000).parse(path, "docx")
    assert "确认用户诉求" in pages[0].page_content


class FakeLegacyParser(LegacyDocParser):
    async def extract(self, path: Path) -> str:
        return "旧版 Word 中的有效制度内容。"


@pytest.mark.anyio
async def test_legacy_doc_parser_is_pluggable(tmp_path: Path) -> None:
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"ole")
    pages = await DocumentParser(max_chars=1000, legacy_parser=FakeLegacyParser()).parse(path, "doc")
    assert pages[0].metadata["source_type"] == "legacy_doc"


@pytest.mark.anyio
async def test_unsupported_extension_does_not_invoke_legacy_runtime(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_text("content", encoding="utf-8")
    with pytest.raises(DocumentParseError, match="不支持"):
        await DocumentParser(max_chars=1000).parse(path, "txt")

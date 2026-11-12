"""Validation de signature et extraction de texte (PDF page par page, DOCX par section, TXT/MD)."""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field

ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class ExtractionError(Exception):
    """Message affichable et non sensible."""


@dataclass
class Segment:
    text: str
    page: int | None = None
    section: str | None = None


@dataclass
class Extracted:
    segments: list[Segment] = field(default_factory=list)
    page_count: int | None = None

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.segments)


def extension(filename: str) -> str:
    m = re.search(r"\.[A-Za-z0-9]+$", filename or "")
    return m.group(0).lower() if m else ""


def sniff(filename: str, data: bytes) -> str:
    """Vérifie extension + signature binaire. Retourne le type MIME, ou lève ValueError."""
    ext = extension(filename)
    if ext not in ALLOWED:
        raise ValueError("Format non accepté. Formats autorisés : PDF, DOCX, TXT, MD.")
    if ext == ".pdf":
        if b"%PDF-" not in data[:1024]:
            raise ValueError("Le fichier n'est pas un PDF valide.")
    elif ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" not in z.namelist():
                    raise ValueError
        except Exception:
            raise ValueError("Le fichier n'est pas un DOCX valide.") from None
    else:
        if b"\x00" in data[:8192]:
            raise ValueError("Le fichier texte contient des données binaires.")
    return ALLOWED[ext]


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("­", "").replace("\x00", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # césures de fin de ligne
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _pdf(data: bytes) -> Extracted:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise ExtractionError("PDF illisible ou corrompu.") from None
    with doc:
        if doc.needs_pass:
            raise ExtractionError("PDF protégé par mot de passe.")
        out = Extracted(page_count=doc.page_count)
        for i, page in enumerate(doc, start=1):
            text = clean_text(page.get_text("text", sort=True))
            if text:
                out.segments.append(Segment(text=text, page=i))
    if out.char_count < 20:
        raise ExtractionError("Aucun texte extractible (PDF scanné ? L'OCR n'est pas encore pris en charge).")
    return out


def _docx(data: bytes) -> Extracted:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception:
        raise ExtractionError("DOCX illisible ou corrompu.") from None
    out = Extracted()
    section: str | None = None
    buf: list[str] = []

    def flush():
        text = clean_text("\n".join(buf))
        if text:
            out.segments.append(Segment(text=text, section=section))
        buf.clear()

    for block in d.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            style = (block.style.name or "").lower() if block.style is not None else ""
            if style.startswith(("heading", "titre", "title")):
                flush()
                section = text[:255]
                buf.append(text)
            else:
                buf.append(text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [c.text.strip() for c in row.cells]
                buf.append(" | ".join(dict.fromkeys(c for c in cells if c)))
    flush()
    if out.char_count < 1:
        raise ExtractionError("Le document DOCX ne contient pas de texte.")
    return out


def _txt(data: bytes) -> Extracted:
    # UTF-16 uniquement si un BOM est présent (sinon il « décode » n'importe quelle suite d'octets)
    encodings = ("utf-16",) if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig", "cp1252", "latin-1")
    for enc in encodings + ("latin-1",):
        try:
            text = data.decode(enc)
            break
        except UnicodeError:
            continue
    text = clean_text(text)
    if not text:
        raise ExtractionError("Le fichier texte est vide.")
    return Extracted(segments=[Segment(text=text)])


def extract(filename: str, data: bytes) -> Extracted:
    ext = extension(filename)
    if ext == ".pdf":
        return _pdf(data)
    if ext == ".docx":
        return _docx(data)
    if ext in (".txt", ".md"):
        return _txt(data)
    raise ExtractionError("Format non pris en charge.")

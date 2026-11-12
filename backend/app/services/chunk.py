"""Découpage en chunks (~900 caractères, recouvrement ~150) respectant paragraphes et phrases."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.extract import Extracted

_SENT = re.compile(r"(?<=[.!?…;:])\s+(?=[A-ZÀ-ÖØ-Þ0-9«\"“(\[•\-])")


@dataclass
class Chunk:
    ordinal: int
    text: str
    page: int | None
    section: str | None


def _units(text: str, size: int) -> list[str]:
    """Paragraphes -> phrases -> coupes dures, de sorte qu'aucune unité ne dépasse `size`."""
    units: list[str] = []
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            units.append(para)
            continue
        for sent in _SENT.split(para.replace("\n", " ")):
            sent = sent.strip()
            while len(sent) > size:
                cut = sent.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                units.append(sent[:cut].strip())
                sent = sent[cut:].strip()
            if sent:
                units.append(sent)
    return units


def split_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    units = _units(text, size)
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for u in units:
        if cur and cur_len + len(u) + 1 > size:
            chunks.append(" ".join(cur))
            # recouvrement : on reprend les dernières unités jusqu'à ~overlap caractères
            tail: list[str] = []
            tail_len = 0
            for prev in reversed(cur):
                if tail_len + len(prev) > overlap:
                    break
                tail.insert(0, prev)
                tail_len += len(prev) + 1
            if not tail and overlap > 0 and len(cur[-1]) > overlap:
                frag = cur[-1][-overlap:]
                sp = frag.find(" ")
                tail, tail_len = [frag[sp + 1:] if sp >= 0 else frag], overlap
            cur, cur_len = tail, tail_len
        cur.append(u)
        cur_len += len(u) + 1
    if cur:
        last = " ".join(cur)
        if chunks and len(last) < overlap + 40 and last in chunks[-1]:
            pass  # reliquat entièrement contenu dans le chunk précédent
        else:
            chunks.append(last)
    return chunks


def chunk_document(extracted: Extracted, size: int = 900, overlap: int = 150) -> list[Chunk]:
    out: list[Chunk] = []
    for seg in extracted.segments:
        for piece in split_text(seg.text, size, overlap):
            if len(piece.strip()) < 3:
                continue
            out.append(Chunk(ordinal=len(out), text=piece.strip(), page=seg.page, section=seg.section))
    return out

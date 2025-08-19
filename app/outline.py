import fitz  # PyMuPDF
from collections import defaultdict, Counter
import re

NOISE_RE = re.compile(r"(copyright|©|page \d+ of \d+|version\s*\d|istqb|all rights reserved)", re.I)

def _clean(text: str) -> str:
    text = " ".join(text.split())
    return (text + " ") if text else ""

def _any_letters(s: str) -> bool:
    return any(c.isalpha() for c in s)

def extract_blocks(doc):
    grouped_lines = []
    font_sizes = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict").get("blocks", [])
        rows = defaultdict(list)

        for b in blocks:
            for line in b.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                text = _clean(" ".join(s.get("text", "").strip() for s in spans if s.get("text")))
                if not text.strip():
                    continue

                size = round(float(spans[0].get("size", 0)), 1)
                bbox = spans[0].get("bbox", (0, 0, 0, 0))
                y = round(bbox[1], 1)
                rows[(size, y)].append({
                    "text": text,
                    "size": size,
                    "page": page_num,
                    "bbox": bbox,
                })
                font_sizes.append(size)

        for (size, _y), lines in rows.items():
            merged = _clean(" ".join(l["text"].strip() for l in lines))
            if merged:
                grouped_lines.append({
                    "text": merged,
                    "size": size,
                    "page": lines[0]["page"],
                    "bbox": lines[0]["bbox"],
                })

    return font_sizes, grouped_lines

def _map_font_sizes(font_sizes):
    if not font_sizes:
        return {}
    uniq = sorted({round(s, 1) for s in font_sizes}, reverse=True)
    top = uniq[:3]  # H1,H2,H3
    levels = ["H1", "H2", "H3"]
    return {size: levels[i] for i, size in enumerate(top)}

def detect_title(blocks, max_font):
    parts = []
    for b in blocks:
        if b["page"] == 0 and round(b["size"], 1) == round(max_font, 1):
            t = b["text"].strip()
            if _any_letters(t) and not NOISE_RE.search(t):
                parts.append(t)
    return "  ".join(parts)

def build_outline(blocks, font_map):
    outline = []
    seen = set()

    for b in blocks:
        txt = b["text"].strip()
        if not _any_letters(txt) or NOISE_RE.search(txt):
            continue

        lvl = font_map.get(round(b["size"], 1))
        if not lvl:
            continue

        if len(txt) > 140:
            continue

        key = (txt, b["page"])
        if key in seen:
            continue
        seen.add(key)

        outline.append({
            "level": lvl,
            "text": _clean(txt),
            "page": b["page"] + 1,  # 1-based pages for UI
        })

    # Sort by page, then by text as a stable fallback
    outline.sort(key=lambda x: (x["page"], x["text"]))
    return outline

def outline_from_pdf(pdf_path: str):
    doc = fitz.open(pdf_path)
    try:
        sizes, blocks = extract_blocks(doc)
        font_map = _map_font_sizes(sizes)
        title = detect_title(blocks, max(sizes) if sizes else 0)
        outline = build_outline(blocks, font_map)
        return {"title": title, "outline": outline}
    finally:
        doc.close()
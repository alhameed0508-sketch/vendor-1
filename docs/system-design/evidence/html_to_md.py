"""Convert MuleCatch-System-Design.html into docs/SYSTEM_DESIGN.md (same content, diagrams as PNGs).

Usage: python html_to_md.py   (run from docs/system-design/evidence; needs beautifulsoup4 + markdownify)
"""
import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "MuleCatch-System-Design.html"
OUT = HERE.parent.parent / "SYSTEM_DESIGN.md"
DIAGRAMS = {  # svg <title> prefix -> image file in docs/system-design/
    "Overview": ("system-design/MuleCatch-System-Design-overview.png", "The whole system on one page"),
    "Unified pipeline": ("system-design/diagram-pipeline.png", "Unified pipeline"),
    "Sequence": ("system-design/diagram-request-path.png", "One payment scored"),
    "Simplified data model": ("system-design/diagram-data-model.png", "Data model"),
    "Growth path": ("system-design/diagram-growth.png", "Growth path"),
}
LABELS = {"v": "V", "a": "A", "p": "P", "e": "E", "u": "?"}

HEADER = """# MuleCatch risk engine: system design

> Generated with the **sketch-system-design** skill. The formatted page with the hand-drawn diagrams is
> [`system-design/MuleCatch-System-Design.html`](system-design/MuleCatch-System-Design.html)
> (PDF: [`MuleCatch-System-Design.pdf`](system-design/MuleCatch-System-Design.pdf)). This Markdown copy is generated
> from it by `system-design/evidence/html_to_md.py`, so the two never disagree. Every number comes from
> `system-design/evidence/workload_model.py` or `capacity_benchmark.py`.
>
> Labels: **[V]** verified or measured · **[A]** assumption · **[P]** proposal · **[E]** exists today · **[?]** unknown.

## Where each part of the brief is answered

| Brief asks for | Section |
|---|---|
| Existing architecture assessment | §7 Audit of today's system |
| Proposed enhanced architecture | §1 One-page picture, §6.2 Unified pipeline |
| Component-level architecture | §6.1 Box by box, §6.3 The four engines |
| End-to-end data flow | §6.2 Unified pipeline, §6.6 Main request path |
| Real-time event processing | §4 How many requests, §6.6, §6.14 Growth path |
| Mule detection integration | §6.3.1 Mule network: the core |
| The three new engines | §6.3.2 Session, §6.3.3 Payment intent & beneficiary, §6.3.4 Behaviour |
| ML model and feature engineering | §6.5 Scoring, bands and the model |
| Database and storage design | §6.7 Data model, §4.6 Storage |
| API specifications | §6.8 API |
| External integrations | §6.9 Real data sources and provenance |
| Risk scoring and decision logic | §6.5 Scoring, bands and the model |
| False-positive prevention | §6.4 False-positive control, §5 Base rate, §7.2 |
| Security, privacy and access control | §6.10 Security, privacy and access |
| Scalability and performance | §2 Numbers, §4, §6.14 Growth path, §6.15 Cost |
| Monitoring, logging and feedback | §6.11 Monitoring, logging and feedback |
| Deployment architecture | §6.13 Deployment |
| Testing and validation | §6.12 Testing and evaluation |

"""


def main():
    soup = BeautifulSoup(PAGE.read_text(encoding="utf-8"), "html.parser")
    main_el = soup.find("main")
    main_el.find("header").decompose()
    for span in main_el.select("span.t"):
        kind = next((c for c in span.get("class", []) if c in LABELS), None)
        span.replace_with(f"[{LABELS[kind]}] " if kind else span.get_text())
    for num in main_el.select("h2 span.num"):
        num.replace_with(f"{num.get_text()} · ")
    for tiles in main_el.select("div.tiles"):
        table = BeautifulSoup("<table><thead><tr><th>Measure</th><th>Pilot</th><th>Detail</th></tr></thead><tbody></tbody></table>",
                              "html.parser")
        body = table.find("tbody")
        for tile in tiles.select("div.tile"):
            row = table.new_tag("tr")
            for cls in ("tk", "tv", "ts"):
                cell = table.new_tag("td")
                part = tile.find("div", class_=cls)
                cell.string = part.get_text(" ", strip=True) if part else ""
                row.append(cell)
            body.append(row)
        tiles.replace_with(table)
    for board in main_el.select("div.board"):
        title = board.find("title").get_text() if board.find("title") else ""
        image = next((v for k, v in DIAGRAMS.items() if title.startswith(k)), None)
        para = soup.new_tag("p")
        if image:
            img = soup.new_tag("img", src=image[0], alt=image[1])
            para.append(img)
        board.replace_with(para)
    md = markdownify(str(main_el), heading_style="ATX", bullets="-", strip=["main", "section", "div"],
                     escape_misc=False, escape_underscores=False)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    md = md.replace("](#", "](#")  # in-page anchors stay as they are
    OUT.write_text(HEADER + md, encoding="utf-8")
    print(f"wrote {OUT} ({len(md):,} chars)")


if __name__ == "__main__":
    main()

"""Design-system helpers for building a projector-safe 16:9 pitch deck with python-pptx.
Palette + typography are constants so a deck stays consistent. All sizes in inches.
Usage: from deck_lib import *  (see build_deck.py for an example)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree
import os

# ---------- palette: dark navy/purple ground, orange accent (echoes iQOO), semantic green/red ----------
NAVY = "14142B"; NAVY2 = "1C1B3A"; PURPLE = "2D1A63"; PURPLE2 = "3A2472"
ORANGE = "F5A623"; ORANGE2 = "FFB84D"; GREEN = "2E9E5B"; RED = "D64545"
WHITE = "FFFFFF"; LAV = "F1EEFA"; MUTED = "A9A6C2"; MUTED2 = "8D8AAB"
CARD = "23224A"; CARD2 = "2A2952"; LINE = "3B3A66"
FONT_H = "Segoe UI"; FONT_B = "Segoe UI"; FONT_MONO = "Consolas"
SLIDE_W, SLIDE_H = 13.333, 7.5


def rgb(h):
    return RGBColor.from_string(h.upper())


def new_prs():
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def bg(slide, color=NAVY, gradient_to=None, angle=45):
    f = slide.background.fill
    if gradient_to:
        f.gradient()
        f.gradient_angle = angle
        f.gradient_stops[0].color.rgb = rgb(color)
        f.gradient_stops[1].color.rgb = rgb(gradient_to)
    else:
        f.solid()
        f.fore_color.rgb = rgb(color)


def _no_line(shape):
    shape.line.fill.background()


def _no_shadow(shape):
    etree.SubElement(shape._element.spPr, qn("a:effectLst"))


def rect(slide, x, y, w, h, fill=CARD, line=None, radius=None, line_w=1.0):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        shp.adjustments[0] = min(0.5, radius / min(w, h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(line_w)
    else:
        _no_line(shp)
    _no_shadow(shp)
    return shp


def oval(slide, x, y, w, h, fill=ORANGE, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    if line:
        shp.line.color.rgb = rgb(line)
    else:
        _no_line(shp)
    _no_shadow(shp)
    return shp


def text(slide, x, y, w, h, content, size=18, color=WHITE, bold=False, font=None, align="l", anchor="t",
         italic=False, spacing=1.05, wrap=True, mono=False, para_space=0, margin=0.05):
    """content: str | list of paragraphs. paragraph: str | list of runs. run: str | (str, {size,color,bold,italic,font})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    paras = content if isinstance(content, list) else [content]
    base_font = font or (FONT_MONO if mono else FONT_B)
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        p.line_spacing = spacing
        if para_space:
            p.space_after = Pt(para_space)
        runs = para if isinstance(para, list) else [para]
        for run in runs:
            s, o = run if isinstance(run, tuple) else (run, {})
            r = p.add_run()
            r.text = s
            f = r.font
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.name = o.get("font", base_font)
            f.color.rgb = rgb(o.get("color", color))
    return tb


def image(slide, path, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)


def line(slide, x1, y1, x2, y2, color=LINE, width=1.5, dash=False):
    c = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = 4
    return c


def arrow(slide, x, y, w, h, fill=ORANGE, direction="r"):
    kind = {"r": MSO_SHAPE.RIGHT_ARROW, "d": MSO_SHAPE.DOWN_ARROW}[direction]
    shp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    _no_line(shp)
    _no_shadow(shp)
    return shp


def pill(slide, x, y, w, h, label, fill=ORANGE, color=NAVY, size=12, bold=True):
    r = rect(slide, x, y, w, h, fill=fill, radius=h / 2)
    text(slide, x, y, w, h, label, size=size, color=color, bold=bold, align="c", anchor="m")
    return r


def card(slide, x, y, w, h, title=None, body=None, fill=CARD, accent=None, title_size=16, body_size=13,
         icon=None, radius=0.14, title_color=WHITE, body_color=MUTED):
    rect(slide, x, y, w, h, fill=fill, radius=radius)
    if accent:
        rect(slide, x, y + 0.12, 0.06, h - 0.24, fill=accent, radius=0.03)
    pad = 0.3 if accent else 0.22
    ty = y + 0.16
    title_x = x + pad
    if icon and os.path.exists(icon):
        image(slide, icon, x + pad, ty, h=0.38)
        title_x = x + pad + 0.5
    if title:
        text(slide, title_x, ty - 0.02, w - (title_x - x) - 0.15, 0.5, title, size=title_size, bold=True, color=title_color)
    if body:
        text(slide, x + pad, ty + (0.48 if title else 0), w - pad - 0.15, h - (0.64 if title else 0.2), body,
             size=body_size, color=body_color, spacing=1.12)


def check(slide, x, y, ok=True, size=0.3, partial=False):
    fill = ORANGE if partial else (GREEN if ok else RED)
    oval(slide, x, y, size, size, fill=fill)
    glyph = "~" if partial else ("✓" if ok else "✕")
    text(slide, x - 0.05, y - 0.04, size + 0.1, size + 0.08, glyph, size=int(size * 40), color=WHITE, bold=True,
         align="c", anchor="m", font=FONT_B if partial else "Segoe UI Symbol")


def header(slide, kicker, title, kicker_color=ORANGE, title_size=30, y=0.42, w=12.3):
    text(slide, 0.55, y, w, 0.3, kicker.upper(), size=11, color=kicker_color, bold=True, font=FONT_H)
    text(slide, 0.55, y + 0.28, w, 0.9, title, size=title_size, color=WHITE, bold=True, font=FONT_H, spacing=1.0)


def footer(slide, n, total, label="MuleCatch · BuildX Hackathon 2026 · Banking and FinTech"):
    line(slide, 0.55, 7.02, 12.78, 7.02, color=LINE, width=0.75)
    text(slide, 0.55, 7.06, 9, 0.3, label, size=9, color=MUTED2)
    text(slide, 11.6, 7.06, 1.18, 0.3, f"{n:02d} / {total:02d}", size=9, color=MUTED2, align="r")


def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt


def big_number(slide, x, y, w, value, label, value_size=54, color=ORANGE, label_color=MUTED, label_size=13,
               align="l", source=None):
    text(slide, x, y, w, 0.95, value, size=value_size, color=color, bold=True, font=FONT_H, align=align, anchor="b")
    text(slide, x, y + 0.98, w, 0.85, label, size=label_size, color=label_color, align=align, spacing=1.1)
    if source:
        text(slide, x, y + 1.88, w, 0.3, source, size=9.5, color=MUTED2, align=align, italic=True)


def grid_table(slide, x, y, col_w, row_h, rows, header_fill=PURPLE, header_color=WHITE, body_fill=(CARD, CARD2),
               body_color=LAV, size=12, header_size=12, first_col_bold=True, highlight_row=None,
               highlight_fill="1F3B2A", cell_pad=0.08):
    """rows: list of lists. cell: str | list-of-runs | ('CHECK', True/False/'partial'[, caption])."""
    cy = y
    for ri, row in enumerate(rows):
        cx = x
        is_head = ri == 0
        rh = row_h[ri] if isinstance(row_h, list) else row_h
        if is_head:
            fill = header_fill
        elif highlight_row == ri:
            fill = highlight_fill
        else:
            fill = body_fill[(ri - 1) % 2]
        for ci, cell in enumerate(row):
            cw = col_w[ci]
            rect(slide, cx, cy, cw, rh, fill=fill)
            if isinstance(cell, tuple) and cell[0] == "CHECK":
                v = cell[1]
                s = 0.3
                cyy = cy + rh / 2 - s / 2 - (0.1 if len(cell) > 2 else 0)
                check(slide, cx + cw / 2 - s / 2, cyy, ok=(v is True), partial=(v == "partial"), size=s)
                if len(cell) > 2:
                    text(slide, cx, cyy + s + 0.02, cw, 0.3, cell[2], size=9, color=MUTED, align="c")
            else:
                bold = is_head or (first_col_bold and ci == 0)
                col = header_color if is_head else (WHITE if (ci == 0 or highlight_row == ri) else body_color)
                text(slide, cx + cell_pad, cy, cw - 2 * cell_pad, rh, cell, size=header_size if is_head else size,
                     color=col, bold=bold, anchor="m", spacing=1.05)
            cx += cw
        cy += rh
    return cy


def phone_frame(slide, x, y, w, h, screen_path=None, fill="0B0B1A", bezel=0.09):
    """Simple phone bezel with the screen image scaled inside it."""
    rect(slide, x, y, w, h, fill=fill, radius=0.45, line="4A4977", line_w=1.25)
    if screen_path and os.path.exists(screen_path):
        image(slide, screen_path, x + bezel, y + bezel, w=w - 2 * bezel, h=h - 2 * bezel)
    else:
        rect(slide, x + bezel, y + bezel, w - 2 * bezel, h - 2 * bezel, fill=NAVY2, radius=0.36)
    oval(slide, x + w / 2 - 0.05, y + bezel + 0.06, 0.1, 0.1, fill="1A1A2E")

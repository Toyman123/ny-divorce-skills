# Re-deriving coordinates

All coordinates are baked into `scripts/fill_divorce_forms.py` for the 51-page
packet effective 3/1/26. `PAGES` maps each form key to its 0-based page range.
If NYS revises a form, re-measure that form only and re-render every page.

## Text-layer forms (JD-2, JD-3, JD-4, RJI, UCS-111, notices)

PDF points, measured **top-down**. Pull labels, ruled lines and glyphs with pdfplumber:

```python
import pdfplumber
p = pdfplumber.open('assets/blank-packet.pdf').pages[n]
words = p.extract_words()                                   # labels: x0, x1, top
rules = [o for o in p.lines + p.rects if o['x1'] - o['x0'] > 20 and o['bottom'] - o['top'] < 3]
glyph_boxes = [c for c in p.chars if c['text'] in '❑□']     # JD-3 checkboxes are font glyphs
vector_boxes = [r for r in p.rects if 8 < r['x1'] - r['x0'] < 14]   # JD-4 checkboxes are 11.5 pt squares
underscores = [w for w in words if '___' in w['text']]       # JD-4 / RJI / notices: blanks are typed underscores
```

Placement helpers in `Sheet`:

| Helper | Use | Anchor |
|---|---|---|
| `r(page, x, rule_y, s)` | ruled line (JD-3) | baseline = rule y - 2 |
| `text(page, x, top, s)` | underscore blank or label line | baseline = top + 12 - 0.25*size (Arial 12 labels sit at top + 9.47) |
| `q(page, x0, top)` | JD-3 Wingdings ❑ | visible box x0+1..x0+8.6, top+0.8..top+8.6 |
| `b(page, x0, top, dy)` | Courier □ | visible box x0..x0+7, top+dy..top+dy+7; dy=2.6 on JD-3, **-3.3 on the Notice of Entry** |
| `mark(page, x0, top)` | JD-4 vector square | centred in the 11.5 pt rect |

**Glyph bounding boxes lie.** pdfplumber's `top` for a glyph is the font's
bbox, not the ink. The same □ character sits at top+2.6 on JD-3 and at top-3.3
on the Notice of Entry because the two fonts report different metrics. Measure
the ink once per font:

```python
import numpy as np, pypdfium2 as pdfium
S = 8
im = np.array(pdfium.PdfDocument(pdf)[n].render(scale=S).to_pil().convert('L')) < 128
sub = im[int((top-4)*S):int((top+12)*S), int((x0-4)*S):int((x0+10)*S)]
cols = np.where(sub.sum(0) >= sub.shape[0] * 0.25)[0]   # box sides
rows = np.where(sub.sum(1) >= sub.shape[1] * 0.25)[0]   # box top/bottom edges
```

The RJI (UD-13) party block's underscores have their baseline at top+6.0 (8 pt
font). Writing at the usual top+8 strikes the text through; it uses top+5.5.

## Scanned forms (Note of Issue, DOH-2168)

No text layer. Render at 200 dpi; `pdf_points = pixels * 0.36` (`SCALE`).

**DOH-2168's mediabox is offset** (origin -1.94, -1.50, size 615.9 x 795).
Pixel measurements start at the mediabox corner, so `Sheet.render` translates
the overlay by `(mediabox.left, mediabox.bottom)`. Without it every mark is
~2 pt high and right, enough to put names on top of the printed FIRST/LAST labels.

Education bubbles (boxes 18/22) are 18 boxes, left edges at 200 dpi:
`990 1022 1054 1086 1118 1150 1182 1215 1247 | 1312 1344 1378 1409 | 1467 1498 1532 1563 1595`
(00-08 elementary, 09-12 high school, 13-17 college).

## UCS-840M (scanned sideways)

The page has no `/Rotate`; the scan itself is turned 90 deg. Measure in the
**upright** view and draw rotated text:

```python
im = pdfium.PdfDocument(pdf)[42].render(scale=200/72).to_pil().rotate(90, expand=True)
```

PIL's `rotate(90)` is counter-clockwise, so an upright point (u, v) maps to the
page as `x = W - v`, `y_top = u` (points). `Sheet.rot_text(page, u, line_v, s)`
takes 200 dpi upright pixels of the **start of each underline** and draws with
`translate(W - v, H - u); rotate(-90)`.

The scan is skewed about 0.4 deg, so each line was located individually: start
from a rough position and snap to the nearest row with a long dark run under
the field. Gender circles: measure the ring's extent, not the mean of dark
pixels in a window. The label text drags the mean sideways (that put an X on
"Male" in the first draft).

## Verify

Render every filled page and look at it. Coordinate drift is invisible
otherwise:

```python
pdfium.PdfDocument(path)[n].render(scale=170/72).to_pil().save('check.png')
```

Run both `assets/case-template.json` and `assets/case-example-complex.json`:
between them they hit every branch.

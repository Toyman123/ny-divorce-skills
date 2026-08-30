# Re-deriving coordinates

## Text-layer forms (JD-5, JD-6)

```bash
python /mnt/skills/public/pdf/scripts/extract_form_structure.py form.pdf structure.json
```

Returns every text label with `page`, `x0`, `x1`, `top`, `bottom` in PDF points
measured **top-down** from the top of the page, plus any vector-drawn checkbox
rectangles.

- Entry text: `x` = the preceding label's `x1` + 2, `top` = that label's `top`,
  `bottom` = `top` + 12 (the body line height on these forms).
- JD-6 checkboxes are real vector rectangles and come back in `checkboxes`.
- JD-5 checkboxes are **text glyphs**, not rectangles - search the labels for
  `\u2751` (the ❑ used for top-level options) and `\u25a1` (the □ used for inline
  sub-options). They will not appear in `checkboxes`.
- Ruled writing lines don't show up as labels. Find them with pdfplumber:
  ```python
  [o for o in page.lines + page.rects if o['x1'] - o['x0'] > 100]
  ```
  Set the text baseline ~2 pt above the rule so it sits on the line rather than
  striking through it.

## Scanned forms (Note of Issue, DOH-2168)

No usable text layer. Render at 200 dpi and measure in pixels:

```python
import pypdfium2 as pdfium
pdfium.PdfDocument(pdf)[n].render(scale=200/72).to_pil().save('hi.png')
```

At 200 dpi, `pdf_points = pixels * 0.36`, which is what `SCALE` in the script does.

Measure numerically rather than by eye - cropping and guessing drifts by 5-10 px,
which is enough to land an X on the wrong checkbox:

```python
import numpy as np
from PIL import Image
im = np.array(Image.open('hi.png').convert('L')) < 128

# a ruled underline: the long horizontal dark run in a row band
[ (y, np.where(im[y])[0].min(), np.where(im[y])[0].max())
  for y in range(y0, y1) if im[y, x0:x1].sum() > 100 ]

# a checkbox square: vertical edges are columns with many dark pixels
[ x for x in range(x0, x1) if im[y0:y1, x].sum() > (y1 - y0) * 0.4 ]

# a row of checkboxes: take the box-top row and split it into runs
xs = np.where(im[top_row])[0]
```

Size the X to the box. These boxes are ~19 px at 200 dpi, about 7 pt, so a 6-6.5 pt
bold X fits; a 10 pt X spills over the edges.

## Rendering

Draw a real overlay and `merge_page` it - do not use `FreeText` annotations. Some
viewers and print drivers drop or reposition annotations, which is unacceptable on
a court filing.

Vertical placement: for left-aligned text, `baseline = page_height - (bottom - 0.25*size)`.
For an X centred in a checkbox, `baseline = page_height - (box_centre + 0.35*size)`.

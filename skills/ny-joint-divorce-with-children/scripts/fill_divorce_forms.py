#!/usr/bin/env python3
"""
Fill the NYS Uncontested Joint Divorce WITH CHILDREN forms packet (eff. 3/1/26).

    python fill_divorce_forms.py --case case.json --out <dir> [--forms ...] [--no-cssa]

Draws text onto the official blank PDF at measured coordinates (a real page
overlay merged with pypdf - not annotations, not form fields), one PDF per form.

Coordinate systems:
  * Text-layer forms (JD-2, JD-3, JD-4, RJI, UCS-111, notices): PDF points
    measured top-down. `r()` writes on a ruled line (y = the rule), `text()`
    writes at a label's top, `q()` / `b()` mark the JD-3 glyph checkboxes
    (Wingdings ❑ / Courier □) and `mark()` the JD-4 vector boxes.
  * Scanned forms (Note of Issue, DOH-2168): 200 dpi pixel boxes x SCALE.
  * UCS-840M is scanned SIDEWAYS on a portrait page: coordinates are 200 dpi
    pixels in the upright (rotated) view and text is drawn rotated -90 deg.

Never put Social Security numbers in the case file - those are handwritten.
Child-support figures come from cssa.py, never from the user as bare numbers.
"""
import argparse
import datetime as dt
import json
import os
import sys
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cssa  # noqa: E402

INK = Color(0, 0, 0)
FONT = 'Helvetica'
BOLD = 'Helvetica-Bold'
SCALE = 0.36          # 200 dpi pixels -> PDF points
LINE = 12.0           # body line height on the text-layer forms
CB = 11.5             # JD-4 checkbox side

# 0-based page ranges in the official 51-page packet
PAGES = {'jd2': (3, 5), 'jd3': (5, 22), 'jd4': (22, 40), 'noi': (40, 41), 'rji': (41, 42),
         'rji_addendum': (42, 43), 'doh': (43, 44), 'notify': (44, 45), 'ucs111': (45, 46),
         'entry': (47, 48), 'aff_judgment': (48, 49), 'aff_mail': (49, 50), 'aff_personal': (50, 51)}
DEFAULT_FORMS = 'jd2,jd3,jd4,noi,rji,rji_addendum,doh,ucs111'
FREQ = {'week': 0, 'two_weeks': 1, 'month': 2, 'other': 3}


# =========================================================================== Sheet
class Sheet:
    """Collects placements for one extracted form, then renders them."""

    def __init__(self):
        self.items = []          # (page, x, top, bottom, text, size, mode)
        self.extra_pages = []    # list of (title, [lines]) appended after the form

    # ---- text
    def text(self, page, x, top, s, size=10, height=LINE, width=None):
        if s in (None, ''):
            return
        s = str(s)
        if width:
            while size > 6 and stringWidth(s, FONT, size) > width:
                size -= 0.5
        self.items.append((page, x, top, top + height, s, size, 'left'))

    def r(self, page, x, rule_y, s, size=10, width=None):
        """Write on a ruled line whose y (top-down) is rule_y."""
        self.text(page, x, rule_y - 2 - LINE + 0.25 * size, s, size, width=width)

    def lines(self, page, x, rule_ys, s, size=10, width=400, first_width=None, first_x=None):
        """Wrap s across several ruled lines (first line may start further right)."""
        if not s:
            return
        rows, words, cur = [], str(s).split(), ''
        for w in words:
            lim = (first_width or width) if not rows else width
            t = (cur + ' ' + w).strip()
            if stringWidth(t, FONT, size) <= lim:
                cur = t
            else:
                rows.append(cur)
                cur = w
        rows.append(cur)
        if len(rows) > len(rule_ys):
            raise ValueError(f'text too long for {len(rule_ys)} lines on page {page}: {s[:60]}...')
        for i, (row, y) in enumerate(zip(rows, rule_ys)):
            self.r(page, first_x if (i == 0 and first_x) else x, y, row, size)

    # ---- checkboxes
    def mark(self, page, x0, top, x1=None, bot=None, size=9):
        x1 = x0 + CB if x1 is None else x1
        bot = top + CB if bot is None else bot
        self.items.append((page, (x0 + x1) / 2, top, bot, 'X', size, 'cbox'))

    def q(self, page, x0, top):
        """JD-3 Wingdings ❑ (12 pt): visible box ~ x0+1..x0+8.6, top+0.8..top+8.6"""
        self.items.append((page, x0 + 4.8, top + 0.8, top + 8.8, 'X', 8, 'cbox'))

    def b(self, page, x0, top, dy=2.6):
        """Courier □ (12 pt): visible box x0..x0+7, top+dy..top+dy+7. dy is 2.6 on JD-3;
        the Notice of Entry's font reports a different bbox and needs dy=-3.3 (measured)."""
        self.items.append((page, x0 + 3.5, top + dy, top + dy + 7, 'X', 6.5, 'cbox'))

    # ---- scanned forms
    def img_text(self, page, box, s, size=8):
        if s in (None, ''):
            return
        x0, t, x1, b = [v * SCALE for v in box]
        self.items.append((page, x0 + 1, t, b, str(s), size, 'left'))

    def img_mark(self, page, box, size=6):
        x0, t, x1, b = [v * SCALE for v in box]
        self.items.append((page, (x0 + x1) / 2, t, b, 'X', size, 'cbox'))

    def rot_text(self, page, u, line_v, s, size=8, width_px=None):
        """Sideways scan: u, line_v in 200 dpi px of the upright view; text sits on the line."""
        if s in (None, ''):
            return
        s = str(s)
        if width_px:
            while size > 5.5 and stringWidth(s, FONT, size) > width_px * SCALE:
                size -= 0.5
        self.items.append((page, u * SCALE, (line_v - 4) * SCALE, None, s, size, 'rot'))

    def rot_mark(self, page, u, v, size=7):
        self.items.append((page, u * SCALE, v * SCALE, None, 'X', size, 'rotc'))

    # ---- output
    def render(self, reader_pages, out_path):
        writer = PdfWriter()
        by_page = {}
        for it in self.items:
            by_page.setdefault(it[0], []).append(it)
        for i, page in enumerate(reader_pages, start=1):
            if i in by_page:
                w, h = float(page.mediabox.width), float(page.mediabox.height)
                ox, oy = float(page.mediabox.left), float(page.mediabox.bottom)
                buf = BytesIO()
                c = canvas.Canvas(buf, pagesize=(w, h))
                c.translate(ox, oy)          # pixel/point measurements start at the mediabox corner
                c.setFillColor(INK)
                for (_, x, top, bottom, s, size, mode) in by_page[i]:
                    c.setFont(BOLD if s == 'X' else FONT, size)
                    if mode == 'cbox':
                        c.drawCentredString(x, h - ((top + bottom) / 2 + 0.35 * size), s)
                    elif mode == 'left':
                        c.drawString(x, h - (bottom - 0.25 * size), s)
                    else:  # rotated: x=u (down the page), top=v (from the right edge)
                        c.saveState()
                        c.translate(w - top, h - x)
                        c.rotate(-90)
                        if mode == 'rot':
                            c.drawString(0, 0, s)
                        else:
                            c.drawCentredString(0, -0.35 * size, s)
                        c.restoreState()
                c.save()
                buf.seek(0)
                page.merge_page(PdfReader(buf).pages[0])
            writer.add_page(page)
        for title, rows in self.extra_pages:
            writer.add_page(PdfReader(attachment_page(title, rows)).pages[0])
        with open(out_path, 'wb') as fh:
            writer.write(fh)


def attachment_page(title, rows):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont(BOLD, 12)
    c.drawString(72, 720, title)
    c.setFont(FONT, 10)
    y = 696
    for row in rows:
        c.drawString(72, y, row)
        y -= 16
    c.save()
    buf.seek(0)
    return buf


def extract(src, key):
    a, b = PAGES[key]
    rd = PdfReader(src)
    return [rd.pages[i] for i in range(a, b)]


# =========================================================================== helpers
def full_name(p):
    return ' '.join(x for x in (p.get('first'), p.get('middle', ''), p.get('last')) if x).upper()


def money(v):
    if v in (None, ''):
        return ''
    try:
        v = float(str(v).replace('$', '').replace(',', ''))
    except ValueError:
        return str(v)          # already-formatted text: write it as given
    return f'{v:,.2f}'


def pct(v):
    return '' if v in (None, '') else f'{float(v):g}'


def address_lines(sp):
    """Two mailing lines: the attorney's if represented, else the spouse's own."""
    if sp['represented']:
        return sp['attorney_address_line1'], sp['attorney_address_line2']
    ap = sp.get('address_parts')
    if ap:
        return ap['street'].upper(), f"{ap['city']}, {ap.get('state', 'NY')} {ap.get('zip', '')}".upper().strip()
    parts = sp['address'].split(', ', 1)
    return parts[0], parts[1] if len(parts) > 1 else ''


def other(s):
    return 'spouse2' if s == 'spouse1' else 'spouse1'


def parse_date(s):
    return dt.datetime.strptime(s, '%m/%d/%Y').date()


def age_on(dob, ref):
    d = parse_date(dob)
    return ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))


def split_children(d):
    ref = parse_date(d['as_of']) if d.get('as_of') else dt.date.today()
    minors, adults = [], []
    for ch in d['children']:
        a = age_on(ch['dob'], ref)
        if a >= 21:
            raise SystemExit(f"{full_name(ch)} is {a} on {ref:%m/%d/%Y} - only children under 21 belong in "
                             'this packet. Remove them from "children".')
        (minors if a < 18 else adults).append(ch)
    return minors, adults


def uniform(values):
    values = [v for v in values if v]
    return values[0] if values and all(v == values[0] for v in values) else None


def has_support_order(d):
    return bool(d['child_support'].get('existing_order'))


def public_assistance(d):
    return (d['spouse1'].get('on_public_assistance') or d['spouse2'].get('on_public_assistance')
            or any(c.get('public_assistance') for c in d['children']))


def health_plans_none(d):
    return all(str(d[s].get('health_plan', '')).strip().upper() in ('', 'NONE') for s in ('spouse1', 'spouse2'))


# =========================================================================== JD-3 (17 pp)
U18_SLOT = [(6, 0.0, 442.0), (6, 182.9, 624.9), (7, -212.8, 230.0)]     # (page, dy, public-asst row)
A18_SLOT = [(7, 0.0), (7, 157.3), (8, -267.2)]


def build_jd3(d, r):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    cs = d['child_support']
    minors, adults = split_children(d)

    # p1 caption
    s.r(1, 96, 100.8, d['county'], 11)
    s.r(1, 428, 121.4, d['index_no'])
    s.r(1, 76, 136.0, full_name(s1), 11)
    s.r(1, 76, 198.0, full_name(s2), 11)
    s.r(1, 132, 239.3, s1.get('residence_state', 'NEW YORK'), width=125)
    s.r(1, 143, 264.5, s1['residence_county'], width=114)
    s.r(1, 143, 297.9, s2['residence_county'], width=114)

    # p2 residency, spouses, military
    res = d['residency']
    if res == 'two_years':
        s.q(2, 126.0, 140.4)
    elif res in ('one_year_married_ny', 'one_year_lived_ny'):
        s.q(2, 126.0, 180.0)
        s.q(2, 171.1, 213.6 if res == 'one_year_married_ny' else 233.5)
    elif res == 'one_year_breakdown_ny':
        s.q(2, 126.0, 273.1)
    elif res == 'both_in_ny':
        s.q(2, 126.0, 326.5)
    for sp, name_x, name_y, addr_y, pa_y in ((s1, 182, 390.8, 410.3, 450.6), (s2, 176, 502.3, 521.8, 562.2)):
        s.r(2, name_x, name_y, full_name(sp), width=335)
        s.r(2, 152, addr_y, sp['address'], width=383)
        s.b(2, 121.5 if sp.get('on_public_assistance') else 158.7, pa_y)
    mil = d.get('military', [])
    if not mil:
        s.q(2, 90.0, 603.2)
    else:
        s.q(2, 90.0, 623.0)
        if 'spouse1' in mil:
            s.b(2, 300.4, 622.8)
        if 'spouse2' in mil:
            s.b(2, 415.8, 622.8)

    # p3 marriage, health plans
    s.r(3, 222, 103.6, d['marriage_date'], width=132)
    s.r(3, 371, 103.6, d['marriage_place'], width=163)
    if d['ceremony'] == 'civil':
        s.q(3, 126.0, 138.2)
    else:
        s.q(3, 126.0, 158.0)
        s.q(3, 162.0, 205.4 if d.get('barriers') == 'taken' else 252.8)
    for pg, sp, ys in ((3, s1, (587.4, 607.2, 626.9, 646.7)), (4, s2, (84.0, 103.8, 123.5, 143.2))):
        for x, y, k in zip((290, 162, 269, 216), ys, ('health_plan', 'health_plan_address',
                                                       'health_plan_id', 'health_plan_admin')):
            s.r(pg, x, y, sp.get(k, ''), width=500 - x)

    # p4 income table - rows G/H come from cssa, never the user
    rows = {sp: cssa.income_rows(d['income'][sp]) for sp in ('spouse1', 'spouse2')}
    for k, top in zip('ABCDEFGH', (233.2, 258.9, 284.7, 310.4, 336.2, 373.5, 411.1, 436.9)):
        if k in 'BCDEF' and not any(str(d['income'][sp].get(k, '')).strip() for sp in rows):
            vals = ('0.00', '0.00')
        else:
            vals = (money(rows['spouse1'][k]), money(rows['spouse2'][k]))
        s.text(4, 356, top, vals[0], 10)
        s.text(4, 451, top, vals[1], 10)
    s.text(4, 367, 462.7, money(rows['spouse1']['H']), 10)
    s.text(4, 462, 462.7, money(rows['spouse2']['H']), 10)
    s.r(4, 163, 499.3, str(len(d['children'])))

    # p4-5 maintenance
    m = d.get('maintenance', {'type': 'none'})
    if m.get('type', 'none') == 'none':
        s.q(4, 72.0, 654.3)
    else:
        s.q(5, 72.0, 73.1)
        g = m.get('guideline', {})
        if g.get('payor'):
            s.b(5, 262.2 if g['payor'] == 'spouse1' else 350.9, 86.8)
        s.r(5, 368, 112.7, money(g.get('amount')))
        s.r(5, 240, 275.8, g.get('years_married', ''))
        for x, k in ((144, 'min_years'), (237, 'min_months'), (333, 'max_years'), (425, 'max_months')):
            s.r(5, x, 291.8, g.get(k, ''))
        recipient = other(m['payor'])
        if m['type'] == 'agreement':
            s.q(5, 90.0, 308.6)
            s.r(5, 259, 339.3, m.get('agreement_date', ''))
            s.b(5, 125.9 if recipient == 'spouse1' else 213.9, 348.0)
            s.r(5, 243, 380.0, money(m['amount']))
            s.r(5, 377, 380.0, m.get('day_of', ''))
            s.b(5, (126.0, 210.9, 323.5, 413.4)[FREQ[m['frequency']]], 382.7)
            if m['frequency'] == 'other':
                s.r(5, 129, 409.4, m.get('other_text', ''))
            s.r(5, 281, 426.9, m.get('duration_years', ''))
            s.r(5, 373, 426.9, m.get('duration_months', ''))
        else:  # in_form
            s.q(5, 90.0, 455.8)
            s.b(5, 125.9 if recipient == 'spouse1' else 214.1, 475.2)
            s.r(5, 243, 507.2, money(m['amount']))
            fx = {'week': (337.5, 496.1), 'two_weeks': (423.1, 496.1), 'month': (126.0, 511.0)}[m['frequency']]
            s.b(5, *fx)
            s.r(5, 320, 542.8, m.get('start', ''))
            s.r(5, 129, 556.8, m.get('end', ''))
            pm = {'direct': (242.1, 565.4), 'income_deduction': (371.6, 565.4), 'scu': (180.9, 580.3)}
            if m.get('payment_method') in pm:
                s.b(5, *pm[m['payment_method']])
    s.q(5, 90.0, 705.6)   # there are children of the spouses

    # p6-7 children under 18 with custody chart
    for ch, (pg, dy, pa) in zip(minors, U18_SLOT):
        s.r(pg, 139, 303.1 + dy, full_name(ch), width=218)
        s.r(pg, 171, 322.9 + dy, ch['dob'])
        s.r(pg, 150, 362.5 + dy, ch.get('address', ''), width=232)
        s.r(pg, 159, 413.6 + dy, ch.get('lives_with', ''), width=205)
        s.r(pg, 213, 433.3 + dy, ch.get('relationship', ''), width=152)
        s.b(pg, 279.9 if ch.get('public_assistance') else 324.4, pa)
        s.q(pg, 400.8, {'joint': 306.0, 'spouse1': 319.8, 'spouse2': 333.6}[ch['legal_custody']] + dy)
        s.q(pg, 400.8, {'joint': 373.3, 'spouse1': 400.9, 'spouse2': 414.7}[ch['physical_custody']] + dy)
    if len(minors) > 3:
        s.q(7, 76.7, 262.4)
        s.extra_pages.append(('JD-3 Attachment - Additional children under 18', [
            f"{full_name(c)}  DOB {c['dob']}  legal: {c['legal_custody']}  physical: {c['physical_custody']}"
            f"  lives with: {c.get('lives_with', '')}  public assistance: {'yes' if c.get('public_assistance') else 'no'}"
            for c in minors[3:]]))
    # p7-8 children 18-20
    for ch, (pg, dy) in zip(adults, A18_SLOT):
        s.r(pg, 121, 357.5 + dy, full_name(ch), width=278)
        s.r(pg, 153, 377.3 + dy, ch['dob'])
        s.r(pg, 82, 411.8 + dy, ch.get('address', ''), width=428)
        s.r(pg, 141, 442.4 + dy, ch.get('lives_with', ''), width=205)
        s.r(pg, 195, 462.1 + dy, ch.get('relationship', ''), width=150)
        s.b(pg, 260.9 if ch.get('public_assistance') else 303.3, 470.7 + dy)
    if len(adults) > 3:
        s.q(8, 81.3, 236.6)
        s.extra_pages.append(('JD-3 Attachment - Additional children aged 18-20', [
            f"{full_name(c)}  DOB {c['dob']}  lives with: {c.get('lives_with', '')}" for c in adults[3:]]))

    # p8 custody + parenting time (only meaningful with children under 18)
    cu = d.get('custody', {})
    if minors:
        t = cu.get('type')
        if t == 'order':
            s.q(8, 108.0, 310.1)
            s.r(8, 174, 368.5, cu.get('order_county', ''))
            s.r(8, 176, 388.1, cu.get('order_docket', ''))
            s.r(8, 168, 407.8, cu.get('order_date', ''))
        elif t == 'agreement':
            s.q(8, 108.0, 436.7)
            s.r(8, 129, 461.4, cu.get('agreement_date', ''))
        elif t == 'none':
            s.q(8, 108.0, 517.7)
        if cu.get('parenting_time') == 'attached':
            s.q(8, 108.0, 585.0)
        elif cu.get('parenting_time') == 'schedule':
            s.q(8, 108.0, 604.8)
            s.lines(8, 129, (636.0, 656.6, 677.4, 698.0), cu.get('parenting_time_schedule', ''), width=405)

    # p9 custodial parent, SCU, existing order
    cp = cs['custodial_parent']
    s.q(9, 126.0, 243.1 if cp == 'spouse1' else 262.9)
    scu = cs.get('scu', {})
    if scu.get('who'):
        s.b(9, {'spouse1': 287.6, 'spouse2': 370.0, 'both': 455.9}[scu['who']], 310.1)
    if scu.get('status'):
        s.q(9, 90.0, {'requesting': 338.9, 'applied': 394.1, 'receives': 408.0, 'declines': 421.8}[scu['status']])
    eo = cs.get('existing_order')
    if eo:
        s.q(9, 108.0, 502.8)
        s.b(9, *((436.4, 516.3) if eo['payor'] == 'spouse1' else (126.0, 531.0)))
        s.r(9, 242, 542.1, money(eo['amount']))
        s.b(9, *{'week': (322.9, 531.0), 'two_weeks': (404.9, 531.0), 'month': (126.0, 545.9)}[eo['frequency']])
        s.r(9, 192, 591.7, eo.get('county', ''))
        s.r(9, 194, 611.3, eo.get('docket', ''))
        s.r(9, 186, 630.7, eo.get('date', ''))
    else:
        s.q(9, 108.0, 674.0)
    return s


def build_jd3_full(d, r):
    """JD-3 with the support-agreement pages, background check, property, fees, verifications."""
    s = build_jd3(d, r)
    s1, s2 = d['spouse1'], d['spouse2']
    cs = d['child_support']
    minors, _ = split_children(d)

    if not has_support_order(d):
        # p10 agreement + amounts
        if cs.get('agreement') == 'separate':
            s.q(10, 126.0, 73.1)
            s.r(10, 224, 97.8, cs.get('agreement_date', ''))
        else:
            s.q(10, 126.0, 140.4)
        if r:
            s.b(10, 367.8 if r['higher_income'] == 'spouse1' else 452.4, 255.7)
            s.b(10, 380.0 if r['non_custodial'] == 'spouse1' else 464.9, 277.2)
            pt = cs.get('paid_to')
            if pt in ('spouse1', 'spouse2', 'other', 'scu'):
                s.q(10, 162.0, {'spouse1': 318.9, 'spouse2': 338.8, 'other': 358.5, 'scu': 392.1}[pt])
            if pt == 'other':
                s.r(10, 409, 369.4, cs.get('paid_to_other_name', ''), width=124)
            s.r(10, 425, 450.8, money(r['agreed_per_payment']))
            s.b(10, *{'week': (162.0, 454.5), 'two_weeks': (246.9, 454.5), 'month': (359.5, 454.5)}[r['frequency']])
            s.r(10, 336, 486.7, money(r['agreed_annual']))
            if r['over_cap']:
                s.q(10, 162.0, 549.7)
                s.b(10, 404.0 if r['over_cap_election'] == 'apply' else 463.9, 549.5)
            else:
                s.q(10, 162.0, 529.9)
            s.r(10, 171, 651.1, money(r['presumptive_annual']))
            # p11 use the Act / deviate
            if r['deviate']:
                s.q(11, 162.0, 126.6)
                s.lines(11, 183, (151.2, 171.7, 191.5, 211.3), cs['deviation_reason'], width=350,
                        first_x=342, first_width=192)
            else:
                s.q(11, 162.0, 106.8)
        s.q(11, 162.0, 255.2 if public_assistance(d) else 235.3)
        cc = cs.get('child_care', {})
        for sp, qy, pct_y, amt_y, fy in (('spouse1', 377.5, 388.4, 402.1, (391.0, 391.0, 405.9)),
                                         ('spouse2', 425.9, 436.8, 450.6, (439.5, 439.5, 454.4))):
            c = cc.get(sp)
            if c:
                s.q(11, 144.0, qy)
                s.r(11, 338, pct_y, pct(c.get('pct')))
                s.r(11, 228, amt_y, money(c.get('amount')))
                if c.get('frequency') in FREQ:
                    i = FREQ[c['frequency']]
                    s.b(11, (308.1, 389.5, 162.0)[i], fy[i])
        edu = cs.get('education', {})
        for sp, qy, slots in (('spouse1', 508.1, [(11, 539.6, 553.4), (11, 573.8, 587.6), (11, 608.1, 622.0)]),
                              ('spouse2', 630.8, [(11, 662.3, 676.2), (11, 696.6, 710.4), (12, 84.9, 98.8)])):
            items = edu.get(sp, [])
            if items:
                s.q(11, 144.0, qy)
            if len(items) > 3:
                raise SystemExit(f'JD-3 has room for 3 education items per spouse ({sp} has {len(items)})')
            for it, (pg, y, py) in zip(items, slots):
                s.r(pg, 200, y, it.get('for', ''), width=190)
                s.r(pg, 493, y, money(it.get('amount')), width=46)
                s.r(pg, 197, py, pct(it.get('pct')))
        # p12 health insurance
        h = cs.get('health', {})
        if h.get('covered_by'):
            s.q(12, 162.0, {'state': 182.1, 'spouse1': 229.5, 'spouse2': 249.4}[h['covered_by']])
        s.r(12, 348, 280.9, money(h.get('premium')))
        if h.get('premium_frequency') in FREQ:
            s.b(12, *[(428.8, 269.8), (162.0, 284.7), (271.1, 284.7)][FREQ[h['premium_frequency']]])
        s.r(12, 417, 317.3, pct(h.get('spouse1_pct')))
        s.r(12, 165, 344.9, pct(h.get('spouse2_pct')))
        un = h.get('unreimbursed', {})
        if un.get('spouse1_pct') not in (None, '', 0):
            s.q(12, 162.0, 388.2)
            s.r(12, 405, 399.1, pct(un['spouse1_pct']))
        if un.get('spouse2_pct') not in (None, '', 0):
            s.q(12, 162.0, 421.8)
            s.r(12, 405, 432.7, pct(un['spouse2_pct']))

    # p12-13 background check (children under 18 only)
    bg = d.get('background', {})
    if minors:
        ops = bg.get('orders_of_protection', [])
        if not ops:
            s.q(12, 108.0, 598.4)
        else:
            s.q(12, 108.0, 618.3)
            rows = [(12, 713.1), (13, 94.4), (13, 119.3)]     # bottom rule of each data row, -2
            if len(ops) > len(rows):
                raise SystemExit('more than 3 orders of protection - the form has 3 rows; attach a sheet')
            for op, (pg, y) in zip(ops, rows):
                for x, k, wd in ((111, 'against', 116), (233, 'county', 92), (331, 'court', 101), (437, 'docket', 101)):
                    s.r(pg, x, y, op.get(k, ''), 9, width=wd)
        if not bg.get('abuse_neglect'):
            s.q(13, 108.0, 177.0)
        else:
            s.q(13, 108.0, 210.6)
            s.lines(13, 129, (255.7, 275.5), bg['abuse_neglect'], width=405)
        so = bg.get('sex_offender', {})
        if not so:
            s.q(13, 108.0, 300.5)
        for sp, qy, y1, y2 in (('spouse1', 353.9, 396.0, 415.5), ('spouse2', 424.8, 467.0, 486.3)):
            if so.get(sp):
                s.q(13, 108.0, qy)
                s.r(13, 223, y1, so[sp].get('id', ''))
                s.r(13, 423, y1, so[sp].get('dob', ''))
                s.r(13, 255, y2, so[sp].get('names', ''), width=285)

    # p13 marital home
    mh = d.get('marital_home', 'not_applicable')
    if mh == 'not_applicable' or not mh:
        s.q(13, 81.0, 586.0)
    else:
        s.q(13, 81.0, 605.8)
        s.b(13, 215.1 if mh['occupant'] == 'spouse1' else 297.6, 605.6)
        s.r(13, 250, 633.5, mh['address'], width=283)
        if mh.get('until'):
            s.q(13, 108.0, 644.4)
            s.r(13, 154, 655.3, mh['until'], width=330)
        elif mh.get('as_follows'):
            s.q(13, 108.0, 664.2)
            s.r(13, 188, 675.1, mh['as_follows'], width=337)

    # p14 property, real estate, pensions, debt
    pr = d.get('property', '')
    if pr == 'divided':
        s.q(14, 90.0, 216.8)
    elif pr == 'separate_agreement':
        s.q(14, 90.0, 250.6)
    elif pr == 'in_form':
        s.q(14, 90.0, 270.4)
        s.lines(14, 111, (295.6, 315.4, 335.2), d.get('property_text', ''), width=422, size=9)
    re_ = d.get('real_estate', 'not_applicable')
    if re_ == 'not_applicable' or not re_:
        s.q(14, 90.0, 386.1)
    else:
        s.q(14, 90.0, 405.9 if re_['from'] == 'spouse1' else 473.2)
        s.r(14, 222, 464.2 if re_['from'] == 'spouse1' else 531.4, re_['address'], width=312)
    pen = d.get('pensions', '')
    if pen:
        s.q(14, 90.0, {'qdro': 574.0, 'separate_agreement': 607.6, 'waive': 627.4}[pen])
    debt = d.get('debt', '')
    if debt == 'not_applicable':
        s.q(14, 90.0, 667.0)
    elif debt == 'separate_agreement':
        s.q(14, 90.0, 686.8)
    elif debt == 'in_form':
        s.q(15, 90.0, 73.1)
        s.lines(15, 111, (98.5, 118.3, 138.1), d.get('debt_text', ''), width=422, size=9)

    # p15 name change, fees
    if s1.get('former_last_name'):
        s.q(15, 90.0, 204.2)
        s.r(15, 212, 234.9, s1['former_last_name'])
    if s2.get('former_last_name'):
        s.q(15, 90.0, 243.8)
        s.r(15, 212, 274.5, s2['former_last_name'])
    fees = d.get('fees', 'each_own')
    if fees == 'each_own':
        s.q(15, 90.0, 373.8)
    elif isinstance(fees, dict):
        s.q(15, 90.0, 393.7)
        s.b(15, 224.8 if fees['payor'] == 'spouse1' else 318.3, 393.5)
        s.r(15, 440, 404.6, money(fees.get('amount')))
        s.lines(15, 111, (437.0, 459.6), fees.get('experts', ''), width=422, first_x=170, first_width=365)

    # p16-17 printed names only - no dates, no signatures, no notary
    s.r(16, 225, 176.1, full_name(s1), width=158)
    s.r(16, 381, 482.8, full_name(s1), 9, width=148)
    s.r(17, 221, 107.3, full_name(s2), width=241)
    s.r(17, 385, 335.8, full_name(s2), 9, width=149)
    return s


# =========================================================================== JD-4 (18 pp)
JD4_CHILD_TOPS = (130.0, 204.2, 278.2, 352.4, 426.4, 500.6)


def build_jd4(d, r):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    cs = d['child_support']
    minors, adults = split_children(d)

    # p1 caption (date / judge / calendar no. are the court's)
    s.text(1, 396, 87.6, d['county'], 10, width=95)
    s.text(1, 426, 178.7, d['index_no'], 10)
    s.text(1, 74, 205.2, full_name(s1), 11, width=230)
    s.text(1, 74, 290.3, full_name(s2), 11, width=230)
    for sp, top in ((s1, 386.9), (s2, 407.7)):
        s.mark(1, 191.2 if sp['represented'] else 383.1, top)
    s.text(1, 92, 595.2, d['date_summons_filed'], 10)

    # p2
    s.text(2, 213, 170.4, s1['address'], 9, width=303)
    s.text(2, 213, 211.8, s2['address'], 9, width=303)
    res = d['residency']
    s.mark(2, 91.1, {'two_years': 273.3, 'one_year_married_ny': 314.7, 'one_year_lived_ny': 314.7,
                     'one_year_breakdown_ny': 376.9, 'both_in_ny': 418.2}[res])
    mil = d.get('military', [])
    if not mil:
        s.mark(2, 91.1, 521.7)
    else:
        s.mark(2, 91.1, 563.1)
        if 'spouse1' in mil:
            s.mark(2, 346.6, 563.1)
        if 'spouse2' in mil:
            s.mark(2, 468.6, 563.1)
    s.text(2, 225, 605.2, d['marriage_date'], 10, width=97)
    s.text(2, 341, 605.2, d['marriage_place'], 10, width=194)
    s.mark(2, 109.1, 656.3 if d['ceremony'] == 'civil' else 677.0)

    # p3 barriers, health plans
    if d['ceremony'] != 'civil':
        s.mark(3, 145.1, 73.2 if d.get('barriers') == 'taken' else 135.3)
    if health_plans_none(d):
        s.mark(3, 91.1, 259.2)
    else:
        s.mark(3, 91.1, 300.7)
        for sp, ys in ((s1, (342.7, 362.5, 382.3, 402.1)), (s2, (421.9, 441.7, 461.5, 481.3))):
            for x, y, k in zip((289, 161, 268, 215), ys, ('health_plan', 'health_plan_address',
                                                           'health_plan_id', 'health_plan_admin')):
                s.text(3, x, y, sp.get(k, ''), 9, width=498 - x)

    # p4 maintenance, children categories
    m = d.get('maintenance', {'type': 'none'})
    if m.get('type', 'none') == 'none':
        s.mark(4, 91.1, 135.9)
        s.mark(4, 127.1, 156.6)
    else:
        s.mark(4, 91.1, 239.4)
        if m['type'] == 'agreement':
            s.mark(4, 133.8, 260.1)
            s.text(4, 352, 260.7, m.get('agreement_date', ''), 10)
        else:
            s.mark(4, 267.3, 239.4)
        s.mark(4, 145.1 if m['payor'] == 'spouse1' else 240.3, 281.7)
        s.mark(4, *((446.2, 281.7) if other(m['payor']) == 'spouse1' else (145.1, 302.3)))
        s.text(4, 262, 324.5, money(m['amount']), 10)
        s.mark(4, *[(350.6, 323.9), (435.1, 323.9), (145.1, 344.6), (238.2, 344.6)][FREQ[m['frequency']]])
        if m['frequency'] == 'other':
            s.text(4, 272, 345.2, m.get('other_text', ''), 9, width=118)
    if minors:
        s.mark(4, 91.1, 572.7)
    if adults:
        s.mark(4, 91.1, 593.5)

    # p5 all children under 21 (SSN left blank)
    kids = d['children']
    if len(kids) > 6:
        s.extra_pages.append(('JD-4 Attachment - Additional children under 21', [
            f"{full_name(c)}  DOB {c['dob']}  {c.get('address', '')}" for c in kids[6:]]))
    for ch, top in zip(kids, JD4_CHILD_TOPS):
        s.text(5, 120, top, full_name(ch), 10, width=322)
        s.text(5, 368, top + 20.8, ch['dob'], 10)
        s.text(5, 131, top + 41.4, ch.get('address', ''), 9, width=395)
    bg = d.get('background', {})
    if not bg.get('orders_of_protection') and not bg.get('abuse_neglect'):
        s.mark(5, 91.1, 609.7)

    # p6 custody/visitation (para 16), custodial parent (17), support order or agreement (18)
    cu = d.get('custody', {})
    if not minors:
        s.mark(6, 91.1, 197.4)
    elif cu.get('type') == 'order':
        s.mark(6, 91.1, 238.8)
        s.mark(6, 165.7, 238.8)
        if cu.get('parenting_time') != 'schedule':
            s.mark(6, 230.9, 238.8)
        s.text(6, 123, 260.1, cu.get('order_county', ''), 10, width=168)
        s.text(6, 374, 260.1, cu.get('order_date', ''), 10)
        s.text(6, 205, 280.9, cu.get('order_docket', ''), 10)
    else:
        s.mark(6, 91.1, 321.7)
        s.mark(6, 169.1, 321.7)
        s.mark(6, 234.3, 321.7)
        if cu.get('type') == 'agreement':
            s.mark(6, 215.2, 342.3)
            s.text(6, 437, 342.9, cu.get('agreement_date', ''), 10)
        else:
            s.mark(6, 384.9, 321.7)
    s.mark(6, *((472.1, 363.1) if cs['custodial_parent'] == 'spouse1' else (111.7, 383.7)))
    eo = cs.get('existing_order')
    if eo:
        s.mark(6, 91.1, 425.1)
        s.text(6, 110, 446.5, eo.get('county', ''), 10, width=136)
        s.text(6, 392, 446.5, eo.get('docket', ''), 10)
        s.text(6, 143, 467.1, eo.get('date', ''), 10)
        s.mark(6, 319.2 if eo['payor'] == 'spouse1' else 414.6, 466.5)
        s.text(6, 116, 487.9, money(eo['amount']), 10)
        s.mark(6, {'week': 205.8, 'two_weeks': 293.7, 'month': 409.6}[eo['frequency']], 487.3)
    else:
        s.mark(6, 91.1, 549.3)
        if cs.get('agreement') == 'separate':
            s.mark(6, 191.8, 570.1)
            s.text(6, 364, 570.7, cs.get('agreement_date', ''), 10)
        else:
            s.mark(6, 313.0, 549.3)

    if r and not eo:
        # p7 CSSA derivation
        s.text(7, 433, 262.6, money(r['adjusted']['spouse1']), 10)
        s.text(7, 433, 284.1, money(r['adjusted']['spouse2']), 10)
        s.text(7, 425, 305.6, money(r['combined']), 10)
        s.q(7, 216.1, (347.8, 368.4, 389.1, 409.8, 430.6)[min(r['n_children'], 5) - 1])
        s.text(7, 206, 472.8, money(r['combined_obligation']), 10)
        s.text(7, 200, 515.0, f"{r['share_pct']['spouse1']:.2f}", 10)
        s.text(7, 437, 515.0, f"{r['share_pct']['spouse2']:.2f}", 10)
        s.text(7, 470, 557.2, money(r['ncp_capped']), 10)
        s.text(7, 273, 640.1, money(r['presumptive_per_payment']), 10)
        s.mark(7, *[(406.8, 639.5), (163.1, 660.1), (275.7, 660.1)][FREQ[r['frequency']]])
        if r['over_cap']:
            s.mark(7, 322.0 if r['over_cap_election'] == 'apply' else 377.8, 680.9)
            s.text(8, 398, 94.5, money(r['ncp_over_cap']), 10)
        # p8 meets / deviates, agreed amount, payee, public assistance
        if r['deviate']:
            s.mark(8, 163.1, 156.0)
            s.lines(8, 182, (188.8, 209.5, 230.2, 250.9), cs['deviation_reason'], width=350,
                    first_x=373, first_width=160)
            s.lines(8, 182, (292.4, 313.0, 333.8, 354.4), cs.get('court_deviation_reason', ''), width=350,
                    first_x=281, first_width=250)
        else:
            s.mark(8, 163.1, 135.3)
        s.mark(8, 214.5 if r['non_custodial'] == 'spouse1' else 306.4, 384.5)
        s.text(8, 134, 405.9, money(r['agreed_per_payment']), 10)
        s.mark(8, (237.3, 321.8, 437.6)[FREQ[r['frequency']]], 405.3)
    pt = cs.get('paid_to')
    if pt:
        s.mark(8, *{'spouse1': (358.0, 488.0), 'spouse2': (91.1, 508.8), 'other': (237.7, 508.8),
                    'scu': (358.8, 529.4)}[pt])
        if pt == 'other':
            s.text(8, 92, 530.0, cs.get('paid_to_other_name', ''), 10, width=200)
    s.mark(8, 109.1, 633.0 if public_assistance(d) else 612.2)

    # p9 income deduction order (21), marital property (22)
    idd = cs.get('income_deduction')
    if idd:
        s.mark(9, 109.1, {'issue': 156.0, 'alternative': 197.4, 'good_cause': 259.5}[idd])
        if idd == 'good_cause':
            s.lines(9, 128, (313.0, 333.8, 354.4), cs.get('good_cause_reason', ''), width=410,
                    first_x=329, first_width=203)
    pr = d.get('property', '')
    if pr == 'divided':
        s.mark(9, 91.1, 405.1)
    elif pr in ('separate_agreement', 'in_form'):
        s.mark(9, 91.1, 425.7)
        s.mark(9, *((191.8, 446.5) if pr == 'separate_agreement' else (305.9, 425.7)))

    # p11 SCU notice
    s.mark(11, 91.1, 389.2 if pt == 'scu' else 410.0)

    # p12 judgment para 2 maintenance
    if m.get('type', 'none') == 'none':
        s.mark(12, 91.1, 478.3)
    else:
        s.mark(12, 91.1, 498.9)
        s.mark(12, 127.1 if m['payor'] == 'spouse1' else 222.3, 520.5)
        s.mark(12, *((421.8, 520.5) if other(m['payor']) == 'spouse1' else (127.1, 541.1)))
        s.text(12, 243, 563.4, money(m['amount']), 10)
        s.mark(12, *[(326.0, 562.8), (410.5, 562.8), (127.1, 583.4), (217.0, 583.4)][FREQ[m['frequency']]])
        if m['frequency'] == 'other':
            s.text(12, 272, 584.0, m.get('other_text', ''), 9, width=118)

    # p13 judgment paras 3 (legal custody), 4 (visitation), 5 (child support)
    if minors:
        if cu.get('type') == 'order':
            s.mark(13, 91.1, 73.2)
            s.text(13, 408, 73.8, cu.get('order_county', ''), 10, width=125)
            s.text(13, 237, 94.5, cu.get('order_docket', ''), 10)
        else:
            s.mark(13, 91.1, 135.3)
            lc = uniform([c['legal_custody'] for c in minors])
            if lc:
                s.mark(13, 109.1, {'joint': 176.7, 'spouse1': 218.1, 'spouse2': 259.5}[lc])
                s.mark(13, 245.9 if lc == 'joint' else 290.6, {'joint': 176.7, 'spouse1': 218.1,
                                                                 'spouse2': 259.5}[lc])
        if cu.get('type') == 'order' and cu.get('parenting_time') != 'schedule':
            s.mark(13, 91.1, 300.9)
            s.text(13, 413, 301.5, cu.get('order_county', ''), 10, width=124)
            s.text(13, 237, 322.3, cu.get('order_docket', ''), 10)
        elif cu.get('parenting_time') == 'schedule':
            s.mark(13, 91.1, 363.1)
            if cu.get('visitation_parent'):
                s.mark(13, 221.2 if cu['visitation_parent'] == 'spouse1' else 316.4, 383.7)
            s.lines(13, 110, (437.2, 458.0, 478.6), cu.get('parenting_time_schedule', ''), width=422)
    if eo:
        s.mark(13, 91.1, 487.3)
        s.text(13, 110, 508.5, eo.get('county', ''), 10, width=163)
        s.text(13, 408, 508.5, eo.get('docket', ''), 10)
    elif r:
        s.mark(13, 91.1, 570.1)
        s.mark(13, 127.1 if r['non_custodial'] == 'spouse1' else 218.9, 591.6)
        s.text(13, 436, 592.2, money(r['agreed_per_payment']), 10)
        s.mark(13, (127.1, 211.6, 327.4)[FREQ[r['frequency']]], 612.2)
        if pt:
            s.mark(13, *{'spouse1': (272.0, 654.5), 'spouse2': (418.5, 654.5), 'other': (144.4, 675.2),
                         'scu': (144.4, 695.9)}[pt])
            if pt == 'other':
                s.text(13, 300, 675.8, cs.get('paid_to_other_name', ''), 9, width=205)

    if not eo:
        # p14 child care, education, health insurance
        cc = cs.get('child_care', {})
        for sp, top in (('spouse1', 136.1), ('spouse2', 177.5)):
            c = cc.get(sp)
            if c:
                s.mark(14, 127.1, top)
                s.text(14, 319, top + 0.6, pct(c.get('pct')), 10)
                s.text(14, 165, top + 21.4, money(c.get('amount')), 10)
                if c.get('frequency') in FREQ:
                    s.mark(14, (248.6, 333.1, 449.0)[FREQ[c['frequency']]], top + 20.8)
        edu = cs.get('education', {})
        for sp, top, rows in (('spouse1', 240.4, ((262.6, 283.3), (304.9, 325.5), (347.0, 367.6))),
                              ('spouse2', 387.8, ((409.9, 430.6), (452.1, 472.8), (494.4, 515.0)))):
            items = edu.get(sp, [])
            if items:
                s.mark(14, 127.1, top)
            for it, (y, py) in zip(items, rows):
                s.text(14, 172, y, it.get('for', ''), 9, width=210)
                s.text(14, 486, y, money(it.get('amount')), 9, width=48)
                s.text(14, 169, py, pct(it.get('pct')), 10)
        h = cs.get('health', {})
        if h.get('covered_by'):
            s.mark(14, 163.1, {'state': 599.6, 'spouse1': 641.0, 'spouse2': 661.8}[h['covered_by']])
        s.text(14, 329, 683.9, money(h.get('premium')), 10)
        if h.get('premium_frequency') in FREQ:
            s.mark(14, *[(415.9, 683.3), (145.1, 703.9), (260.9, 703.9)][FREQ[h['premium_frequency']]])
        # p15
        s.text(15, 243, 74.7, pct(h.get('spouse1_pct')), 10)
        s.text(15, 243, 95.3, pct(h.get('spouse2_pct')), 10)
        un = h.get('unreimbursed', {})
        if un.get('spouse1_pct') not in (None, '', 0):
            s.mark(15, 145.1, 304.1)
            s.text(15, 386, 304.7, pct(un['spouse1_pct']), 10)
        if un.get('spouse2_pct') not in (None, '', 0):
            s.mark(15, 145.1, 324.9)
            s.text(15, 386, 325.5, pct(un['spouse2_pct']), 10)
        if r:
            s.mark(15, 109.1, 490.5 if r['deviate'] else 428.4)
        if h.get('qmcso'):
            s.mark(15, 91.1, 656.1)
    if idd:
        s.mark(15, 109.1, 573.3 if idd == 'issue' else 614.7)

    # p16 marital home (9), real estate (10), QDRO (11), settlement agreement (12)
    mh = d.get('marital_home', 'not_applicable')
    if isinstance(mh, dict):
        s.mark(16, 91.1, 73.2)
        s.mark(16, 344.6 if mh['occupant'] == 'spouse1' else 436.5, 73.2)
        s.text(16, 110, 115.2, mh['address'], 10, width=423)
        if mh.get('until'):
            s.mark(16, 109.1, 135.3)
            s.text(16, 153, 135.9, mh['until'], 10, width=356)
        elif mh.get('as_follows'):
            s.mark(16, 109.1, 156.0)
            s.text(16, 187, 156.6, mh['as_follows'], 10, width=346)
    re_ = d.get('real_estate', 'not_applicable')
    if isinstance(re_, dict):
        s.mark(16, 91.1, 176.7)
        s.mark(16, 245.2 if other(re_['from']) == 'spouse1' else 337.1, 197.4)
        s.text(16, 165, 280.9, re_['address'], 10, width=366)
        s.text(16, 180, 301.5, re_.get('by_date', ''), 10, width=219)
    if d.get('pensions') == 'qdro':
        s.mark(16, 91.1, 342.3)
    sa = d.get('settlement_agreement')
    if sa:
        s.mark(16, 91.1, 445.9)
        s.mark(16, 358.8, 466.5)
        s.text(16, 110, 467.1, sa.get('day', ''), 10)
        s.text(16, 233, 467.1, sa.get('month_year', ''), 10, width=116)
    else:
        s.mark(16, 91.1, 404.5)

    # p17 who serves the judgment (17); p18 former names (18) - judge signs, nothing else
    s.mark(17, 91.1 if d['serves_judgment'] == 'spouse1' else 176.3, 611.5)
    if s1.get('former_last_name'):
        s.mark(18, 91.1, 73.2)
        s.text(18, 385, 73.8, s1['former_last_name'], 10)
    if s2.get('former_last_name'):
        s.mark(18, 91.1, 93.9)
        s.text(18, 385, 94.5, s2['former_last_name'], 10)
    return s


# =========================================================================== shared forms
# (pages identical to the no-children packet - coordinates carried over unchanged)
JD2_RELIEF = {
    'none': 89.6, 'maintenance_waived': 137.2, 'property_waived': 153.1,
    'property': 184.9, 'maintenance': 200.7, 'retirement': 216.6, 'child_support': 232.4,
    'custody': 264.2, 'visitation': 280.1, 'fees': 295.9, 'former_name': 311.9,
    'order_of_protection': 327.7, 'marital_home': 343.5, 'court_orders': 359.4, 'other': 375.3,
}


def build_jd2(d, r=None):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    s.text(1, 428, 76.7, d['index_no'], 10)
    s.text(1, 150, 90.5, d['county'], 11)
    s.text(1, 472, 96.5, d['date_summons_filed'], 9)
    s.text(1, 368, 130.1, d['county'], 9)
    s.text(1, 74, 135.2, full_name(s1), 11)
    s.text(1, 74, 197.2, full_name(s2), 11)
    s.text(1, 76, 556.5, d['county'], 10)
    for top, sp in ((584.1, s1), (597.9, s2)):
        if sp['residence_county'].strip().upper() == d['county'].strip().upper():
            s.mark(1, 90, top, x1=101, bot=top + 12)
            s.text(1, 279, top, sp['address'], 9, width=290)
    for key in d.get('ancillary_relief', []):
        top = JD2_RELIEF[key]
        s.mark(2, 90, top, x1=101, bot=top + 12)
    for sp, a, b, ph, nm, l1, l2 in ((s1, 444.0, 458.9, 476.1, 503.7, 519.7, 535.5),
                                     (s2, 604.3, 619.2, 636.4, 664.0, 679.8, 695.6)):
        top = b if sp['represented'] else a
        s.mark(2, 360, top, x1=367, bot=top + 12, size=8)
        s.text(2, 432, ph, sp['attorney_phone'] if sp['represented'] else sp['phone'], 9)
        s.text(2, 362, nm, sp['attorney_name'] if sp['represented'] else full_name(sp), 9)
        a1, a2 = address_lines(sp)
        s.text(2, 362, l1, a1, 9, width=190)
        s.text(2, 362, l2, a2, 9, width=190)
    return s


def build_noi(d, r=None):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    s.img_text(1, [560, 566, 765, 592], d['county'], 11)
    s.img_text(1, [360, 655, 950, 686], full_name(s1), 11)
    s.img_text(1, [360, 855, 950, 886], full_name(s2), 11)
    s.img_text(1, [1275, 655, 1660, 686], d['index_no'], 11)
    filed = {'plaintiff': [688, 1065, 705, 1086], 'plaintiff_attorney': [803, 1065, 820, 1086],
             'defendant': [1042, 1065, 1059, 1086]}
    s.img_mark(1, filed[d['note_of_issue_filed_by']], 6.5)
    s.img_text(1, [1180, 1150, 1700, 1180], d['date_summons_filed'], 10)
    s.img_text(1, [1200, 1225, 1700, 1255], d['date_summons_served'], 10)
    joined = {'waiver': [1000, 1298, 1018, 1319], 'default': [1180, 1298, 1198, 1319]}
    s.img_mark(1, joined[d['issue_joined']], 6.5)
    for sp, dy in ((s1, 0), (s2, 261)):
        s.img_mark(1, [615, 1529 + dy, 634, 1551 + dy] if sp['represented'] else [356, 1529 + dy, 374, 1551 + dy], 6.5)
        who = sp['attorney_name'] + ', ESQ.' if sp['represented'] else full_name(sp)
        s.img_text(1, [700, 1562 + dy, 1500, 1590 + dy], who, 10)
        if sp['represented']:
            l1, l2 = sp['attorney_address_line1'], sp['attorney_address_line2']
        else:
            parts = sp['address'].split(', ', 1)
            l1, l2 = parts[0], parts[1] if len(parts) > 1 else ''
        s.img_text(1, [358, 1594 + dy, 1200, 1620 + dy], l1, 10)
        s.img_text(1, [358, 1622 + dy, 1200, 1648 + dy], l2, 10)
        s.img_text(1, [538, 1662 + dy, 1000, 1690 + dy], sp['attorney_phone'] if sp['represented'] else sp['phone'], 10)
        if dy == 0:
            s.img_text(1, [538, 1690, 1000, 1718], sp.get('attorney_fax', ''), 10)
    return s


# DOH-2168 box 24/25 education bubble row: total years of schooling 00-17 (left edge, 200 dpi px)
DOH_EDU = dict(zip(range(18), (990, 1022, 1054, 1086, 1118, 1150, 1182, 1215, 1247,
                                1312, 1344, 1378, 1409, 1467, 1498, 1532, 1563, 1595)))


def build_doh(d, r=None):
    s = Sheet()
    for sp, dy in ((d['spouse1'], 0), (d['spouse2'], 296)):
        s.img_text(1, [380, 352 + dy, 592, 378 + dy], sp['first'].upper(), 9)
        s.img_text(1, [600, 352 + dy, 812, 378 + dy], sp.get('middle', '').upper(), 9)
        s.img_text(1, [820, 352 + dy, 982, 378 + dy], sp['last'].upper(), 9)
        s.img_text(1, [995, 352 + dy, 1250, 378 + dy], sp.get('birth_name', '').upper(), 9)
        s.img_text(1, [212, 438 + dy, 252, 470 + dy], sp['dob_month'], 9)
        s.img_text(1, [260, 438 + dy, 306, 470 + dy], sp['dob_day'], 9)
        s.img_text(1, [316, 438 + dy, 406, 470 + dy], sp['dob_year'], 9)
        s.img_text(1, [424, 436 + dy, 636, 470 + dy], sp['birth_state'], 9)
        s.img_text(1, [652, 436 + dy, 752, 470 + dy], sp.get('sex', ''), 9)
        s.img_text(1, [768, 436 + dy, 982, 470 + dy], sp['residence_state'], 9)
        s.img_text(1, [1000, 436 + dy, 1222, 470 + dy], sp['residence_county'], 9)
        loc_y = {'CITY': 419, 'TOWN': 439, 'VILLAGE': 460}[sp['locality_type']]
        s.img_mark(1, [1250, loc_y + dy, 1267, loc_y + 14 + dy])
        s.img_text(1, [1332, loc_y + 1 + dy, 1670, loc_y + 19 + dy], sp['locality_name'], 8)
        s.img_text(1, [214, 506 + dy, 982, 542 + dy], sp['address_short'], 9)
        yn = [1032, 526 + dy, 1055, 547 + dy] if sp['within_limits'] == 'YES' else [1110, 526 + dy, 1133, 547 + dy]
        s.img_mark(1, yn)
        s.img_text(1, [1358, 524 + dy, 1670, 546 + dy], sp.get('if_no_town', ''), 8)
        s.img_text(1, [240, 574 + dy + (10 if dy else 0), 940, 606 + dy + (10 if dy else 0)],
                   sp['attorney_name'] or 'NONE - UNREPRESENTED', 9)
        s.img_text(1, [995, 580 + dy + (4 if dy else 0), 1670, 612 + dy + (4 if dy else 0)],
                   sp['attorney_address_short'] or sp['address_short'], 8)

    s.img_text(1, [214, 950, 706, 988], d['marriage_city'], 9)
    s.img_text(1, [722, 950, 1196, 988], d['marriage_county'], 9)
    s.img_text(1, [1212, 950, 1670, 988], d['marriage_state'], 9)
    s.img_text(1, [328, 1030, 388, 1068], d['marriage_date_month'], 9)
    s.img_text(1, [398, 1030, 450, 1068], d['marriage_date_day'], 9)
    s.img_text(1, [460, 1030, 524, 1068], d['marriage_date_year'], 9)
    s.img_text(1, [716, 1030, 776, 1068], d['separated_month'], 9)
    s.img_text(1, [786, 1030, 864, 1068], d['separated_year'], 9)
    minors, _ = split_children(d)
    s.img_text(1, [882, 1040, 1246, 1076], str(d.get('children_born', len(d['children']))), 10)
    s.img_text(1, [1262, 1040, 1670, 1076], str(len(minors)), 10)

    # boxes 15/19 (race) are never filled
    for sp, dy in ((d['spouse1'], 0), (d['spouse2'], 162)):
        s.img_text(1, [424, 1512 + dy, 634, 1540 + dy], sp['marriage_number'], 9)
        if sp['prior_ended_death'] == 'NONE':
            s.img_mark(1, [722, 1562 + dy + (5 if dy else 0), 743, 1581 + dy + (5 if dy else 0)])
        if sp['prior_ended_divorce'] == 'NONE':
            s.img_mark(1, [876, 1562 + dy + (5 if dy else 0), 898, 1581 + dy + (5 if dy else 0)])
        if sp.get('education_box') not in (None, ''):
            ex = DOH_EDU[int(sp['education_box'])]
            s.img_mark(1, [ex, 1508 + dy + (2 if dy else 0), ex + 23, 1531 + dy + (2 if dy else 0)])

    s.img_text(1, [178, 1782, 642, 1810], full_name(d['spouse1']), 9)
    s.img_text(1, [656, 1782, 1146, 1810], d['decree_granted_to'], 9)
    s.img_text(1, [1162, 1782, 1666, 1810], d['legal_grounds'], 8)
    s.img_text(1, [250, 1872, 1150, 1902], d.get('preparer_name', ''), 10)
    return s


def build_rji(d, r=None):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    minors, _ = split_children(d)
    s.text(1, 176, 66.2, 'SUPREME', 8, height=10)
    s.text(1, 336, 66.2, d['county'], 8, height=10)
    s.text(1, 180, 85.2, d['index_no'], 8, height=10)
    s.text(1, 25, 128, full_name(s1), 9, height=10)
    s.text(1, 25, 178, full_name(s2), 9, height=10)

    def yes_no(flag, top):
        s.mark(1, 263 if flag else 292, top, x1=271 if flag else 300, bot=top + 8, size=6)
    yes_no(bool(d['date_summons_filed']), 228.3)
    s.text(1, 390, 228.3, d['date_summons_filed'], 7, height=9)
    yes_no(bool(d['date_summons_served']), 240.7)
    s.text(1, 390, 241.6, d['date_summons_served'], 7, height=9)
    yes_no(bool(minors), 253.2)                           # children under 18 -> attach UCS-840M
    s.mark(1, 18, 282.2, x1=27, bot=292.2, size=6)        # Note of Issue
    PB = 7.5     # party-block underscores: underscore baseline is top+6.0, so write at top+5.5
    for base, sp in ((0.0, s1), (93.0, s2)):
        if not sp['represented']:
            s.mark(1, 19, 423.1 + base, x1=29, bot=435.1 + base, size=6)
        s.text(1, 41, 413.0 + base, sp['last'].upper(), 8, height=PB)
        s.text(1, 41, 436.1 + base, sp['first'].upper(), 8, height=PB)
        s.text(1, 41, 459.4 + base, sp.get('middle', '').upper(), 8, height=PB)
        if sp['represented']:
            a = sp['attorney_name'].split()
            s.text(1, 181, 389.7 + base, ' '.join(a[:-1]), 8, height=PB)
            s.text(1, 376, 389.7 + base, a[-1] if a else '', 8, height=PB)
            s.text(1, 181, 436.1 + base, sp['attorney_address_line1'], 8, height=PB)
            s.text(1, 181, 459.4 + base, sp['attorney_phone'], 8, height=PB)
        else:
            ap = sp.get('address_parts')
            if ap:
                s.text(1, 181, 436.1 + base, ap.get('street', '').upper(), 8, height=PB, width=172)
                s.text(1, 359, 436.1 + base, ap.get('city', '').upper(), 8, height=PB, width=100)
                s.text(1, 464, 436.1 + base, ap.get('state', '').upper(), 8, height=PB, width=48)
                s.text(1, 517, 436.1 + base, ap.get('zip', ''), 8, height=PB, width=50)
            else:
                s.text(1, 181, 436.1 + base, sp['address'], 8, height=PB, width=170)
            s.text(1, 181, 459.4 + base, sp['phone'], 8, height=PB)
    s.mark(1, 567, 523.8, x1=577, bot=534.9, size=6)      # issue joined: NO
    s.text(1, 320, 731.0, d.get('preparer_name', ''), 9, height=10)
    return s


# --- UCS-840M (scanned sideways): upright-view 200 dpi px (u right, v down) of each line's start
A840 = {'county': (837, 234), 'index': (1553, 241)}
A840_SIDE = {   # last, first, dob; prior name rows; address rows (street, city, zip); male/female circle centres
    'spouse1': dict(last=(442, 355), first=(931, 358), dob=(1489, 363),
                    prior=[(427, 431, 927, 435), (427, 461, 927, 465), (427, 491, 927, 495)],
                    addr=[(523, 553, 1047, 557, 1570, 560), (523, 637, 1047, 641, 1570, 645),
                          (523, 703, 1047, 707, 1570, 712), (523, 770, 1047, 775, 1570, 778)],
                    male=(1438, 397), female=(1546, 396)),
    'spouse2': dict(last=(442, 859), first=(931, 864), dob=(1489, 868),
                    prior=[(427, 933, 927, 938), (427, 963, 927, 968), (427, 993, 927, 999)],
                    addr=[(523, 1055, 1047, 1061, 1570, 1064), (523, 1141, 1047, 1145, 1570, 1149),
                          (523, 1208, 1047, 1213, 1570, 1217), (523, 1276, 1047, 1280, 1570, 1284)],
                    male=(1436, 900), female=(1544, 899)),
}
A840_KIDS = [(1368, 1374, 1378), (1422, 1428, 1431), (1476, 1481, 1485), (1530, 1536, 1540), (1585, 1591, 1594)]


def build_rji_addendum(d, r=None):
    s = Sheet()
    minors, _ = split_children(d)
    s.rot_text(1, *A840['county'], d['county'], 9, width_px=380)
    s.rot_text(1, *A840['index'], d['index_no'], 9, width_px=440)
    for key in ('spouse1', 'spouse2'):
        sp, g = d[key], A840_SIDE[key]
        s.rot_text(1, *g['last'], sp['last'].upper(), 8, width_px=330)
        s.rot_text(1, *g['first'], sp['first'].upper(), 8, width_px=330)
        s.rot_text(1, *g['dob'], f"{sp['dob_month']}/{sp['dob_day']}/{sp['dob_year']}", 8)
        if sp.get('sex') in ('M', 'F'):
            s.rot_mark(1, *(g['male'] if sp['sex'] == 'M' else g['female']))
        for pn, (lu, lv, fu, fv) in zip(sp.get('prior_names', []), g['prior']):
            s.rot_text(1, lu, lv, pn.get('last', '').upper(), 8, width_px=330)
            s.rot_text(1, fu, fv, pn.get('first', '').upper(), 8, width_px=330)
        addrs = [sp.get('address_parts', {})] + sp.get('address_history', [])[:3]
        for i, (a, (su, sv, cu_, cv, zu, zv)) in enumerate(zip(addrs, g['addr'])):
            s.rot_text(1, su, sv, a.get('street', '').upper(), 8, width_px=500)
            s.rot_text(1, cu_, cv, a.get('city', '').upper(), 8, width_px=330)
            # "New York" is pre-printed on the present-address row only
            if i > 0 or a.get('state', 'NY').upper() not in ('NY', 'NEW YORK'):
                s.rot_text(1, 1392, zv - 2, a.get('state', '').upper(), 8, width_px=130)
            s.rot_text(1, zu, zv, a.get('zip', ''), 8, width_px=150)
    for ch, (lv, fv, dv) in zip(minors, A840_KIDS):
        s.rot_text(1, 427, lv, ch['last'].upper(), 8, width_px=340)
        s.rot_text(1, 918, fv, ch['first'].upper(), 8, width_px=340)
        s.rot_text(1, 1478, dv, ch['dob'], 8)
        if ch.get('sex') in ('M', 'F'):
            s.rot_mark(1, 1870 if ch['sex'] == 'M' else 1939, lv)
    if len(minors) > 5:
        s.extra_pages.append(('UCS-840M Attachment - Additional children under 18', [
            f"{c['last'].upper()}, {c['first'].upper()}  DOB {c['dob']}  {c.get('sex', '')}" for c in minors[5:]]))
    return s


def build_ucs111(d, r):
    s = Sheet()
    cs = d['child_support']
    t = lambda x, top, v, size=10, width=None: s.text(1, x, top, v, size, height=10.3, width=width)
    x_left = lambda x, top: s.mark(1, x - 9, top + 1.5, x1=x - 2, bot=top + 8.5, size=7)
    t(110, 154.1, d['county'], width=125)
    t(111, 178.8, d['index_no'])
    t(74, 224.8, d['date_summons_filed'])
    t(74, 316.8, str(len(d['children'])))
    if r:
        t(117, 362.8, money(r['adjusted']['spouse1']), 9)
        t(219, 362.8, money(r['adjusted']['spouse2']), 9)
        pays1 = r['non_custodial'] == 'spouse1'
        t(79, 431.8, money(r['agreed_annual']) if pays1 else '0', 10)
        t(174, 431.8, money(r['agreed_annual']) if not pays1 else '0', 10)
        x_left(86, 650.4) if r['deviate'] else x_left(198, 650.4)
        if r['deviate']:
            x_left(342, 408.9)
            rows, cur = [], ''
            for w in cs['deviation_reason'].split():
                nxt = (cur + ' ' + w).strip()
                if stringWidth(nxt, FONT, 8) <= 215:
                    cur = nxt
                else:
                    rows.append(cur)
                    cur = w
            rows.append(cur)
            if len(rows) > 6:
                raise SystemExit('UCS-111 deviation reason is too long for the "Other (specify)" space')
            for i, row in enumerate(rows):
                t(342, 422 + 11 * i, row, 8)
    h, cc, edu = cs.get('health', {}), cs.get('child_care', {}), cs.get('education', {})
    un = h.get('unreimbursed', {})
    for sp, x in (('spouse1', 86), ('spouse2', 198)):
        k = sp + '_pct'
        if float(h.get(k) or 0) > 0 or float(un.get(k) or 0) > 0:
            x_left(x, 512.3)
        if cc.get(sp):
            x_left(x, 535.4)
        if edu.get(sp):
            x_left(x, 558.3)
    m = d.get('maintenance', {'type': 'none'})
    if m.get('type', 'none') == 'none':
        x_left(342, 535.4)
        t(330, 581.4, '0')
    else:
        x_left(396 if m['payor'] == 'spouse1' else 464, 535.4)
        if m['frequency'] in cssa.PER_YEAR:
            t(330, 581.4, money(float(m['amount']) * cssa.PER_YEAR[m['frequency']]))
    pa = d.get('property_allocation', {})
    t(326, 650.4, pct(pa.get('plaintiff_pct')))
    t(448, 650.4, pct(pa.get('defendant_pct')))
    return s


def build_notify(d, r=None):
    s = Sheet()
    s.text(1, 260, 106.0, d['county'], 10)
    s.text(1, 110, 170.4, full_name(d['spouse1']), 10, width=196)
    s.text(1, 337, 170.4, full_name(d['spouse2']), 10, width=196)
    s.text(1, 133, 207.2, d['index_no'], 10)
    return s


def build_entry(d, r=None):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    s.text(1, 150, 90.5, d['county'], 11)
    s.text(1, 427, 111.1, d['index_no'], 10)
    s.text(1, 74, 124.9, full_name(s1), 11)
    s.text(1, 74, 187.0, full_name(s2), 11)
    s.text(1, 391, 271.4, d['county'], 10)
    server = d['serves_judgment']
    srv, oth = d[server], d[other(server)]
    top = 423.2 if server == 'spouse1' else 438.1
    s.b(1, 420.0 if srv['represented'] else 324.0, top, dy=-3.3)
    s.text(1, 326, 465.4, srv['attorney_name'] if srv['represented'] else full_name(srv), 9)
    a1, a2 = address_lines(srv)
    s.text(1, 326, 481.2, a1, 9, width=240)
    s.text(1, 326, 497.0, a2, 9, width=240)
    top = 530.3 if other(server) == 'spouse1' else 545.2
    s.b(1, 168.0 if oth['represented'] else 72.0, top, dy=-3.3)
    s.text(1, 74, 577.2, oth['attorney_name'] if oth['represented'] else full_name(oth), 9)
    a1, a2 = address_lines(oth)
    s.text(1, 74, 593.0, a1, 9, width=240)
    s.text(1, 74, 608.9, a2, 9, width=240)
    return s


def build_aff_judgment(d, r=None):
    s = Sheet()
    s.text(1, 148, 64.3, d['county'], 11)
    s.text(1, 412, 77.7, d['index_no'], 10)
    s.text(1, 108, 105.3, full_name(d['spouse1']), 10)
    s.text(1, 108, 215.5, full_name(d['spouse2']), 10)
    s.text(1, 145, 298.4, d['county'], 10)
    return s


def build_passthrough(d, r=None):
    return Sheet()


# =========================================================================== main
JOBS = [('jd2', build_jd2, '1-JD-2-Summons-FILLED.pdf'),
        ('jd3', build_jd3_full, '2-JD-3-Joint-Affirmation-FILLED.pdf'),
        ('jd4', build_jd4, '3-JD-4-Findings-Judgment-FILLED.pdf'),
        ('noi', build_noi, '4-Note-of-Issue-UD-9-FILLED.pdf'),
        ('rji', build_rji, '5-RJI-UD-13-FILLED.pdf'),
        ('rji_addendum', build_rji_addendum, '6-RJI-Addendum-UCS-840M-FILLED.pdf'),
        ('doh', build_doh, '7-DOH-2168-Certificate-of-Dissolution-FILLED.pdf'),
        ('ucs111', build_ucs111, '8-UCS-111-Child-Support-Summary-FILLED.pdf'),
        ('notify', build_notify, '9-Notification-Letter-FILLED.pdf'),
        ('entry', build_entry, '10-Notice-of-Entry-FILLED.pdf'),
        ('aff_judgment', build_aff_judgment, '11-Affirmation-of-Service-of-Judgment-FILLED.pdf'),
        ('aff_mail', build_passthrough, '12-Affirmation-of-Service-by-Mail-BLANK.pdf'),
        ('aff_personal', build_passthrough, '13-Affirmation-of-Personal-Delivery-BLANK.pdf')]


def main():
    ap = argparse.ArgumentParser(description='Fill the NYS joint divorce WITH CHILDREN packet.')
    default_packet = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'blank-packet.pdf')
    ap.add_argument('--packet', default=os.path.normpath(default_packet),
                    help='blank official packet PDF (defaults to the bundled 3/1/26 packet)')
    ap.add_argument('--case', required=True, help='case JSON')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--forms', default=DEFAULT_FORMS,
                    help='comma-separated form keys. Default: the eight initial-filing forms (' + DEFAULT_FORMS +
                         '). Also: notify, entry, aff_judgment, aff_mail, aff_personal. "all" = every form.')
    ap.add_argument('--no-cssa', action='store_true', help='leave every computed child-support field blank')
    a = ap.parse_args()

    if len(PdfReader(a.packet).pages) != 51:
        raise SystemExit('packet does not have 51 pages - re-verify PAGES against this revision first')
    d = json.load(open(a.case))
    if not d.get('children'):
        raise SystemExit('no children under 21 - use the ny-joint-divorce-no-children skill instead')
    wanted = [j[0] for j in JOBS] if a.forms == 'all' else [k.strip() for k in a.forms.split(',')]
    if 'scu' in wanted:
        raise SystemExit('The SCU Information Sheet (UD-8a) is not in this packet. Download UD-8a from '
                         'nycourts.gov separately if the spouses want Support Collection Unit services.')
    unknown = [k for k in wanted if k not in {j[0] for j in JOBS}]
    if unknown:
        raise SystemExit('unknown form key(s): ' + ', '.join(unknown))

    split_children(d)          # validates every child is under 21 before anything is written
    r = None
    if not a.no_cssa and not has_support_order(d):
        r = cssa.compute(d)
        print(cssa.worksheet(r))
        print()
    os.makedirs(a.out, exist_ok=True)
    for key, builder, name in JOBS:
        if key in wanted:
            builder(d, r).render(extract(a.packet, key), os.path.join(a.out, name))
            print('wrote', name)
    minors, _ = split_children(d)
    if minors and not uniform([c['legal_custody'] for c in minors]):
        print('NOTE: children have different legal-custody arrangements - JD-4 para 3 write-in lines '
              'must be completed by hand.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Fill the NYS Uncontested Joint Divorce (No Children) forms.

    python fill_divorce_forms.py --packet <blank-packet.pdf> --case case.json --out <dir>

Produces four separate PDFs: JD-5, JD-6, Note of Issue (UD-9), DOH-2168.

Coordinates are baked in. Text-layer forms (JD-5, JD-6) use PDF points measured
top-down from the top of the page. The two scanned forms (Note of Issue, DOH-2168)
use pixel coordinates from a 200 dpi render; SCALE converts them to points.

Never put Social Security numbers in the case file - those are handwritten.
"""
import argparse
import json
import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.pdfbase.pdfmetrics import stringWidth

INK = Color(0, 0, 0)
FONT = 'Helvetica'
BOLD = 'Helvetica-Bold'
SCALE = 0.36          # 200 dpi pixels -> PDF points

# 0-based page indices in the official packet PDF
PAGES = {'jd2': (2, 4), 'jd5': (4, 13), 'jd6': (13, 21), 'noi': (21, 22), 'rji': (22, 23),
         'doh': (23, 24), 'notify': (24, 25), 'entry': (25, 26), 'aff_judgment': (26, 27),
         'aff_mail': (27, 28), 'aff_personal': (28, 29)}

LINE = 12.0           # body line height on the text-layer forms
CB = 11.5             # checkbox side on JD-6


class Sheet:
    """Collects placements for one extracted form, then renders them."""

    def __init__(self):
        self.items = []          # (page_1based, x, top, bottom, text, size, mode)

    def text(self, page, x, top, s, size=10, height=LINE):
        if s not in (None, ''):
            self.items.append((page, x, top, top + height, str(s), size, 'left'))

    def mark(self, page, x0, top, x1=None, bot=None, size=9):
        x1 = x0 + CB if x1 is None else x1
        bot = top + CB if bot is None else bot
        self.items.append((page, (x0 + x1) / 2, top, bot, 'X', size, 'cbox'))

    def img_text(self, page, box, s, size=8, height=None):
        """box = [x0, top, x1, bottom] in 200 dpi pixels"""
        if s in (None, ''):
            return
        x0, t, x1, b = [v * SCALE for v in box]
        self.items.append((page, x0 + 1, t, b, str(s), size, 'left'))

    def img_mark(self, page, box, size=6):
        x0, t, x1, b = [v * SCALE for v in box]
        self.items.append((page, (x0 + x1) / 2, t, b, 'X', size, 'cbox'))

    def render(self, reader_pages, out_path):
        writer = PdfWriter()
        by_page = {}
        for it in self.items:
            by_page.setdefault(it[0], []).append(it)
        for i, page in enumerate(reader_pages, start=1):
            if i in by_page:
                w, h = float(page.mediabox.width), float(page.mediabox.height)
                buf = BytesIO()
                c = canvas.Canvas(buf, pagesize=(w, h))
                c.setFillColor(INK)
                for (_, x, top, bottom, s, size, mode) in by_page[i]:
                    c.setFont(BOLD if s == 'X' else FONT, size)
                    if mode == 'cbox':
                        c.drawCentredString(x, h - ((top + bottom) / 2 + 0.35 * size), s)
                    else:
                        c.drawString(x, h - (bottom - 0.25 * size), s)
                c.save()
                buf.seek(0)
                page.merge_page(PdfReader(buf).pages[0])
            writer.add_page(page)
        with open(out_path, 'wb') as fh:
            writer.write(fh)


def extract(src, key):
    a, b = PAGES[key]
    return [PdfReader(src).pages[i] for i in range(a, b)]


def wrap(text, font, size, width):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if stringWidth(t, font, size) <= width:
            cur = t
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out


def full_name(p):
    return ' '.join(x for x in (p['first'], p.get('middle', ''), p['last']) if x).upper()


# --------------------------------------------------------------------------- JD-6
def build_jd6(d):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']

    s.text(1, 395, 87.6, d['county'], 11)
    s.text(1, 74, 198.4, full_name(s1), 11)
    s.text(1, 74, 283.5, full_name(s2), 11)
    for pg_row, sp in ((373.2, s1), (393.9, s2)):
        s.mark(1, 191.2 if sp['represented'] else 383.1, pg_row)

    s.text(2, 213, 115.2, s1['address'], 9)
    s.text(2, 213, 156.6, s2['address'], 9)
    s.mark(2, 91.1, {'two_years': 218.1, 'one_year_married_ny': 259.5,
                     'one_year_breakdown_ny': 321.7, 'both_in_ny': 363.0}[d['residency']])
    if not d['military']:
        s.mark(2, 91.1, 466.5)
    s.text(2, 225, 549.9, d['marriage_date'], 10)
    s.text(2, 341, 549.9, d['marriage_place'], 10)
    s.mark(2, 109.1, 601.1 if d['ceremony'] == 'civil' else 621.8)

    s.mark(3, 91.1, 232.5)
    for base, sp in ((274.5, s1), (353.7, s2)):
        s.text(3, 289, base, sp['health_plan'], 9)
        s.text(3, 161, base + 19.8, sp['health_plan_address'], 9)
        s.text(3, 268, base + 39.6, sp['health_plan_id'], 9)
        s.text(3, 215, base + 59.4, sp['health_plan_admin'], 9)
    if d['maintenance'] == 'none':
        s.mark(3, 91.1, 677.8)
        s.mark(3, 127.1, 698.5)

    if d['property'] == 'already_divided':
        s.mark(4, 91.1, 518.5)
    else:
        s.mark(4, 91.1, 539.1)
        s.mark(4, 305.9 if not d['settlement_agreement'] else 191.8,
               539.1 if not d['settlement_agreement'] else 559.9)

    if d['maintenance'] == 'none':
        s.mark(6, 91.1, 213.3)
    if d['marital_home'] == 'not_applicable':
        s.text(6, 110, 464.7, 'NOT APPLICABLE', 10)
    if d['real_estate'] == 'not_applicable':
        s.text(6, 165, 651.1, 'NOT APPLICABLE', 10)

    s.mark(7, 91.1, 176.7 if d['settlement_agreement'] else 135.3)

    s.mark(8, 91.1 if d['serves_judgment'] == 'spouse1' else 176.3, 197.4)
    if s1.get('former_last_name'):
        s.mark(8, 91.1, 259.5)
        s.text(8, 385, 260.1, s1['former_last_name'], 10)
    if s2.get('former_last_name'):
        s.mark(8, 91.1, 280.2)
        s.text(8, 385, 280.8, s2['former_last_name'], 10)
    return s


# --------------------------------------------------------------------------- JD-5
def build_jd5(d):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']

    s.text(1, 150, 89.6, d['county'], 11)
    s.text(1, 90, 122, full_name(s1), 11)
    s.text(1, 90, 184, full_name(s2), 11)
    s.text(1, 145, 229.9, s1['residence_state'], 10)
    s.text(1, 145, 255.1, s1['residence_county'], 10)
    s.text(1, 145, 288.5, s2['residence_county'], 10)

    s.mark(2, 126, {'two_years': 140.0, 'one_year_resident': 179.6,
                    'one_year_breakdown_ny': 272.8, 'both_in_ny': 326.1}[d['residency']],
           x1=137, bot=152.1)
    s.text(2, 180, 379.6, full_name(s1), 10)
    s.text(2, 152, 399.2, s1['address'], 10)
    s.mark(2, 122 if s1['on_public_assistance'] else 159, 450.3, x1=129 if s1['on_public_assistance'] else 166,
           bot=462.6, size=8)
    s.text(2, 176, 491.1, full_name(s2), 10)
    s.text(2, 152, 510.7, s2['address'], 10)
    s.mark(2, 121 if s2['on_public_assistance'] else 158, 561.9, x1=128 if s2['on_public_assistance'] else 166,
           bot=574.2, size=8)
    if not d['military']:
        s.mark(2, 90, 636.4, x1=101, bot=648.5)

    s.text(3, 224, 126.0, d['marriage_date'], 10)
    s.text(3, 352, 126.0, d['marriage_place'], 10)
    s.mark(3, 126, 171.4 if d['ceremony'] == 'civil' else 191.2, x1=137, bot=183.5)
    s.text(3, 290, 609.9, s1['health_plan'], 10)
    s.text(3, 162, 629.8, s1['health_plan_address'], 10)
    s.text(3, 270, 649.6, s1['health_plan_id'], 10)
    s.text(3, 216, 669.4, s1['health_plan_admin'], 10)

    s.text(4, 290, 73.0, s2['health_plan'], 10)
    s.text(4, 162, 92.7, s2['health_plan_address'], 10)
    s.text(4, 270, 112.4, s2['health_plan_id'], 10)
    s.text(4, 216, 132.2, s2['health_plan_admin'], 10)
    rows = {'A': 232.9, 'B': 258.6, 'C': 284.4, 'D': 310.1, 'E': 335.9, 'F': 373.2, 'G': 410.7, 'H': 436.5}
    for key, top in rows.items():
        s.text(4, 362, top, d['income']['spouse1'].get(key, ''), 10)
        s.text(4, 456, top, d['income']['spouse2'].get(key, ''), 10)
    if d['maintenance'] == 'none':
        s.mark(4, 72, 634.1, x1=83, bot=646.2)

    if d['marital_home'] == 'not_applicable':
        s.mark(5, 81, 662.9, x1=92, bot=675.0)

    prop_top = {'already_divided': 263.9, 'separate_agreement': 297.5, 'no_separate_agreement': 317.3}
    s.mark(6, 90, prop_top[d['property']], x1=101, bot=prop_top[d['property']] + 12)
    if d['property'] == 'no_separate_agreement' and d.get('property_text'):
        size, lead, x0, x1, start = 5.6, 9.9, 109.0, 534.0, 340.4
        for n, line in enumerate(wrap(d['property_text'], FONT, size, x1 - x0)):
            s.items.append((6, x0, start + lead * n - 6, start + lead * n, line, size, 'left'))
    if d['real_estate'] == 'not_applicable':
        s.mark(6, 90, 437.6, x1=101, bot=449.7)
    if d['pensions'] == 'waive':
        s.mark(6, 90, 678.9, x1=101, bot=691.0)

    debt_top = {'not_applicable': 92.6, 'separate_agreement': 112.4, 'agree_that': 132.2}
    if d.get('debt') in debt_top:
        s.mark(7, 90, debt_top[d['debt']], x1=101, bot=debt_top[d['debt']] + 12)
    if s1.get('former_last_name'):
        s.mark(7, 90, 267.8, x1=101, bot=279.9)
        s.text(7, 212, 287.7, s1['former_last_name'], 10)
    if s2.get('former_last_name'):
        s.mark(7, 90, 307.4, x1=101, bot=319.5)
        s.text(7, 212, 327.3, s2['former_last_name'], 10)
    if d['fees'] == 'each_own':
        s.mark(7, 90, 437.4, x1=101, bot=449.5)

    s.text(8, 222, 197.9, full_name(s1), 10)
    s.text(8, 389, 434.7, full_name(s1), 10)
    s.text(9, 222, 197.9, full_name(s2), 10)
    s.text(9, 389, 434.7, full_name(s2), 10)
    return s


# --------------------------------------------------------------------------- Note of Issue
def build_noi(d):
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
    # line 12 - plaintiff side
    s.img_mark(1, [615, 1529, 634, 1551] if s1['represented'] else [356, 1529, 374, 1551], 6.5)
    who1 = s1['attorney_name'] + ', ESQ.' if s1['represented'] else full_name(s1)
    s.img_text(1, [700, 1562, 1500, 1590], who1, 10)
    s.img_text(1, [358, 1594, 1200, 1620], s1['attorney_address_line1'] if s1['represented'] else '', 10)
    s.img_text(1, [358, 1622, 1200, 1648], s1['attorney_address_line2'] if s1['represented'] else '', 10)
    s.img_text(1, [538, 1662, 1000, 1690], s1['attorney_phone'] if s1['represented'] else s1['phone'], 10)
    s.img_text(1, [538, 1690, 1000, 1718], s1.get('attorney_fax', ''), 10)
    # line 13 - defendant side
    s.img_mark(1, [615, 1790, 634, 1812] if s2['represented'] else [356, 1790, 374, 1812], 6.5)
    who2 = s2['attorney_name'] + ', ESQ.' if s2['represented'] else full_name(s2)
    s.img_text(1, [700, 1822, 1500, 1850], who2, 10)
    addr = s2['address'].split(', ', 1)
    s.img_text(1, [358, 1853, 1200, 1879], addr[0], 10)
    s.img_text(1, [358, 1881, 1200, 1907], addr[1] if len(addr) > 1 else '', 10)
    s.img_text(1, [538, 1922, 1000, 1950], s2['attorney_phone'] if s2['represented'] else s2['phone'], 10)
    return s


# --------------------------------------------------------------------------- DOH-2168
DOH_EDU = {13: 1467, 14: 1498, 15: 1532, 16: 1563, 17: 1595}


def build_doh(d):
    s = Sheet()
    for sp, dy in ((d['spouse1'], 0), (d['spouse2'], 296)):
        s.img_text(1, [380, 352 + dy, 592, 378 + dy], sp['first'], 9)
        s.img_text(1, [600, 352 + dy, 812, 378 + dy], sp.get('middle', ''), 9)
        s.img_text(1, [820, 352 + dy, 982, 378 + dy], sp['last'], 9)
        s.img_text(1, [995, 352 + dy, 1250, 378 + dy], sp.get('birth_name', ''), 9)
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
    s.img_text(1, [882, 1040, 1246, 1076], d['children_born'], 10)
    s.img_text(1, [1262, 1040, 1670, 1076], d['children_under_18'], 10)

    for sp, dy in ((d['spouse1'], 0), (d['spouse2'], 162)):
        s.img_text(1, [218, 1512 + dy, 412, 1540 + dy], sp['race'], 9)
        s.img_text(1, [424, 1512 + dy, 634, 1540 + dy], sp['marriage_number'], 9)
        if sp['prior_ended_death'] == 'NONE':
            s.img_mark(1, [722, 1562 + dy + (5 if dy else 0), 743, 1581 + dy + (5 if dy else 0)])
        if sp['prior_ended_divorce'] == 'NONE':
            s.img_mark(1, [876, 1562 + dy + (5 if dy else 0), 898, 1581 + dy + (5 if dy else 0)])
        ex = DOH_EDU[sp['education_box']]
        s.img_mark(1, [ex, 1508 + dy + (2 if dy else 0), ex + 23, 1531 + dy + (2 if dy else 0)])

    s.img_text(1, [178, 1782, 642, 1810], full_name(d['spouse1']), 9)
    s.img_text(1, [656, 1782, 1146, 1810], d['decree_granted_to'], 9)
    s.img_text(1, [1162, 1782, 1666, 1810], d['legal_grounds'], 8)
    s.img_text(1, [250, 1872, 1150, 1902], d.get('preparer_name', ''), 10)
    return s



# --------------------------------------------------------------------------- JD-2 Summons
JD2_RELIEF = {
    'none': 89.6, 'maintenance_waived': 137.2, 'property_waived': 153.1,
    'property': 184.9, 'maintenance': 200.7, 'retirement': 216.6, 'child_support': 232.4,
    'custody': 264.2, 'visitation': 280.1, 'fees': 295.9, 'former_name': 311.9,
    'order_of_protection': 327.7, 'marital_home': 343.5, 'court_orders': 359.4, 'other': 375.3,
}


def build_jd2(d):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    s.text(1, 428, 76.7, d['index_no'], 10)
    s.text(1, 150, 90.5, d['county'], 11)
    s.text(1, 472, 96.5, d['date_summons_filed'], 9)
    s.text(1, 368, 130.1, d['county'], 9)
    s.text(1, 74, 135.2, full_name(s1), 11)
    s.text(1, 74, 197.2, full_name(s2), 11)
    s.text(1, 76, 556.5, d['county'], 10)
    # venue: whichever spouse actually lives in the filing county
    for top, sp in ((584.1, s1), (597.9, s2)):
        if sp['residence_county'].strip().upper() == d['county'].strip().upper():
            s.mark(1, 90, top, x1=101, bot=top + 12)
            s.text(1, 279, top, sp['address'], 9)

    for key in d.get('ancillary_relief', []):
        top = JD2_RELIEF[key]
        s.mark(2, 90, top, x1=101, bot=top + 12)
    s.mark(2, 360, 458.9 if s1['represented'] else 444.0, x1=367, bot=(458.9 if s1['represented'] else 444.0) + 12,
           size=8)
    s.text(2, 432, 476.1, s1['attorney_phone'] if s1['represented'] else s1['phone'], 9)
    s.text(2, 362, 503.7, s1['attorney_name'] if s1['represented'] else full_name(s1), 9)
    s.text(2, 362, 519.7, s1['attorney_address_line1'] if s1['represented'] else s1['address'], 9)
    s.text(2, 362, 535.5, s1['attorney_address_line2'], 9)
    s.mark(2, 360, 619.2 if s2['represented'] else 604.3, x1=367, bot=(619.2 if s2['represented'] else 604.3) + 12,
           size=8)
    s.text(2, 432, 636.4, s2['attorney_phone'] if s2['represented'] else s2['phone'], 9)
    s.text(2, 362, 664.0, s2['attorney_name'] if s2['represented'] else full_name(s2), 9)
    s.text(2, 362, 679.8, s2['attorney_address_line1'] if s2['represented'] else s2['address'], 9)
    s.text(2, 362, 695.6, s2['attorney_address_line2'], 9)
    return s


# --------------------------------------------------------------------------- RJI (UD-13)
def build_rji(d):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    s.text(1, 176, 66.2, 'SUPREME', 8, height=10)
    s.text(1, 336, 66.2, d['county'], 8, height=10)
    s.text(1, 180, 85.2, d['index_no'], 8, height=10)
    s.text(1, 25, 128, full_name(s1), 9, height=10)
    s.text(1, 25, 178, full_name(s2), 9, height=10)

    yes_no = lambda flag, top: s.mark(1, 263 if flag else 292, top, x1=271 if flag else 300, bot=top + 8, size=6)
    yes_no(bool(d['date_summons_filed']), 228.3)
    s.text(1, 390, 228.3, d['date_summons_filed'], 7, height=9)
    yes_no(bool(d['date_summons_served']), 240.7)
    s.text(1, 390, 241.6, d['date_summons_served'], 7, height=9)
    yes_no(False, 253.2)                                  # children under 18
    s.mark(1, 18, 282.2, x1=27, bot=292.2, size=6)        # Note of Issue

    for base, sp in ((0.0, s1), (93.0, s2)):
        if not sp['represented']:
            s.mark(1, 19, 423.1 + base, x1=29, bot=435.1 + base, size=6)
        s.text(1, 41, 413.0 + base, sp['last'], 8, height=10)
        s.text(1, 41, 436.1 + base, sp['first'], 8, height=10)
        s.text(1, 41, 459.4 + base, sp.get('middle', ''), 8, height=10)
        if sp['represented']:
            a = sp['attorney_name'].split()
            s.text(1, 181, 389.7 + base, ' '.join(a[:-1]), 8, height=10)
            s.text(1, 376, 389.7 + base, a[-1] if a else '', 8, height=10)
            s.text(1, 181, 436.1 + base, sp['attorney_address_line1'], 8, height=10)
            s.text(1, 181, 459.4 + base, sp['attorney_phone'], 8, height=10)
        else:
            s.text(1, 181, 436.1 + base, sp['address'], 8, height=10)
            s.text(1, 181, 459.4 + base, sp['phone'], 8, height=10)
    s.mark(1, 567, 523.8, x1=577, bot=534.9, size=6)      # issue joined: NO
    s.text(1, 320, 731.0, d.get('preparer_name', ''), 9, height=10)
    return s


# --------------------------------------------------------------------------- Notification letter
def build_notify(d):
    s = Sheet()
    s.text(1, 260, 106.0, d['county'], 10)
    s.text(1, 110, 170.4, full_name(d['spouse1']), 10)
    s.text(1, 337, 170.4, full_name(d['spouse2']), 10)
    s.text(1, 133, 207.2, d['index_no'], 10)
    return s


# --------------------------------------------------------------------------- Notice of Entry
def build_entry(d):
    s = Sheet()
    s1, s2 = d['spouse1'], d['spouse2']
    s.text(1, 150, 90.5, d['county'], 11)
    s.text(1, 427, 111.1, d['index_no'], 10)
    s.text(1, 74, 124.9, full_name(s1), 11)
    s.text(1, 74, 187.0, full_name(s2), 11)
    s.text(1, 391, 271.4, d['county'], 10)
    server, other = ('spouse1', 'spouse2') if d['serves_judgment'] == 'spouse1' else ('spouse2', 'spouse1')
    srv, oth = d[server], d[other]
    # FROM block
    s.mark(1, 420 if srv['represented'] else 324, 423.2 if server == 'spouse1' else 438.1,
           x1=427 if srv['represented'] else 331,
           bot=(423.2 if server == 'spouse1' else 438.1) + 12, size=8)
    s.text(1, 326, 465.4, srv['attorney_name'] if srv['represented'] else full_name(srv), 9)
    s.text(1, 326, 481.2, srv['attorney_address_line1'] if srv['represented'] else srv['address'], 9)
    s.text(1, 326, 497.0, srv['attorney_address_line2'], 9)
    # TO block
    s.mark(1, 168 if oth['represented'] else 72, 530.3 if other == 'spouse1' else 545.2,
           x1=175 if oth['represented'] else 79,
           bot=(530.3 if other == 'spouse1' else 545.2) + 12, size=8)
    s.text(1, 74, 577.2, oth['attorney_name'] if oth['represented'] else full_name(oth), 9)
    s.text(1, 74, 593.0, oth['attorney_address_line1'] if oth['represented'] else oth['address'], 9)
    s.text(1, 74, 608.9, oth['attorney_address_line2'], 9)
    return s


# --------------------------------------------------------------------------- Affirmation of service of judgment
def build_aff_judgment(d):
    s = Sheet()
    s.text(1, 148, 64.3, d['county'], 11)
    s.text(1, 412, 77.7, d['index_no'], 10)
    s.text(1, 108, 105.3, full_name(d['spouse1']), 10)
    s.text(1, 108, 215.5, full_name(d['spouse2']), 10)
    s.text(1, 145, 298.4, d['county'], 10)
    return s


def build_passthrough(d):
    return Sheet()


def main():
    ap = argparse.ArgumentParser()
    default_packet = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', 'assets', 'blank-packet.pdf')
    ap.add_argument('--packet', default=os.path.normpath(default_packet),
                    help='blank official packet PDF (defaults to the copy bundled in assets/)')
    ap.add_argument('--case', required=True, help='case JSON')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--forms', default='jd2,jd5,jd6,noi,doh',
                    help='comma-separated form keys to fill. Default is the five core filing forms. '
                         'Choices: jd2, jd5, jd6, noi, rji, doh, notify, entry, aff_judgment, '
                         'aff_mail, aff_personal. Use "all" for the whole packet.')
    a = ap.parse_args()

    d = json.load(open(a.case))
    os.makedirs(a.out, exist_ok=True)
    jobs = [('jd2', build_jd2, '1-JD-2-Summons-FILLED.pdf'),
            ('jd5', build_jd5, '2-JD-5-Joint-Affirmation-FILLED.pdf'),
            ('jd6', build_jd6, '3-JD-6-Findings-Judgment-FILLED.pdf'),
            ('noi', build_noi, '4-Note-of-Issue-UD-9-FILLED.pdf'),
            ('rji', build_rji, '5-RJI-UD-13-FILLED.pdf'),
            ('doh', build_doh, '6-DOH-2168-Certificate-of-Dissolution-FILLED.pdf'),
            ('notify', build_notify, '7-Notification-Letter-FILLED.pdf'),
            ('entry', build_entry, '8-Notice-of-Entry-FILLED.pdf'),
            ('aff_judgment', build_aff_judgment, '9-Affirmation-of-Service-of-Judgment-FILLED.pdf'),
            ('aff_mail', build_passthrough, '10-Affirmation-of-Service-by-Mail-BLANK.pdf'),
            ('aff_personal', build_passthrough, '11-Affirmation-of-Personal-Delivery-BLANK.pdf')]
    wanted = [k.strip() for k in a.forms.split(',')] if a.forms != 'all' else [j[0] for j in jobs]
    unknown = [k for k in wanted if k not in {j[0] for j in jobs}]
    if unknown:
        raise SystemExit('unknown form key(s): ' + ', '.join(unknown))
    for key, builder, name in jobs:
        if key not in wanted:
            continue
        builder(d).render(extract(a.packet, key), os.path.join(a.out, name))
        print('wrote', name)


if __name__ == '__main__':
    main()

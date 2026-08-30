---
name: ny-joint-divorce-with-children
description: Fills every form in the New York State Uncontested Joint Divorce WITH CHILDREN packet (JD-2, JD-3 Joint Affirmation, JD-4 Findings/Judgment, Note of Issue, RJI UD-13, RJI Addendum UCS-840M, DOH-2168, UCS-111 Child Support Summary, Notification Letter, Notice of Entry, Affirmations of Service) by overlaying typed answers onto the official blank PDFs at exact field coordinates, and computes the CSSA child support figures those forms require. Use whenever someone with children under 21 wants to do or file a New York divorce, or mentions NY divorce forms, a joint or uncontested divorce packet, JD-2, JD-3, JD-4, UCS-840M, UCS-111, UD-13, DOH-2168, a Note of Issue, a Certificate of Dissolution, child support calculations for a divorce, or a Judgment of Divorce - including when they just upload the packet and start listing names and dates. Not for cases with no children under 21.
---

# NY Uncontested Joint Divorce - With Children

Fills the NYS "Uncontested Joint Divorce With Children" packet by drawing text
onto the official blank PDF at measured coordinates. Output is a real page
overlay, not an annotation, so it prints and flattens correctly for court filing.

**Scope check first.** This packet only applies when there are children of the
marriage under 21. If there are none, stop - that case needs the "With No
Children" packet (JD-5/JD-6), which is a separate skill.

## What it produces

Thirteen files, numbered in filing order:

| # | Form | Filled? |
|---|---|---|
| 1 | JD-2 Summons with Notice / Notice of Appearance | yes |
| 2 | JD-3 Joint Affirmation of Facts and Agreement (with children) | yes |
| 3 | JD-4 Findings of Fact, Conclusions of Law, Judgment | yes |
| 4 | Note of Issue (UD-9) | yes |
| 5 | Request for Judicial Intervention (UD-13) | yes |
| 6 | RJI Addendum (UCS-840M) | yes |
| 7 | DOH-2168 Certificate of Dissolution | yes |
| 8 | UCS-111 Child Support Summary | yes |
| 9 | Notification Letter / Postcard | caption only - the clerk checks the boxes |
| 10 | Notice of Entry | yes (post-judgment) |
| 11 | Affirmation of Service by Mail of Judgment w/ Notice of Entry | caption only - the server fills the rest |
| 12 | Affirmation of Service by Mail | blank pass-through |
| 13 | Affirmation of Personal Delivery | blank pass-through |

Items 1-9 are the initial filing (`--forms` defaults to 1-8; add `notify` for
item 9, which needs two copies plus two stamped self-addressed envelopes).
Items 10-13 come after the judge signs. Unlike the no-children packet, items
12-13 are NOT irrelevant here - their checkboxes are child-support service
documents - but they are the process server's to fill, so they pass through
blank.

There is a `scu` form key that intentionally errors: the SCU Information Sheet
(UD-8a) that JD-3 § B.2 references is **not in this packet**. If the spouses
want SCU services, download UD-8a from nycourts.gov separately.

## Boundaries

State once, at the start, that you are transcribing what the user provides and
are not giving legal advice, and that an attorney should review before filing.
Don't repeat it every turn.

**Never accept or write Social Security numbers - including the children's.**
The JD-3 (§ B.3, § C.3, and every child block), the JD-4 (¶4 and the children
list), and the DOH-2168 (boxes 1C, 6C) all ask for them. Leave every SSN field
blank and tell the user to write them in by hand. If the user pastes an SSN,
don't put it in the case file or the PDF.

**Never fill signature lines.** JD-3 pages 16-17 (both spouses sign before a
notary - the form says STOP), JD-4 page 18 (the judge signs), DOH-2168 box 26
signature, and every affirmation of service. Printed names are fine; signatures
are not.

**Never guess a substantive term.** Custody, parenting time, deviation reasons,
debt allocation, income figures, maintenance, and property division are legal
choices. If the user hasn't said, leave the field blank and list it as
outstanding. Formatting defaults (all-caps names, date format) are yours to
pick; legal content is not.

**Computed figures are computed, then confirmed.** Every child-support number
on JD-3 § B.2.a, JD-4 ¶18, and UCS-111 comes from `scripts/cssa.py` - never
hand-entered, never accepted from the user as a bare number. The filler runs
the calculation automatically and prints the worksheet; show that worksheet to
the user and get an explicit OK before delivering the forms. If the spouses
want a different amount, that is a *deviation* (`child_support.deviate` +
reason), not an edit to the calculation. `--no-cssa` leaves all computed
fields blank.

**DOH-2168 race boxes (15/19) are never filled.** Leave them for the parties
to complete by hand if they choose.

## Workflow

1. **The blank packet is bundled** at `assets/blank-packet.pdf` (the official
   51-page 3/1/26 packet - it already contains every form including the shared
   ones). `--packet` is only needed if the user uploads a newer revision; if
   they do, verify the page layout matches `PAGES` in the script before
   trusting any coordinates.

2. **Ask for the case data in one pass.** Use
   `references/intake-checklist.md`. Ask everything at once rather than
   drip-feeding questions.

3. **Write the case JSON.** Copy `assets/case-template.json` and replace the
   values. Every key is documented in `references/case-schema.md`. Leave
   unknown values as `""` - the script skips empty strings.

4. **Run the filler, confirm the CSSA worksheet.**

   ```bash
   python scripts/cssa.py --case case.json          # worksheet alone, or
   python scripts/fill_divorce_forms.py --case case.json --out <dir>
   ```

   `--forms` defaults to the eight initial-filing forms:
   **jd2, jd3, jd4, noi, rji, rji_addendum, doh, ucs111**.
   Other keys: `notify`, `entry`, `aff_judgment`, `aff_mail`, `aff_personal`.
   `--forms all` does the entire packet. Deliver forms as separate PDFs -
   clerks usually want them filed individually.

5. **Verify visually. Always.** Render each filled page and look at it:
   ```python
   import pypdfium2 as pdfium
   pdfium.PdfDocument(path)[n].render(scale=170/72).to_pil().save('check.png')
   ```
   Then `view` the PNG. Coordinate drift is the failure mode of this whole
   approach and it is invisible unless you look. Check specifically: text
   sitting on top of a printed label ("$", "for", "is" right before a blank
   are the usual victims), X marks on the wrong checkbox, and text overrunning
   a cell border. The UCS-840M page must be rotated to check
   (`.rotate(90, expand=True)` after rendering). Fix and re-render before
   delivering.

6. **Report what's still blank.** End with an explicit list: SSNs, index
   number if not yet assigned, dates the court supplies (Note of Issue clerk
   box, JD-4 courthouse/date/judge, DOH-2168 decree section 14A-14F, Notice
   of Entry stamped date), signatures and notarization, and anything the user
   hasn't decided.

## Which form gets which answer

- **The CSSA worksheet appears twice at different depths.** JD-3 p.10 carries
  the headline numbers; JD-4 ¶18 carries the full derivation (adjusted
  incomes, pro-rata shares, capped obligation, over-cap election). Both are
  fed from the same `cssa.compute()` result so they cannot disagree.
- **The JD-3 income table rows G and H are derived** (G = B+C+D+E+F,
  H = A−G). The filler computes them; never take them from the user, or the
  table can contradict the CSSA figures.
- **Custody chart vs. decree.** Per-child custody goes in the JD-3 p.6-7
  chart. The JD-4 ¶3 decree only takes a *uniform* arrangement ("joint legal
  custody of all of the children"); if the children have different
  arrangements, the JD-4 write-in lines must be completed by hand - flag it.
- **"Children of the spouses" counts differ by form.** JD-3 splits under-18
  (custody chart, 3 slots) from 18-20 (3 slots); JD-4 p.5 lists all under-21
  (6 slots); UCS-840M lists only under-18 (5 slots); DOH-2168 wants counts,
  not names. The filler routes one `children` array to all four - don't
  maintain separate lists.
- **Parenting time** appears on JD-3 p.8 (schedule write-in) and JD-4 ¶4.
  Fill both from `custody.parenting_time_schedule`.
- **Former last name** appears on JD-3 p.15 and JD-4 ¶18 (last page). Both.

## Field notes that bite

- **Names in all caps** on caption lines, child names, and DOH-2168; preparer
  name in normal case.
- **UCS-111 prints no checkbox glyphs at all.** The blank form has empty space
  where its ☐ boxes should be (the PDF's box characters map to nothing). The
  filler puts a small X just left of each label - that is correct behavior,
  not drift.
- **UCS-111 instruction sheet says write 0, not blank**, for none-amounts. The
  filler does this for the non-payor spouse and waived maintenance.
- **UCS-840M is scanned sideways.** See `references/measuring.md` before
  touching its coordinates.
- **DOH-2168 "STATE OF BIRTH (COUNTRY IF NOT USA)"** wants the *state* for
  anyone born in the US. Push back if the user gives a country for a US birth.
- **DOH-2168 boxes 14A-14F** are the decree section - the county clerk
  completes them. Leave blank.
- **DOH-2168 education** is a bubble row numbered 00-17 (total years of
  schooling). A bachelor's is box **16**. All 18 boxes are mapped.
- **Note of Issue line 9** for a joint uncontested divorce is normally
  NOT JOINED - Waiver.
- **RJI children question is YES** here (unlike the no-children skill) whenever
  any child is under 18, and the UCS-840M addendum must be attached.
- **JD-3 p.16 says STOP** - both spouses sign in front of a notary. Say so.
- **Marital home "until"** on JD-3 p.13 and JD-4 ¶9 accepts a phrase ("the
  youngest child turns 18"), not just a date.

## If the packet version changes

Coordinates are baked into the script. If NYS revises a form, re-measure with
`references/measuring.md`. The CSSA cap ($193,000) and maintenance cap
($241,000) printed on the forms are revised by NYS every two years - if the
packet's printed caps differ from `CAP` in `scripts/cssa.py`, the forms win;
update the constant.

## Reference files

- `references/intake-checklist.md` - everything to ask the user, in one list
- `references/case-schema.md` - every key in the case JSON and its allowed values
- `references/measuring.md` - how to re-derive coordinates, incl. the rotated scan
- `assets/case-template.json` - a filled example to copy
- `assets/case-example-complex.json` - a second example exercising the harder
  branches (maintenance in-form, over-cap income, deviation, an 18-20 child, an
  existing Family Court order, a represented spouse, write-in property/debt)
- `scripts/cssa.py` - the CSSA calculator (importable and standalone)

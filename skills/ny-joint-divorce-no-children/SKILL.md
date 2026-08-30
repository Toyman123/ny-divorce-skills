---
name: ny-joint-divorce-no-children
description: Fills every form in the New York State Uncontested Joint Divorce WITH NO CHILDREN packet (JD-2, JD-5, JD-6, Note of Issue UD-9, RJI UD-13, DOH-2168, Notification Letter, Notice of Entry, Affirmations of Service) by overlaying typed answers onto the official blank PDFs at exact field coordinates. Use whenever someone wants to do or file a New York divorce, or mentions NY divorce forms, a joint or uncontested divorce packet, JD-2, JD-5, JD-6, UD-9, UD-13, DOH-2168, a Note of Issue, a Certificate of Dissolution, or a Judgment of Divorce - including when they just upload the packet and start listing names and dates. Not for cases with children under 21.
---

# NY Uncontested Joint Divorce - No Children

Fills the NYS "Uncontested Joint Divorce With No Children" packet by drawing text
onto the official blank PDF at measured coordinates. Output is a real page overlay,
not an annotation, so it prints and flattens correctly for court filing.

**Scope check first.** This packet only works when there are no children under 21
of the marriage. If there are, stop and say so - that case needs the separate
"With Children" packet (JD-3 Joint Affirmation and JD-4 Findings/Judgment), which
this skill does not cover.

## What it produces

Eleven files, numbered in filing order:

| # | Form | Filled? |
|---|---|---|
| 1 | JD-2 Summons with Notice / Notice of Appearance | yes |
| 2 | JD-5 Joint Affirmation of Facts and Agreement | yes |
| 3 | JD-6 Findings of Fact, Conclusions of Law, Judgment | yes |
| 4 | Note of Issue (UD-9) | yes |
| 5 | Request for Judicial Intervention (UD-13) | yes |
| 6 | DOH-2168 Certificate of Dissolution | yes |
| 7 | Notification Letter / Postcard | caption only - the clerk checks the boxes |
| 8 | Notice of Entry | yes (post-judgment) |
| 9 | Affirmation of Service by Mail of Judgment w/ Notice of Entry | caption only - the server fills the rest |
| 10 | Affirmation of Service by Mail | blank pass-through |
| 11 | Affirmation of Personal Delivery | blank pass-through |

Items 10 and 11 stay blank on purpose: their checkbox options are all child-support
documents, so they don't apply to a no-children case. Item 7 needs two copies plus
two stamped self-addressed envelopes.

Items 1-7 are the initial filing. Items 8-11 come after the judge signs.

## Boundaries

State once, at the start, that you are transcribing what the user provides and are
not giving legal advice, and that an attorney should review before filing. Don't
repeat it every turn.

**Never accept or write Social Security numbers.** The JD-5 (§ B.3, § C.3), the
JD-6 (¶4), and the DOH-2168 (boxes 1C, 6C) all ask for them. Leave every SSN field
blank and tell the user to write them in by hand. If the user pastes an SSN, don't
put it in the case file or the PDF.

**Never fill signature lines.** JD-5 pages 8 and 9, JD-6 last page, DOH-2168 box 26
signature. The *printed* preparer name on DOH-2168 box 26 is fine; the signature
itself is not.

**Never guess a substantive term.** Debt allocation, income figures, maintenance,
and property division are legal choices. If the user hasn't said, leave the field
blank and list it as outstanding. Formatting defaults (all-caps names, date format)
are yours to pick; legal content is not.

## Workflow

1. **Get the blank packet.** The user usually uploads it. If not, it is the official
   NYS packet PDF. Confirm the page layout matches `PAGES` in the script - print
   the first line of each page with pdfplumber if unsure.

2. **Ask for the case data in one pass.** Use the checklist in
   `references/intake-checklist.md`. Ask everything at once rather than
   drip-feeding questions; the user is usually working from a completed intake sheet.

3. **Write the case JSON.** Copy `assets/case-template.json` and replace the values.
   Every key is documented in `references/case-schema.md`. Leave unknown values as
   `""` - the script skips empty strings.

4. **Ask which forms they want, then run the filler.** Fill only what was asked
   for - do not hand over the whole packet by default.

   ```bash
   python scripts/fill_divorce_forms.py --case case.json --out <output-dir> \
     --forms jd2,jd5,jd6,noi,doh
   ```

   The blank packet is bundled at `assets/blank-packet.pdf`, so `--packet` is
   optional - pass it only if the user uploads a newer revision.

   `--forms` defaults to the five core filing forms: **jd2, jd5, jd6, noi, doh**.
   Other keys: `rji`, `notify`, `entry`, `aff_judgment`, `aff_mail`,
   `aff_personal`. `--forms all` does the entire packet.

   Each form comes out as its own PDF. Deliver them separately unless the user asks
   for a combined file - clerks usually want them filed individually.

5. **Verify visually. Always.** Render each filled page and look at it:
   ```python
   import pypdfium2 as pdfium
   pdfium.PdfDocument(path)[n].render(scale=170/72).to_pil().save('check.png')
   ```
   Then `view` the PNG. Coordinate drift is the failure mode of this whole approach
   and it is invisible unless you look. Check specifically: text sitting on top of a
   printed label, X marks landing on the wrong checkbox, and text overrunning a cell
   border. Fix and re-render before delivering.

6. **Report what's still blank.** End with an explicit list: SSNs, index number,
   dates the court supplies, signatures, and anything the user hasn't decided.

## Which form gets which answer

Users routinely name the wrong form. The most common confusion:

- **Property division language** goes on the **JD-5**, Marital Property § A, in the
  "we agree that:" write-in. The **JD-6 ¶14 has no write-in space** - it is two
  checkboxes that point back at the JD-5. If a user hands you a paragraph of
  property language and says it goes on the JD-6, redirect them.
- **Health insurance details** appear on both JD-5 (§ Health Insurance ¶5) and
  JD-6 (¶10). Fill both identically.
- **Former last name** appears on JD-5 § Name Change and JD-6 ¶11. Both.
- **Residency** appears on JD-5 § A.6 and JD-6 ¶5, with *different option wording*.
  The script maps them; don't hand-match them.

## Field notes that bite

- **Names in all caps** on the caption lines and DOH-2168; the preparer name in
  normal case reads better on the signature line.
- **DOH-2168 "STATE OF BIRTH (COUNTRY IF NOT USA)"** wants the *state* for anyone
  born in the US. "USA" or "United States" is not an answer. Push back if the user
  gives you a country for a US birth.
- **DOH-2168 boxes 14A-14F** are the decree section - the county clerk completes
  them. Leave blank.
- **DOH-2168 education** is a bubble row numbered 00-17. College 4 (a bachelor's) is
  box **16**, not box 14. Set `education_box` to the total years of schooling.
- **Note of Issue line 9** for a joint uncontested divorce is normally
  NOT JOINED - Waiver.
- **JD-5 page 8 says STOP** - both spouses sign in front of a notary. Say so.
- **Marital home / real estate not applicable**: JD-6 ¶3 and ¶4 have no N/A
  checkbox, so the script writes "NOT APPLICABLE" on the address line.

## If the packet version changes

The coordinates are baked into the script. If NYS revises a form, re-measure:

```bash
python /mnt/skills/public/pdf/scripts/extract_form_structure.py form.pdf structure.json
```

That gives exact `top`/`x0`/`x1`/`bottom` for every text label on the text-layer
forms (JD-5, JD-6). Place entry text just right of the label and just above the
ruled line. See `references/measuring.md` for the scanned-form procedure, which is
different - Note of Issue and DOH-2168 have no text layer and need pixel
measurement off a 200 dpi render.

## Reference files

- `references/intake-checklist.md` - everything to ask the user, in one list
- `references/case-schema.md` - every key in the case JSON and its allowed values
- `references/measuring.md` - how to re-derive coordinates when a form changes
- `assets/case-template.json` - a filled example to copy

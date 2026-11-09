# New York Divorce Form Skills

This project contains two Claude skills for filling out New York State uncontested joint divorce forms: one for cases without children under 21, and one for cases with children under 21.

I built this to make the form-filling process more organized. Case information is entered in a JSON file, and a Python filler places that information onto copies of the official court forms. It creates a separate filled PDF for each form in the packet.

## How It Works

The AI helps organize the case information and determine which answers belong on each form. A Python script handles the actual placement of text on the PDFs.

The text placement uses fixed coordinates instead of asking the AI to guess where each answer should go. This is important because the court forms have specific boxes and layouts. Even a small placement error can make a form difficult to use. Text is drawn as a real page overlay, not as annotations or form fields, so it prints and flattens correctly.

For cases with children, the child support figures are calculated, not typed in. `cssa.py` implements the Child Support Standards Act (DRL § 240(1-b)) with the figures in effect from March 1, 2026: the $193,000 income cap, the 17/25/29/31/35% percentages, the maintenance adjustment, the over-cap election, and the poverty and self-support-reserve floors. The same result feeds the Joint Affirmation (JD-3), the Findings and Judgment (JD-4), and the Child Support Summary (UCS-111), so the forms cannot disagree with each other.

## Current Features

- Fillers for both packets: no children (27 pages, 11 forms) and with children (47 pages, 13 forms)
- A CSSA child support calculator that prints a worksheet to confirm before any form is delivered
- Custody chart, parenting-time schedule, background check, maintenance, property, real estate, and fee sections
- The sideways-scanned RJI Addendum (UCS-840M) filled with rotated text
- Attachment pages when there are more children than a form has room for
- Case templates, including a complex example that exercises the harder branches
- Reference notes for every case field, the intake questions, and how the coordinates were measured
- Automated tests for the calculator and end-to-end filler runs

The project does not collect Social Security numbers. Those fields, along with signatures, notarization, the DOH-2168 race boxes, and information completed by the court, are left blank.

## Running the Project

This project requires Python 3, `pypdf`, and `reportlab`.

```bash
pip install -r requirements.txt
cp skills/ny-joint-divorce-with-children/assets/case-template.json case.json
```

Edit `case.json` with the case information, then run:

```bash
python skills/ny-joint-divorce-with-children/scripts/fill_divorce_forms.py \
  --case case.json --out out/
```

The with-children filler prints the CSSA worksheet and writes the eight initial-filing forms. Use `--forms all` for the whole packet, or a comma-separated list of form keys. To see the worksheet alone, run `scripts/cssa.py --case case.json`. The no-children filler works the same way from its own folder.

Every case field is explained in each skill's `references/case-schema.md`. The file `references/measuring.md` explains how the form coordinates were measured and how to update them if a court form changes.

To use one of these folders as a Claude skill, copy it into `~/.claude/skills/`.

## Tests

```bash
python -m pytest tests/
```

The tests check hand-worked CSSA cases and run the with-children filler end to end on both example cases. They check structure and guard rails, not placement: filled forms should always be rendered and looked at, because a change to the official PDF can move text out of place.

## Important Legal Notice

This project only copies information you provide onto court forms. It does not give legal advice, decide which forms are right for a case, or confirm that a packet is ready to file. The child support calculation is an estimate for the parties to confirm, not a substitute for the court's.

Before filing anything, check every page, confirm that the forms are the current New York State versions, and consider having a lawyer review them. You are responsible for the accuracy and completeness of all submitted forms. The sample case data is fictional.

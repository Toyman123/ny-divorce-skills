# NY Uncontested Joint Divorce Form Fillers

Claude skills that fill the New York State Uncontested Joint Divorce forms packets — with and without children — by overlaying typed answers onto the official blank court PDFs at measured field coordinates.

---

## How it works

The core design decision is that **the model never draws anything and never does arithmetic.** Filling a court form is a coordinate problem: every answer has to land inside a specific box on a specific page of a specific revision of an official PDF. So the placement lives in `scripts/fill_divorce_forms.py` as baked-in constants — a `PAGES` map of 0-based page ranges for each form, and per-field coordinates measured once against the real packet. The script extracts the relevant pages from the official blank PDF, draws text and checkbox marks with ReportLab at those coordinates, and merges the overlay into the page with pypdf. The result is real page content, not a PDF annotation layer, so it prints and flattens the way a clerk expects. Two coordinate systems coexist because the packet does: the text-layer forms (JD-5, JD-6, JD-3, JD-4) are measured in PDF points from the top of the page, while the scanned forms (Note of Issue, DOH-2168, and the sideways UCS-840M) are measured in pixels off a 200 dpi render and converted with a single `SCALE` constant. Re-measuring is a documented procedure in `references/measuring.md`, not a guessing game.

The same principle governs the child support math in the with-children skill, and it matters more there. Every CSSA figure — combined parental income, the pro-rata shares, the capped obligation, the over-cap election — comes out of `scripts/cssa.py`. The model is explicitly forbidden from hand-entering those numbers or accepting a bare figure from the user, and derived income rows are computed too (`G = B+C+D+E+F`, `H = A−G`) so the income table cannot contradict the support calculation. The worksheet appears twice in the packet at different levels of detail — headline numbers on JD-3, the full derivation on JD-4 ¶18 — and both are fed from the same `compute()` result, so the two forms are structurally incapable of disagreeing. If the spouses want a different amount, that is a *deviation*: a structured input with a stated reason, not an edit to the arithmetic. This is the whole argument for putting correctness-critical work in code rather than the prompt. Code is deterministic, diffable, and testable; the same case JSON produces byte-identical output every run, and when New York revises the income cap you change one constant instead of hoping the model remembers. A language model asked to do the same work fails *silently* — a transposed digit or a field nudged twenty points down the page looks exactly as confident as a correct one. What the model is genuinely good at is the part that stays in the prompt: conducting the intake, routing an answer to the right form when the user names the wrong one, and being explicit about what it refused to fill.

Because coordinate drift is invisible in the file and only shows up on the page, the skills require a **visual verification gate** before anything is delivered: render every filled page to PNG with `pypdfium2` and actually look at it, checking for text sitting on top of a printed label, X marks on the wrong checkbox, and text overrunning a cell border. Alongside that sit hard behavioral limits — never write a Social Security number (they are handwritten), never fill a signature line, never guess a substantive legal term like custody or debt allocation, and always close by listing what is still blank.

---

## Repository layout

```
skills/
  ny-joint-divorce-no-children/     # JD-2, JD-5, JD-6, UD-9, UD-13, DOH-2168, + post-judgment
    SKILL.md
    assets/blank-packet.pdf         # official NYS packet, effective 3/1/26
    assets/case-template.json       # fictional sample case
    references/                     # intake checklist, case schema, measuring guide
    scripts/fill_divorce_forms.py
  ny-joint-divorce-with-children/   # adds JD-3, JD-4, UCS-840M, UCS-111 + CSSA math
    SKILL.md
    assets/blank-packet.pdf         # official NYS packet, effective 3/1/26
```

> **Status:** the with-children skill is incomplete. It ships its `SKILL.md` and
> the official blank packet, but its `references/` and `scripts/` — including
> `cssa.py`, which does the child support math described above — are not yet in
> this repository, so it cannot be run as-is. One thing to check when restoring
> the script: `SKILL.md` describes the packet as 51 pages, but the bundled PDF
> reads as 50. Verify the `PAGES` map against this file before trusting any
> coordinate. The no-children skill is complete.

---

## Setup

Requires Python 3.9+.

```bash
pip install pypdf reportlab pypdfium2 pillow
```

Install as a Claude skill by copying a skill directory into your skills folder:

```bash
cp -r skills/ny-joint-divorce-no-children ~/.claude/skills/
```

## Usage

Copy the template, replace the values with the real case data, then run the filler:

```bash
cp skills/ny-joint-divorce-no-children/assets/case-template.json case.json
```

```bash
python skills/ny-joint-divorce-no-children/scripts/fill_divorce_forms.py --case case.json --out out/ --forms jd2,jd5,jd6,noi,doh
```

`--forms` defaults to the five core filing forms (`jd2,jd5,jd6,noi,doh`). Other keys: `rji`, `notify`, `entry`, `aff_judgment`, `aff_mail`, `aff_personal`. `--forms all` fills the entire packet. Each form is written as its own PDF, which is how clerks generally want them filed. `--packet` is optional — the official blank is bundled — and is only needed if New York publishes a newer revision.

Every key in the case JSON is documented in `references/case-schema.md`. Leave a value as `""` to leave that field blank on the form. **Do not put Social Security numbers in the case file.**

Filled output is ignored by git. Keep it that way — it contains real parties' personal information.

---

## Sample data is fictional

`assets/case-template.json` contains entirely invented sample data — Jane and John Doe at 123 Main Street, Anytown, with 555-01xx phone numbers and `EXAMPLE-000000` identifiers. It is a structural template showing every available key, not a real case. Any resemblance to actual people is unintended.

## Disclaimer

**This is not legal advice.** These skills transcribe information you provide onto court forms. They do not decide anything, and they cannot tell you whether a form is right for your situation.

Verify every generated document against the official forms before filing. Confirm you are using the current NYS revision — the packet here is effective 3/1/26, and the CSSA income cap is revised every two years. Fields the court supplies (index number, judge, stamped dates), all signatures, notarization, and Social Security numbers are intentionally left blank for you to complete by hand. Have an attorney review the output before it goes to a clerk.

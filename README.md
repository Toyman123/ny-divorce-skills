# NY uncontested joint divorce form fillers

Two Claude skills that fill out the New York State uncontested joint divorce
packets — one for cases with no children under 21, one for cases with them. You
give it the case details as JSON, it draws the answers onto the official blank
court PDFs and writes one filled PDF per form.

The design choice worth explaining is what the model isn't allowed to do. The
answers have to land inside specific boxes on a specific revision of a specific
form, and a model doing that fails silently — a field nudged twenty points down
the page looks exactly as confident as a correct one. So placement is hardcoded
coordinates in a script, and the model handles the intake: asking the right
questions, working out which form an answer belongs on, and saying what it left
blank.

## Using it

```bash
cp skills/ny-joint-divorce-no-children/assets/case-template.json case.json
# edit case.json — the template is a fictional Doe case showing every key
python skills/ny-joint-divorce-no-children/scripts/fill_divorce_forms.py \
  --case case.json --out out/
```

```
wrote 1-JD-2-Summons-FILLED.pdf
wrote 2-JD-5-Joint-Affirmation-FILLED.pdf
wrote 3-JD-6-Findings-Judgment-FILLED.pdf
wrote 4-Note-of-Issue-UD-9-FILLED.pdf
wrote 6-DOH-2168-Certificate-of-Dissolution-FILLED.pdf
```

That's the default set. `--forms` takes any of `jd2, jd5, jd6, noi, rji, doh,
notify, entry, aff_judgment, aff_mail, aff_personal`, or `all` for the whole
packet. Each form is written as its own PDF. `aff_mail` and `aff_personal` come
out unfilled by design — the script routes them through a no-op builder.

An empty string means "leave that field blank on the form", which is how you
handle anything the court fills in later. There are no fields for Social
Security numbers; they're meant to be written in by hand.

Every key is documented in `references/case-schema.md`, and
`references/measuring.md` covers re-deriving coordinates if a form changes.

## What's not done

**The with-children skill is a stub.** It has its `SKILL.md` and the blank
packet, and nothing else — no filler script, no `cssa.py`, no reference docs. So
it can't run. Its `SKILL.md` describes in detail how the child support
calculation works, but that's a description of code that isn't in this
repository. Read it as intent, not as something you can check.

**No tests.** None, not even a golden-file check. This is the real weakness:
coordinate drift is invisible unless you render the page and look at it, so
right now correctness depends on a human looking. A fixed case JSON plus a
checked-in expected PDF, diffed on every change, would catch that whole class of
bug.

**One open discrepancy.** The with-children `SKILL.md` describes its packet as
51 pages; the PDF in `assets/` reads as 50. I don't know which is right, and it
can't be settled without the missing script that maps page ranges to forms. If
that script turns up, check the page map before trusting any coordinate.

The sample data in `case-template.json` was replaced with placeholders and the
filler has not been run against it since.

## Running it

Python 3 and `pip install pypdf reportlab`. To use as a Claude skill, copy a
skill directory into `~/.claude/skills/`. The blank packets are bundled, so
there's nothing to download.

`references/measuring.md` additionally uses `pypdfium2` and `pillow` to render
pages to images while measuring coordinates. Not needed to fill forms.

## Stack

Python; `reportlab` draws the text, `pypdf` merges it into the page.

## Sample data is fake

`case-template.json` is Jane and John Doe at 123 Main Street, Anytown, with
555-01xx numbers and `EXAMPLE-000000` identifiers. It's a structural template
showing every available key, not a real case.

## Not legal advice

This transcribes what you type onto court forms. It doesn't decide anything and
it can't tell you whether a form is right for your situation. Check every page
against the official form before filing, confirm you're on the current NYS
revision, and have a lawyer review it. Signatures, notarization, SSNs, and the
fields the court supplies are left blank.

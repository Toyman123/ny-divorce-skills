# NY uncontested joint divorce form fillers

Two Claude skills that fill out the New York State uncontested joint divorce
packets — one for cases with no children under 21, one for cases with them.
You give it the case details as JSON, it draws the answers onto the official
blank court PDFs and writes one filled PDF per form.

I built this because filling the packet by hand is tedious and error-prone, and
because the obvious approach — have a model type into the PDF — is the wrong one.
The answers have to land inside specific boxes on a specific revision of a
specific form, and the child support figures have to be arithmetically right.
Models are bad at both, and worse, they're bad at them *silently*. A field nudged
twenty points down the page looks exactly as confident as a correct one. So the
placement is hardcoded coordinates in a script and the model's job is the intake:
asking the right questions, figuring out which form an answer belongs on, and
being explicit about what it left blank.

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
packet. The last two come out blank on purpose — their checkboxes are all child
support documents, so they don't apply to a no-children case. Separate files
because clerks generally want them filed individually.

Empty string means "leave that field blank on the form", which is how you handle
anything the court fills in later. Don't put Social Security numbers in the case
file; there are no fields for them and they're meant to be written by hand.

Every key is documented in `references/case-schema.md`. `references/measuring.md`
covers re-deriving coordinates when New York revises a form, which they do.

## What's not done

**The with-children skill is a stub.** It has its `SKILL.md` and the blank
packet, and that's it — no filler script, no `cssa.py`, no reference docs. The
child support calculator is the part of this I'd actually want to show someone
and it isn't here — I haven't tracked those files down yet. Everything the
`SKILL.md` says about how the CSSA math works is a description of code that
isn't in this repo, so take it as intent, not as something you can read.

**No tests.** None, not even a golden-file check. This is the real weakness:
coordinate drift is invisible unless you render the page and look at it, and
right now "look at it" means a human looking at it. A fixed case JSON plus a
checked-in expected PDF, diffed on every change, would catch the whole class of
bug. Haven't written it.

**Also worth knowing:** the with-children `SKILL.md` describes its packet as 51
pages, and the PDF in `assets/` reads as 50. I don't know which is right and I
can't check without the script that maps page ranges to forms. If you restore
that script, verify the page map before trusting a single coordinate.

The no-children skill I've run and the output looked right. I have not run it
since scrubbing the sample data out of the template, so if it breaks on the Doe
case that's why.

## Running it

Python 3, plus `pip install pypdf reportlab`. To use as a Claude skill, copy a
skill directory into `~/.claude/skills/`. The blank packets are bundled, so
there's nothing to download.

`references/measuring.md` also uses `pypdfium2` and `pillow` for rendering pages
to images while measuring coordinates — not needed to just fill forms.

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
revision, and have a lawyer look at it. Signatures, notarization, SSNs, and the
fields the court supplies are all deliberately left blank.

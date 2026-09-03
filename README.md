# New York Divorce Form Skills

This project contains two Claude skills for filling out New York State uncontested joint divorce forms. One skill is for cases without children under 21, and the other is intended for cases with children under 21.

I built this to make the form-filling process more organized. Case information is entered in a JSON file, and the working skill places that information onto copies of the official court forms. It creates a separate filled PDF for each form in the packet.

## How It Works

The AI helps organize the case information and determine which answers belong on each form. A Python script handles the actual placement of text on the PDFs.

The text placement uses fixed coordinates instead of asking the AI to guess where each answer should go. This is important because the court forms have specific boxes and layouts. Even a small placement error can make a form difficult to use.

## Current Features

- A case template showing the available fields
- Support for the no-children joint divorce packet
- One filled PDF created for each selected form
- Fixed placement for answers on the official form layouts
- Blank fields for information that must be added later
- Reference notes explaining the case data and form coordinates

The project does not collect Social Security numbers. Those fields, along with signatures, notarization, and information completed by the court, are left blank.

## Running the Project

This project requires Python 3, `pypdf`, and `reportlab`.

```bash
pip install pypdf reportlab
cp skills/ny-joint-divorce-no-children/assets/case-template.json case.json
```

Edit `case.json` with the case information, then run:

```bash
python skills/ny-joint-divorce-no-children/scripts/fill_divorce_forms.py \
  --case case.json --out out/
```

The completed forms will be saved in the `out` folder. You can use the `--forms` option to choose individual forms or use `all` for the full available packet.

Every case field is explained in `references/case-schema.md`. The file `references/measuring.md` explains how the form coordinates were measured and how to update them if a court form changes.

To use one of these folders as a Claude skill, copy it into `~/.claude/skills/`.

## Project Status

The skill for cases without children is the working part of this project. The skill for cases with children is currently a stub. It includes planning instructions and a blank packet, but it does not include the Python filler script or the other files needed to run it.

There are no automated tests yet. Filled forms should always be opened and checked carefully because a change to the official PDF can cause text to move out of place. The sample case data is fictional and is only included to show the expected format.

## Important Legal Notice

This project only copies information you provide onto court forms. It does not give legal advice, decide which forms are right for a case, or confirm that a packet is ready to file.

Before filing anything, check every page, confirm that the forms are the current New York State versions, and consider having a lawyer review them. You are responsible for the accuracy and completeness of all submitted forms.

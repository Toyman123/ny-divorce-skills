"""End-to-end runs of the with-children filler. Run: python -m pytest tests/

These check structure (every form written, right page counts, guard rails).
They do NOT replace looking at the rendered pages - see references/measuring.md.
"""
import copy
import json
import os
import subprocess
import sys

import pytest
from pypdf import PdfReader

SKILL = os.path.join(os.path.dirname(__file__), '..', 'skills', 'ny-joint-divorce-with-children')
FILLER = os.path.join(SKILL, 'scripts', 'fill_divorce_forms.py')
PAGES = {'1-JD-2-Summons-FILLED.pdf': 2, '2-JD-3-Joint-Affirmation-FILLED.pdf': 17,
         '3-JD-4-Findings-Judgment-FILLED.pdf': 18, '4-Note-of-Issue-UD-9-FILLED.pdf': 1,
         '5-RJI-UD-13-FILLED.pdf': 1, '6-RJI-Addendum-UCS-840M-FILLED.pdf': 1,
         '7-DOH-2168-Certificate-of-Dissolution-FILLED.pdf': 1,
         '8-UCS-111-Child-Support-Summary-FILLED.pdf': 1, '9-Notification-Letter-FILLED.pdf': 1,
         '10-Notice-of-Entry-FILLED.pdf': 1, '11-Affirmation-of-Service-of-Judgment-FILLED.pdf': 1,
         '12-Affirmation-of-Service-by-Mail-BLANK.pdf': 1, '13-Affirmation-of-Personal-Delivery-BLANK.pdf': 1}


def run(case, out, *extra):
    return subprocess.run([sys.executable, FILLER, '--case', case, '--out', str(out), *extra],
                          capture_output=True, text=True)


def load(name):
    return json.load(open(os.path.join(SKILL, 'assets', name)))


@pytest.mark.parametrize('example', ['case-template.json', 'case-example-complex.json'])
def test_every_form_written(tmp_path, example):
    p = run(os.path.join(SKILL, 'assets', example), tmp_path, '--forms', 'all')
    assert p.returncode == 0, p.stderr
    assert 'CSSA WORKSHEET' in p.stdout
    for name, n in PAGES.items():
        assert len(PdfReader(tmp_path / name).pages) == n, name


def test_default_is_the_eight_filing_forms(tmp_path):
    p = run(os.path.join(SKILL, 'assets', 'case-template.json'), tmp_path)
    assert p.returncode == 0, p.stderr
    assert sorted(os.listdir(tmp_path)) == sorted(list(PAGES)[:8])


def test_extra_children_get_attachment_pages(tmp_path):
    d = load('case-template.json')
    kid = d['children'][0]
    d['children'] = [dict(kid, first=f'KID{i}', dob=f'0{i + 1}/01/{2010 + i}') for i in range(7)]
    case = tmp_path / 'c.json'
    case.write_text(json.dumps(d))
    p = run(str(case), tmp_path / 'out', '--forms', 'jd3,jd4,rji_addendum')
    assert p.returncode == 0, p.stderr
    assert len(PdfReader(tmp_path / 'out' / '2-JD-3-Joint-Affirmation-FILLED.pdf').pages) == 18
    assert len(PdfReader(tmp_path / 'out' / '3-JD-4-Findings-Judgment-FILLED.pdf').pages) == 19
    assert len(PdfReader(tmp_path / 'out' / '6-RJI-Addendum-UCS-840M-FILLED.pdf').pages) == 2


def test_existing_support_order_skips_cssa(tmp_path):
    d = load('case-template.json')
    d['child_support']['existing_order'] = {'payor': 'spouse2', 'amount': '800', 'frequency': 'month',
                                            'county': 'ANY', 'docket': 'F-1', 'date': '01/02/2025'}
    case = tmp_path / 'c.json'
    case.write_text(json.dumps(d))
    p = run(str(case), tmp_path / 'out')
    assert p.returncode == 0, p.stderr
    assert 'CSSA WORKSHEET' not in p.stdout


@pytest.mark.parametrize('mutate, message', [
    (lambda d: d['children'][0].update(dob='01/01/2004'), 'under 21'),
    (lambda d: d.update(children=[]), 'no-children'),
])
def test_guard_rails_write_nothing(tmp_path, mutate, message):
    d = copy.deepcopy(load('case-template.json'))
    mutate(d)
    case = tmp_path / 'c.json'
    case.write_text(json.dumps(d))
    p = run(str(case), tmp_path / 'out')
    assert p.returncode != 0 and message in p.stderr
    assert not (tmp_path / 'out').exists()


def test_scu_form_key_explains_ud8a(tmp_path):
    p = run(os.path.join(SKILL, 'assets', 'case-template.json'), tmp_path, '--forms', 'scu')
    assert p.returncode != 0 and 'UD-8a' in p.stderr


def test_examples_hold_no_ssn():
    for name in ('case-template.json', 'case-example-complex.json'):
        text = open(os.path.join(SKILL, 'assets', name)).read().lower()
        assert 'ssn' not in text and 'social_security' not in text

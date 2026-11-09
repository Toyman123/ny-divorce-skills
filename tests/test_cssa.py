"""Hand-worked CSSA cases. Run: python -m pytest tests/"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills',
                                'ny-joint-divorce-with-children', 'scripts'))
from cssa import compute  # noqa: E402


def case(s1, s2, kids=1, custodial='spouse2', **cs):
    inc = lambda v: {'A': v[0], 'C': v[1] if len(v) > 1 else 0, 'D': v[2] if len(v) > 2 else 0}
    return {'children': [{}] * kids, 'income': {'spouse1': inc(s1), 'spouse2': inc(s2)},
            'maintenance': cs.pop('maintenance', {'type': 'none'}),
            'child_support': {'custodial_parent': custodial, 'frequency': 'month', **cs}}


def test_two_children_standard():
    # S1 net 73,880, S2 net 36,940; combined 110,820 x 25% = 27,705; S1 share 2/3
    r = compute(case((80000, 4960, 1160), (40000, 2480, 580), kids=2))
    assert r['combined'] == 110820
    assert r['combined_obligation'] == 27705
    assert r['share_pct'] == {'spouse1': 66.67, 'spouse2': 33.33}
    assert r['presumptive_annual'] == 18470
    assert r['presumptive_per_payment'] == 1539.17
    assert r['low_income'] is None


def test_self_support_reserve_floor():
    # NCP 20,000 of 50,000; 8,500 x 40% = 3,400; 16,600 left: above poverty, below SSR
    r = compute(case((20000,), (30000,)))
    assert r['low_income'] == 'self_support_reserve'
    assert r['presumptive_annual'] == 600          # greater of $50/mo or income - SSR (< 0)


def test_poverty_floor():
    # NCP 16,000 of 46,000; 7,820 x 34.8% = 2,720; 13,280 left < 15,960
    r = compute(case((16000,), (30000,)))
    assert r['low_income'] == 'poverty'
    assert r['presumptive_annual'] == 300           # $25 / month


def test_over_cap_apply_and_not_apply():
    applied = compute(case((300000,), (0,), over_cap='apply'))
    assert applied['ncp_capped'] == 32810           # 193,000 x 17%
    assert applied['ncp_over_cap'] == 18190         # 107,000 x 17%
    assert applied['presumptive_annual'] == 51000
    capped = compute(case((300000,), (0,), over_cap='not_apply'))
    assert capped['presumptive_annual'] == 32810


def test_maintenance_moves_income():
    r = compute(case((100000,), (20000,), maintenance={
        'type': 'in_form', 'payor': 'spouse1', 'amount': 1000, 'frequency': 'month'}))
    assert r['adjusted'] == {'spouse1': 88000, 'spouse2': 32000}


def test_five_plus_children_and_custodial_spouse1():
    r = compute(case((30000,), (90000,), kids=6, custodial='spouse1'))
    assert r['percentage'] == 0.35 and r['non_custodial'] == 'spouse2'
    assert r['presumptive_annual'] == round(120000 * 0.35 * 0.75, 2)


def test_deviation_requires_reason_and_amount():
    with pytest.raises(ValueError):
        compute(case((80000,), (40000,), deviate=True, agreed_amount=500))
    r = compute(case((80000,), (40000,), deviate=True, agreed_amount=500,
                     deviation_reason='Spouse 1 pays the children\'s tuition directly'))
    assert r['agreed_annual'] == 6000


def test_rows_g_and_h_are_derived():
    r = compute(case((80000, 4960, 1160), (40000,)))
    assert r['income_rows']['spouse1']['G'] == 6120
    assert r['income_rows']['spouse1']['H'] == 73880

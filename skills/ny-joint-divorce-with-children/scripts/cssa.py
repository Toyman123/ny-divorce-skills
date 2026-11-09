#!/usr/bin/env python3
"""
New York Child Support Standards Act (CSSA) calculator - DRL § 240(1-b).

    python cssa.py --case case.json          # print the worksheet
    python cssa.py --case case.json --json   # machine-readable result

Importable: `from cssa import compute, worksheet`.

Figures in effect March 1, 2026 through February 28, 2028 (the packet prints
the $193,000 cap). NYS revises CAP every two years and the poverty guideline /
self-support reserve every March 1. If the packet's printed cap differs from
CAP, the forms win - update the constants.

The result is an ESTIMATE for the user to confirm, never a substitute for the
court's calculation. It does not do maintenance guideline math; maintenance
comes from the case file as an agreed amount.
"""
import argparse
import json
import sys

CAP = 193_000                 # combined parental income cap (eff. 3/1/26)
POVERTY = 15_960              # HHS poverty guideline, 1-person household (2026)
SSR = 21_546                  # self-support reserve = 135% of POVERTY (eff. 3/1/26)
PCT = {1: 0.17, 2: 0.25, 3: 0.29, 4: 0.31}
PCT_5_PLUS = 0.35
PER_YEAR = {'week': 52, 'two_weeks': 26, 'month': 12}


def _num(v):
    if v in (None, ''):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace('$', '').replace(',', '').strip() or 0)


def percentage(n_children):
    if n_children < 1:
        raise ValueError('CSSA needs at least one child under 21')
    return PCT.get(n_children, PCT_5_PLUS)


def income_rows(inc):
    """JD-3 income table. Rows A-F come from the user; G and H are derived."""
    a, b, c, d, e, f = (_num(inc.get(k)) for k in 'ABCDEF')
    g = b + c + d + e + f
    return {'A': a, 'B': b, 'C': c, 'D': d, 'E': e, 'F': f, 'G': g, 'H': a - g}


def annual_maintenance(case):
    """Agreed maintenance between THESE spouses, annualised, as (payor, amount)."""
    m = case.get('maintenance', {})
    if not isinstance(m, dict) or m.get('type') in (None, '', 'none'):
        return None, 0.0
    per = m.get('frequency')
    if per not in PER_YEAR:
        raise ValueError("maintenance.frequency must be week, two_weeks or month for the CSSA adjustment")
    return m['payor'], _num(m['amount']) * PER_YEAR[per]


def compute(case):
    cs = case['child_support']
    custodial = cs['custodial_parent']
    if custodial not in ('spouse1', 'spouse2'):
        raise ValueError('child_support.custodial_parent must be spouse1 or spouse2')
    ncp = 'spouse2' if custodial == 'spouse1' else 'spouse1'
    n = len(case['children'])
    pct = percentage(n)

    rows = {s: income_rows(case['income'][s]) for s in ('spouse1', 'spouse2')}
    adjusted = {s: rows[s]['H'] for s in rows}
    m_payor, m_amt = annual_maintenance(case)
    if m_payor:
        recipient = 'spouse2' if m_payor == 'spouse1' else 'spouse1'
        adjusted[m_payor] -= m_amt
        adjusted[recipient] += m_amt
    adjusted = {s: max(v, 0.0) for s, v in adjusted.items()}

    combined = adjusted['spouse1'] + adjusted['spouse2']
    if combined <= 0:
        raise ValueError('combined parental income is zero - check the income table')
    capped = min(combined, CAP)
    combined_obligation = round(capped * pct, 2)
    share = {s: adjusted[s] / combined for s in adjusted}
    share_pct = {s: round(share[s] * 100, 2) for s in share}
    ncp_capped = round(combined_obligation * share[ncp], 2)

    over_cap_income = max(combined - CAP, 0.0)
    over_cap_election = cs.get('over_cap', 'not_apply') if over_cap_income else 'not_apply'
    ncp_over_cap = round(over_cap_income * pct * share[ncp], 2) if over_cap_election == 'apply' else 0.0

    basic = ncp_capped + ncp_over_cap
    low_income = None
    ncp_income = adjusted[ncp]
    if ncp_income - basic < POVERTY:
        basic, low_income = 300.0, 'poverty'                       # $25 / month
    elif ncp_income - basic < SSR:
        basic, low_income = round(max(600.0, ncp_income - SSR), 2), 'self_support_reserve'

    freq = cs.get('frequency', 'month')
    if freq not in PER_YEAR:
        raise ValueError('child_support.frequency must be week, two_weeks or month')
    presumptive_per_payment = round(basic / PER_YEAR[freq], 2)

    deviate = bool(cs.get('deviate'))
    if deviate:
        if not str(cs.get('deviation_reason', '')).strip():
            raise ValueError('child_support.deviate is true but deviation_reason is empty')
        agreed_per_payment = _num(cs.get('agreed_amount'))
        if agreed_per_payment <= 0:
            raise ValueError('child_support.deviate is true but agreed_amount is missing')
        agreed_annual = round(agreed_per_payment * PER_YEAR[freq], 2)
    else:
        agreed_per_payment, agreed_annual = presumptive_per_payment, round(basic, 2)

    return {
        'n_children': n, 'percentage': pct, 'custodial': custodial, 'non_custodial': ncp,
        'income_rows': rows, 'maintenance_payor': m_payor, 'maintenance_annual': m_amt,
        'adjusted': {s: round(v, 2) for s, v in adjusted.items()},
        'combined': round(combined, 2), 'over_cap': combined > CAP,
        'over_cap_election': over_cap_election, 'combined_obligation': combined_obligation,
        'share_pct': share_pct, 'ncp_capped': ncp_capped, 'ncp_over_cap': ncp_over_cap,
        'low_income': low_income, 'presumptive_annual': round(basic, 2),
        'frequency': freq, 'presumptive_per_payment': presumptive_per_payment,
        'deviate': deviate, 'agreed_per_payment': round(agreed_per_payment, 2),
        'agreed_annual': agreed_annual,
        'higher_income': 'spouse1' if adjusted['spouse1'] >= adjusted['spouse2'] else 'spouse2',
    }


def money(v):
    return f'{v:,.2f}'


def worksheet(r):
    lab = {'spouse1': 'Spouse 1', 'spouse2': 'Spouse 2'}
    per = {'week': 'week', 'two_weeks': 'two weeks', 'month': 'month'}[r['frequency']]
    out = ['CSSA WORKSHEET - ESTIMATE, CONFIRM BEFORE FILING', '']
    out.append(f"{'':38}{'Spouse 1':>14}{'Spouse 2':>14}")
    names = {'A': 'A Gross income', 'B': 'B NYC/Yonkers tax', 'C': 'C Social Security tax',
             'D': 'D Medicare tax', 'E': 'E Maintenance to other spouse',
             'F': 'F Support for other children', 'G': 'G Total deductions (B-F)',
             'H': 'H Net (A - G)'}
    for k in 'ABCDEFGH':
        out.append(f"{names[k]:38}{money(r['income_rows']['spouse1'][k]):>14}"
                   f"{money(r['income_rows']['spouse2'][k]):>14}")
    if r['maintenance_payor']:
        out.append(f"Maintenance between spouses: {lab[r['maintenance_payor']]} pays "
                   f"${money(r['maintenance_annual'])}/yr (deducted from payor, added to recipient)")
    out.append(f"{'Adjusted gross income':38}{money(r['adjusted']['spouse1']):>14}"
               f"{money(r['adjusted']['spouse2']):>14}")
    out.append(f"{'Pro rata share':38}{r['share_pct']['spouse1']:>13.2f}%{r['share_pct']['spouse2']:>13.2f}%")
    out += ['',
            f"Combined parental income:          ${money(r['combined'])}",
            f"Children: {r['n_children']}  ->  {round(r['percentage'] * 100)}%",
            f"Combined obligation (up to ${CAP:,}): ${money(r['combined_obligation'])} / yr",
            f"Custodial parent: {lab[r['custodial']]}; non-custodial payor: {lab[r['non_custodial']]}",
            f"Non-custodial share up to cap:     ${money(r['ncp_capped'])} / yr"]
    if r['over_cap']:
        out.append(f"Income over cap - election: {r['over_cap_election']}; "
                   f"share on excess ${money(r['ncp_over_cap'])} / yr")
    if r['low_income']:
        out.append(f"LOW-INCOME ADJUSTMENT applied ({r['low_income']}): "
                   f"poverty ${POVERTY:,}, self-support reserve ${SSR:,}")
    out += [f"PRESUMPTIVE child support:         ${money(r['presumptive_annual'])} / yr"
            f" = ${money(r['presumptive_per_payment'])} every {per}"]
    if r['deviate']:
        out.append(f"AGREED (DEVIATION):                ${money(r['agreed_annual'])} / yr"
                   f" = ${money(r['agreed_per_payment'])} every {per}")
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--case', required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    r = compute(json.load(open(a.case)))
    print(json.dumps(r, indent=2) if a.json else worksheet(r))


if __name__ == '__main__':
    sys.exit(main())

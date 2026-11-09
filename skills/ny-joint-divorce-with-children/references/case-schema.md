# Case JSON schema (with children)

Copy `assets/case-template.json` (simple) or `assets/case-example-complex.json`
(every harder branch) and replace the values. `""` leaves a field blank.
**Never put a Social Security number anywhere in this file.**

Spouse choices are always `"spouse1"` / `"spouse2"`. Frequencies are `"week"`,
`"two_weeks"`, `"month"` (maintenance also allows `"other"` + `other_text`).
Dates are `MM/DD/YYYY` unless noted.

## Top level

| Key | Meaning |
|---|---|
| `as_of` | Date used to compute each child's age (default: today). Use the filing date. |
| `county`, `index_no` | Filing county; index number once purchased. |
| `date_summons_filed`, `date_summons_served` | Usually the same day for a joint filing. |
| `residency` | `two_years`, `one_year_married_ny`, `one_year_lived_ny`, `one_year_breakdown_ny`, `both_in_ny` |
| `military` | List of spouses in the military, e.g. `["spouse2"]`; `[]` = neither. |
| `marriage_date`, `marriage_place` | JD-3/JD-4 wording ("city, state, country"). |
| `marriage_city/county/state`, `marriage_date_month/day/year` | DOH-2168 boxes 11-12. |
| `separated_month`, `separated_year` | DOH-2168 box 12B. |
| `ceremony` | `civil` or `religious`. |
| `barriers` | Religious only: `taken` (steps taken) or `waived`. |
| `children_born` | DOH-2168 13A, children ever born alive of this marriage (default: number listed). |
| `marital_home` | `"not_applicable"` or `{occupant, address, until}` or `{occupant, address, as_follows}` (`until` takes a phrase). |
| `property` | `divided`, `separate_agreement`, `in_form` (+ `property_text`, 3 lines). |
| `real_estate` | `"not_applicable"` or `{from, address, by_date}`: `from` transfers title to the other spouse. |
| `pensions` | `qdro`, `separate_agreement`, `waive`. |
| `debt` | `not_applicable`, `separate_agreement`, `in_form` (+ `debt_text`, 3 lines). |
| `fees` | `"each_own"` or `{payor, amount, experts}`. |
| `settlement_agreement` | `null` or `{day: "1st", month_year: "April 2026"}` (JD-4 para 12B). |
| `property_allocation` | UCS-111 N: `{plaintiff_pct, defendant_pct}` or `{}`. |
| `serves_judgment` | Who serves the judgment with notice of entry. |
| `note_of_issue_filed_by` | `plaintiff`, `plaintiff_attorney`, `defendant`. |
| `issue_joined` | `waiver` (normal) or `default`. |
| `decree_granted_to`, `legal_grounds`, `preparer_name` | DOH-2168 / RJI. |
| `ancillary_relief` | JD-2 boxes: `none, maintenance_waived, property_waived, property, maintenance, retirement, child_support, custody, visitation, fees, former_name, order_of_protection, marital_home, court_orders, other`. |

## `spouse1` / `spouse2`

Names (`first`, `middle`, `last`, `birth_name`), `address` (one line),
`address_short` (DOH), `address_parts` `{street, city, state, zip}` (RJI,
UCS-840M, mailing blocks), `address_history` (up to 3 past addresses, same
shape, UCS-840M), `prior_names` (up to 3 `{last, first}`, UCS-840M),
`dob_month/day/year`, `birth_state` (a STATE for US births), `sex` (`M`/`F`,
optional), `residence_state`, `residence_county`, `locality_type`
(`CITY`/`TOWN`/`VILLAGE`), `locality_name`, `within_limits` (`YES`/`NO`),
`if_no_town`, `phone`, `on_public_assistance`, `represented` + attorney
fields (`attorney_name`, `attorney_address_line1/2`, `attorney_address_short`,
`attorney_phone`, `attorney_fax`), health plan fields (`health_plan` = `NONE`
if none), `former_last_name`, `marriage_number`, `prior_ended_death`,
`prior_ended_divorce` (`NONE` checks the box), `education_box` (0-17 total
years; bachelor's = 16).

There is no race key: DOH-2168 boxes 15/19 are never filled.

## `children` (every child under 21; the filler sorts under-18 vs 18-20)

`first`, `middle`, `last`, `dob`, `sex`, `address`, `lives_with`,
`relationship`, `public_assistance`, `legal_custody` and `physical_custody`
(`joint`/`spouse1`/`spouse2`; used only for under-18s).
Capacity: JD-3 3 + 3, JD-4 6, UCS-840M 5. Extra children go on an
auto-generated attachment page and the "additional children" box is checked.

## `custody`

`type`: `order` (+ `order_county`, `order_docket`, `order_date`), `agreement`
(+ `agreement_date`), or `none` (agreed in the JD-3 chart).
`parenting_time`: `attached` or `schedule` (+ `parenting_time_schedule`, 4
lines on JD-3, 3 on JD-4; + `visitation_parent`).

## `income` (JD-3 table, last year)

Rows `A`-`F` per spouse: A gross, B NYC/Yonkers tax, C Social Security, D
Medicare, E maintenance paid to a *different* spouse, F support for other
children. **G and H are computed; never supply them.**

## `maintenance`

`{"type": "none"}` or `type` `agreement` / `in_form` with `payor`, `amount`,
`frequency` (+ `other_text`). `agreement`: `agreement_date`, `day_of`,
`duration_years`, `duration_months`. `in_form`: `start`, `end`,
`payment_method` (`direct`, `income_deduction`, `scu`). Optional `guideline`
`{payor, amount, years_married, min_years, min_months, max_years, max_months}`
from the court's maintenance calculator. Maintenance between the spouses is
moved between their incomes before the CSSA calculation.

## `child_support`

| Key | Meaning |
|---|---|
| `custodial_parent` | Child-support custodial parent (equal time: the lower earner). |
| `scu` | `{who: spouse1/spouse2/both, status: requesting/applied/receives/declines}` |
| `existing_order` | `null`, or a Family Court order to continue: `{payor, amount, frequency, county, docket, date}`. Skips the CSSA pages. |
| `agreement` | `in_form` or `separate` (+ `agreement_date`). |
| `paid_to` | `spouse1`, `spouse2`, `other` (+ `paid_to_other_name`), `scu`. |
| `frequency` | Payment frequency. |
| `over_cap` | Combined income over $193,000: `apply` or `not_apply` the percentage to the excess. |
| `deviate` | `false`, or `true` with `agreed_amount` (per payment), `deviation_reason`, `court_deviation_reason`. |
| `income_deduction` | `issue`, `alternative`, `good_cause` (+ `good_cause_reason`). |
| `child_care` | `{spouse1: {pct, amount, frequency}, spouse2: {...}}` (omit a spouse who pays none). |
| `education` | `{spouse1: [{for, amount, pct}], spouse2: [...]}`, up to 3 each. |
| `health` | `{covered_by: state/spouse1/spouse2, premium, premium_frequency, spouse1_pct, spouse2_pct, unreimbursed: {spouse1_pct, spouse2_pct}, qmcso}` |

## `background` (children under 18 only)

`orders_of_protection`: up to 3 `{against, county, court, docket}`.
`abuse_neglect`: docket + county text, or `""`.
`sex_offender`: `{}` or `{spouse1: {id, dob, names}}`.
JD-4 para 15 ("no allegations") is checked only when both of the first two are empty.

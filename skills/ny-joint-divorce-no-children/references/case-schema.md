# Case JSON schema

Any value left as `""` is skipped - nothing is drawn. Booleans are real JSON booleans.

## Top level
| key | values |
|---|---|
| `county` | filing county, all caps |
| `index_no`, `date_summons_filed`, `date_summons_served` | strings, often `""` |
| `marriage_date` | as it should read on JD-5/JD-6, e.g. `03/03/2010` |
| `marriage_place` | free text for JD-5/JD-6, e.g. `ANYTOWN, NEW YORK, USA` |
| `marriage_city`, `marriage_county`, `marriage_state` | separate cells on DOH-2168 |
| `marriage_date_month/day/year`, `separated_month`, `separated_year` | DOH-2168 cells |
| `ceremony` | `civil` or `religious` |
| `residency` | `two_years`, `one_year_married_ny` (JD-6) / `one_year_resident` (JD-5), `one_year_breakdown_ny`, `both_in_ny` |
| `military` | boolean |
| `children_born`, `children_under_18` | strings, `"0"` for a no-children case |
| `maintenance` | `none` (only value wired up; anything else leaves the section blank) |
| `marital_home` | `not_applicable` |
| `property` | `already_divided`, `separate_agreement`, `no_separate_agreement` |
| `property_text` | the write-in clause, used only with `no_separate_agreement` |
| `real_estate` | `not_applicable` |
| `pensions` | `waive` |
| `debt` | `not_applicable`, `separate_agreement`, `agree_that`, or `""` to leave blank |
| `fees` | `each_own` |
| `settlement_agreement` | boolean; drives JD-6 ¶6 Box A vs Box B |
| `serves_judgment` | `spouse1` or `spouse2` |
| `note_of_issue_filed_by` | `plaintiff`, `plaintiff_attorney`, `defendant` |
| `issue_joined` | `waiver` or `default` |
| `income` | `{"spouse1": {...}, "spouse2": {...}}` with keys `A`-`H` |
| `decree_granted_to` | usually `PLAINTIFF` |
| `legal_grounds` | e.g. `DRL 170(7) IRRETRIEVABLE BREAKDOWN` |
| `preparer_name` | printed on DOH-2168 box 26 above the signature caret |

## Per spouse (`spouse1` = Plaintiff, `spouse2` = Defendant)
`first`, `middle`, `last`, `birth_name`, `address` (long form for JD-5/JD-6),
`address_short` (fits the DOH-2168 cell), `dob_month`, `dob_day`, `dob_year`,
`birth_state`, `sex`, `residence_state`, `residence_county`,
`locality_type` (`CITY`/`TOWN`/`VILLAGE`), `locality_name`,
`within_limits` (`YES`/`NO`), `if_no_town`, `phone`,
`on_public_assistance` (boolean), `represented` (boolean),
`attorney_name`, `attorney_address_line1`, `attorney_address_line2`,
`attorney_address_short`, `attorney_phone`, `attorney_fax`,
`health_plan`, `health_plan_address`, `health_plan_id`, `health_plan_admin`,
`former_last_name`, `race`, `marriage_number`,
`prior_ended_death`, `prior_ended_divorce` (`NONE` checks the NONE box),
`education_box` (13-17; a bachelor's is 16).

There is deliberately no SSN key.

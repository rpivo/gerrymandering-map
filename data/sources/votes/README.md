# Vote totals transcribed from official reports

Official results the pipeline uses as inputs where the precinct data falls short. Each file is copied by hand from a government PDF, because the pipeline doesn't read PDFs. Each is also listed in `data/sources/sources.csv` with the PDF's URL and checksum, so the methodology page credits it.

## `nj-2024-president-by-county.csv`

2024 presidential votes for Harris and Trump in each of New Jersey's 21 counties, from the New Jersey Division of Elections' "Official List, Candidates for President, General Election 11/05/2024", a public government record.

- URL: https://www.nj.gov/state/elections/assets/pdf/election-results/2024/2024-official-general-results-president.pdf
- Downloaded 2026-11-05, SHA-256 `c216c561d1f8da3fdbdbbf67a1e22198b757188fac64f6328f54ce03fcae0e0b`
- Counties sum to the report's statewide totals: Harris 2,220,713, Trump 1,968,215 (a test checks this).

Why: MIT's 2024 precinct file has no early-voting rows for Mercer County (about 24% of its votes) and is 2% to 3% short in Union and Warren. `python -m gerry votes` scales each New Jersey county's precinct votes, party by party, to these totals.

## `tx-planc2333-president-2024.csv`

2024 presidential votes (Harris, Trump) for each of Texas's 38 districts under PLANC2333, the map used in 2026, from the Texas Legislative Council's "Election Analysis for Congressional Districts, PLANC2333, 2024 General Election" (red206, dated 08/18/2025), a public government record. The Council recounts precinct results onto the new districts.

- URL: https://data.capitol.texas.gov/dataset/748c952b-e926-4f44-8d01-a738884b3ec8/resource/94a2fff0-39ca-46f9-9e40-dd72addde245/download/planc2333_r206_election24g.pdf
- Downloaded 2026-11-05, SHA-256 `bb1c1f6b93ee28545fbf985d494ef6c4b34dac1107e868223b3ee92bc2d4e9be`
- Districts sum to the report's statewide line, the same as for the 2024 map: Harris 4,835,134, Trump 6,393,403 (a test checks this).

## `nc-s249-president-2024.csv`

2024 presidential votes (Harris, Trump) for each of North Carolina's 14 districts under S249, 2nd Edition, from the North Carolina General Assembly's StatPack, "2024 Election Contest Report - US President" (generated 10/20/2025), a public government record. The 2nd Edition was the last edition before the bill was ratified as S.L. 2025-95 on 10/22/2025, the map used in 2026. The StatPack leaves out the State Board of Elections' administrative precincts, so its totals are about 0.05% below the certified count.

- URL: https://webservices.ncleg.gov/ViewBillDocument/2025/7591/0/Edition%202%20-%20StatPack%20Report
- Downloaded 2026-11-05, SHA-256 `291186cad4898c6d08bd3ca58f93e87ad4c319c06a2d217ad5ed1c0cad355b40`
- Districts sum to the report's total line: Harris 2,713,609, Trump 2,896,941 (a test checks this).
- Cross-check: districts 2 and 4 to 14 kept their 2024 lines. The MIT precinct join on those lines agrees within 0.3 points for 8 of them and within 1.2 points for all (North Carolina reports 15% of its votes in county-wide early-voting rows, which the join can only split approximately).

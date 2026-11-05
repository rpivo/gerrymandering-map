# Vote totals transcribed from official reports

Official results the pipeline uses as inputs where the precinct data falls short. Each file is copied by hand from a government PDF, because the pipeline doesn't read PDFs. Each is also listed in `data/sources/sources.csv` with the PDF's URL and checksum, so the methodology page credits it.

## `nj-2024-president-by-county.csv`

2024 presidential votes for Harris and Trump in each of New Jersey's 21 counties, from the New Jersey Division of Elections' "Official List, Candidates for President, General Election 11/05/2024", a public government record.

- URL: https://www.nj.gov/state/elections/assets/pdf/election-results/2024/2024-official-general-results-president.pdf
- Downloaded 2026-11-05, SHA-256 `c216c561d1f8da3fdbdbbf67a1e22198b757188fac64f6328f54ce03fcae0e0b`
- Counties sum to the report's statewide totals: Harris 2,220,713, Trump 1,968,215 (a test checks this).

Why: MIT's 2024 precinct file has no early-voting rows for Mercer County (about 24% of its votes) and is 2% to 3% short in Union and Warren. `python -m gerry votes` scales each New Jersey county's precinct votes, party by party, to these totals.

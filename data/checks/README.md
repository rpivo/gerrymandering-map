# Checks

Published numbers the pipeline's own results are compared against. They aren't inputs: nothing is computed from them.

## `tx-planc2193-president-2024.csv`

2024 presidential votes (Harris, Trump) for each of Texas's 38 districts under PLANC2193, the map used in 2024. Transcribed from the Texas Legislative Council's report "Election Analysis for Congressional Districts, PLANC2193, 2024 General Election" (red206), a public government record:

- URL: https://data.capitol.texas.gov/dataset/b806b39a-4bab-4103-a66a-9c99bcaba490/resource/f033e126-e7ee-43d7-95c5-c9fe3a2079d7/download/planc2193_r206_election24g.pdf
- Downloaded 2026-11-05, SHA-256 `efe091b0c1c7f7801855b0d344c9b9c47dd03924ab26446515af8c663cf0689f`
- District totals sum to the report's statewide line: Harris 4,835,134, Trump 6,393,403.

`python -m gerry votes` joins MIT's precinct files and checks that its Texas results, which come out on the 2024 map, match these. A failing check means the join rules have broken.

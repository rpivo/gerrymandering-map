# November 2026 House and Senate results

Who won each U.S. House and Senate race on the November 3, 2026 ballot, transcribed by hand from the states' own results while they were still unofficial. `python -m gerry elected` (`make elected`) turns these files into `site/src/data/elected-2026.json`.

## `results-2026.csv`

One row for each of the 435 House districts (on the 2026 lines) and each of the 35 Senate seats that were up (33 regular class 2 seats, plus special elections in Ohio and Florida): the two leading candidates, their parties and votes, as each state's election office published them.

- `counted` says how complete the count was, in the state's own words.
- `source_url` and `publisher` name the page or file read. A few states publish only through a JSON or CSV export behind their results page, or through county files the state links to (New Jersey, Florida, Ohio), which were added up by district.
- `checked` is the date it was read: 2026-11-06. These are unofficial counts, public government records, and change until each state certifies them.
- A row with no leader means the state hadn't published statewide results that could be read on that date: Illinois, Wisconsin and Mississippi post results only by county until their official counts, Massachusetts and West Virginia hadn't posted general-election results, Michigan's results site wasn't responding, and Maine had posted only overseas and military ballots for its 1st district and Senate race. Pages show those races as pending.
- Names and parties are kept as each state printed them. The pipeline writes them in one style (`gerry.elected.display_name` and `party_name`).

## `uncalled-2026.csv`

Races news organizations' decision desks hadn't called, or that go to a runoff, as of `as_of`. The site shows a winner only for a race that is not on this list, and never calls a race itself. The House list is every race the NBC News Decision Desk hadn't projected on its House results page (data provided by The Associated Press) on 2026-11-06 at 9:32 a.m. ET. The Senate races are those NBC's coverage of November 5 and 6 reported as uncalled. Louisiana's 5th and 6th districts go to a December 12 runoff because no candidate won a majority. Only whether a race was called is taken from news organizations; every name and number comes from the states.

## Updating

Recheck the uncalled list and the pending states, update the rows, and run `make elected`. It fails unless every district and every Senate seat up in 2026 has exactly one row.

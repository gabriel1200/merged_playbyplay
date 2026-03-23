# NBA Play-by-Play Data

Per-game play-by-play files for NBA regular season and playoff games, processed from the NBA Stats API V3 feed.

## File naming

```
{season_end_year}_{game_id}.csv
```

| Example | Season | Type |
|---|---|---|
| `2020_21900002.csv` | 2019-20 | Regular season |
| `2020_41900101.csv` | 2019-20 | Playoffs |
| `2023_22200157.csv` | 2022-23 | Regular season |

The season end-year is the calendar year the season concluded in — so 2019-20 → `2020`, 2022-23 → `2023`.

Game IDs starting with `2` are regular season; starting with `4` are playoffs.

---

## Columns

| Column | Type | Description |
|---|---|---|
| `period` | int | Quarter / OT period (1–4, then 5+ for OT) |
| `clock` | str | ISO duration remaining in period, e.g. `PT11M43.00S` |
| `clock_display` | str | Human-readable clock, e.g. `11:43` |
| `game_clock` | str | Period + clock combined, e.g. `Q2 11:43` |
| `minutes_left_in_game` | float | Continuous minutes left (48:00 → 0:00) |
| `actionNumber` | int | Sequential event number within the game |
| `actionType` | str | Event type: `2pt`, `3pt`, `freethrow`, `rebound`, `foul`, `turnover`, `substitution`, `timeout`, `steal`, `block`, `period` |
| `description` | str | Raw NBA description string |
| `qualifier` | str | List of tags, e.g. `['2ndchance', 'pointsinthepaint']` |
| `playerName` | str | Last name of the primary actor |
| `scoreHome` | int | Running home score |
| `scoreAway` | int | Running away score |
| `shotResult` | str | `Made` / `Missed` (shots and free throws only) |
| `isFieldGoal` | bool | True for 2pt and 3pt attempts |
| `assisted` | bool | True if the made shot had an assist |
| `person_id` | float | NBA player ID of the primary actor (0 for team events) |
| `assister_id` | float | Player ID of the assist on made field goals |
| `previous_action` | str | `actionType` of the preceding row |
| `next_action` | str | `actionType` of the following row |
| `foulDrawnPersonId` | float | Player ID of the player who drew the foul |
| `stealPersonId` | float | Player ID on steal rows |
| `blockPersonId` | float | Player ID on block rows |
| `players_on` | str | Pipe-separated player IDs of all 10 players on court, e.g. `202695\|203076\|...` |
| `off_players_on` | str | Pipe-separated IDs of the 5 offensive players (acting team) |
| `def_players_on` | str | Pipe-separated IDs of the 5 defensive players |
| `xLegacy` | float | Shot X coordinate (shots only, null otherwise) |
| `yLegacy` | float | Shot Y coordinate (shots only, null otherwise) |
| `teamId` | float | NBA team ID of the acting team (0 for neutral events) |
| `game_id` | int | NBA game ID |
| `poc_ok` | bool | True if exactly 10 players are tracked on court for this row. Rows where `poc_ok=False` indicate a lineup tracker gap — use `poc_ok=True` rows for lineup-dependent analysis |

### teamId values

Team IDs are 10-digit numbers stored as `float64`, e.g. `1610612746.0` = LAC. A value of `0.0` indicates a team-neutral event (team rebound, period marker, etc.).

---

## collect_pbp.py

A helper script for loading and combining the per-game files into whatever unit you need. All year and team filtering is done using a lightweight index fetched from GitHub — **no PBP files are opened until the final load step**, so filtering by team across thousands of games is instant.

### Requirements

```
pip install pandas requests
```

### Quick start

```bash
# All LAC 2019-20 regular season games → LAC_2020_rs.csv
python collect_pbp.py --years 2020 --teams LAC --output LAC_2020_rs.csv

# See what you'd get before loading anything
python collect_pbp.py --years 2020 --teams LAC --dry-run
```

---

### CLI reference

```
python collect_pbp.py [options]
```

| Flag | Description | Default |
|---|---|---|
| `--data-dir` | Directory containing the per-game CSVs | `pbp_data` |
| `--years` | Season end-year(s), space-separated | all years |
| `--teams` | Team abbreviation(s), space-separated | all teams |
| `--game-type` | `regular_season`, `playoffs`, or `both` | `regular_season` |
| `--output` | Save path (`.csv` or `.parquet`) | none (returns to stdout summary) |
| `--dry-run` | List matched files without loading | — |
| `--list-years` | Print available season years and exit | — |
| `--list-teams` | Print available team abbreviations and exit | — |
| `--list-games` | Print a table of matched games and exit | — |

> **Default game type is `regular_season`.**  
> Pass `--game-type playoffs` or `--game-type both` to include playoff games.

#### Examples

```bash
# One team, one season (regular season — the default)
python collect_pbp.py --years 2020 --teams LAC --output LAC_2020_rs.csv

# Same team, playoffs only
python collect_pbp.py --years 2020 --teams LAC --game-type playoffs --output LAC_2020_ps.csv

# Both regular season and playoffs
python collect_pbp.py --years 2020 --teams LAC --game-type both --output LAC_2020_all.csv

# Multiple teams, multiple seasons
python collect_pbp.py --years 2020 2021 2022 --teams LAC LAL --output LAC_LAL_3yr.csv

# Entire 2022-23 regular season (all teams), saved as parquet
python collect_pbp.py --years 2023 --output 2023_rs.parquet

# Check what's available
python collect_pbp.py --list-years
python collect_pbp.py --list-teams
python collect_pbp.py --list-games --years 2020 --teams LAC

# Dry run — see which files match without loading them
python collect_pbp.py --years 2020 --teams LAC LAL --dry-run
```

---

### Python API

```python
from collect_pbp import collect, collect_team_season, collect_playoffs, list_games

# One team, one season (regular season)
df = collect_team_season("LAC", 2020)

# Explicit control over game type
df = collect(years=2020, teams="LAC", game_type="regular_season")
df = collect(years=2020, teams="LAC", game_type="playoffs")
df = collect(years=2020, teams="LAC", game_type="both")

# Multiple seasons
df = collect(years=[2020, 2021, 2022], teams="LAC")

# Multiple teams
df = collect(years=2020, teams=["LAC", "LAL"])

# Full season, save as parquet
df = collect(years=2023, output="2023_rs.parquet")

# Inspect before loading
games = list_games(years=2020, teams="LAC")
print(games)
```

#### Available functions

| Function | Description |
|---|---|
| `collect(...)` | Main function — full control over all filters |
| `collect_season(year)` | All regular-season games for a year |
| `collect_playoffs(year)` | All playoff games for a year |
| `collect_team(team, years=None)` | All games (RS + playoffs) for a team |
| `collect_team_season(team, year)` | Regular-season games for one team and year |
| `available_years(data_dir)` | List season years present in `data_dir` |
| `available_teams(years=None)` | List team abbreviations (from index, no files read) |
| `list_games(...)` | DataFrame of matched games with no PBP files opened |

---

### Team abbreviations

| Abbr | Team | Abbr | Team |
|---|---|---|---|
| ATL | Atlanta Hawks | MEM | Memphis Grizzlies |
| BKN | Brooklyn Nets | MIA | Miami Heat |
| BOS | Boston Celtics | MIL | Milwaukee Bucks |
| CHA | Charlotte Hornets | MIN | Minnesota Timberwolves |
| CHI | Chicago Bulls | NOP | New Orleans Pelicans |
| CLE | Cleveland Cavaliers | NYK | New York Knicks |
| DAL | Dallas Mavericks | OKC | Oklahoma City Thunder |
| DEN | Denver Nuggets | ORL | Orlando Magic |
| DET | Detroit Pistons | PHI | Philadelphia 76ers |
| GSW | Golden State Warriors | PHX | Phoenix Suns |
| HOU | Houston Rockets | POR | Portland Trail Blazers |
| IND | Indiana Pacers | SAC | Sacramento Kings |
| LAC | LA Clippers | SAS | San Antonio Spurs |
| LAL | Los Angeles Lakers | TOR | Toronto Raptors |
| MEM | Memphis Grizzlies | UTA | Utah Jazz |
| — | — | WAS | Washington Wizards |

---

### Notes on `players_on`

- Contains the IDs of all 10 players on court at the moment of each action, as a pipe-separated string: `202695|203076|203484|...`
- Use `poc_ok=True` to filter to rows where the lineup tracker is confident exactly 10 players are present. Rows with `poc_ok=False` typically occur near period boundaries in pre-2021 data where the V3 PBP feed omitted substitution events.
- Pre-2021 games have a higher rate of `poc_ok=False` rows (~15–20%) than 2021+ games (~2–5%) due to known data gaps in the V3 feed for older games.
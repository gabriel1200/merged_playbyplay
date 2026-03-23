"""
collect_pbp.py
==============
Helper for assembling per-game PBP CSV files into whatever unit you need.

FILE NAMING CONVENTION
----------------------
Every file is named:  {season_end_year}_{game_id}.csv
  e.g.  2020_21900002.csv   →  2019-20 season, game 21900002
        2023_22200157.csv   →  2022-23 season, game 22200157

Game-ID prefixes
  2...  regular season
  4...  playoffs

TEAM IDs (teamId column, 10-digit floats)
  Stored as float64, e.g. 1610612746.0  →  LAC
  Zero (0.0) means a neutral event (team rebound, timeout with no actor, etc.)

TEAM / GAME FILTERING
---------------------
All year and team filtering is done using the game_dates index from GitHub —
no PBP files are opened until the final load step.  This means filtering by
team across thousands of files is instant regardless of how large the repo is.

The index is fetched once per session and cached in memory.

USAGE EXAMPLES
--------------
  # All games for one season
  collect(years=2020)

  # Multiple seasons
  collect(years=[2020, 2021, 2022])

  # One team, one season
  collect(years=2020, teams="LAC")

  # One team, multiple seasons
  collect(years=[2020, 2021, 2022], teams="LAC")

  # Multiple teams, multiple seasons
  collect(years=[2020, 2021], teams=["LAC", "LAL"])

  # Playoffs only
  collect(years=2020, game_type="playoffs")

  # Save result to a file
  collect(years=2020, teams="LAC", output="LAC_2020.csv")

  # Just list what files would be collected, don't load them
  collect(years=2020, teams="LAC", dry_run=True)

All functions return a combined pandas DataFrame (or None on dry_run).
"""

import os
import re
import glob
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Team ID <-> abbreviation mapping
# ---------------------------------------------------------------------------

TEAM_ID_TO_ABBR = {
    1610612760: "OKC", 1610612749: "MIL", 1610612758: "SAC", 1610612747: "LAL",
    1610612738: "BOS", 1610612743: "DEN", 1610612750: "MIN", 1610612752: "NYK",
    1610612756: "PHX", 1610612753: "ORL", 1610612766: "CHA", 1610612739: "CLE",
    1610612746: "LAC", 1610612737: "ATL", 1610612748: "MIA", 1610612742: "DAL",
    1610612765: "DET", 1610612763: "MEM", 1610612761: "TOR", 1610612741: "CHI",
    1610612754: "IND", 1610612759: "SAS", 1610612745: "HOU", 1610612751: "BKN",
    1610612764: "WAS", 1610612744: "GSW", 1610612755: "PHI", 1610612762: "UTA",
    1610612757: "POR", 1610612740: "NOP",
}

ABBR_TO_TEAM_ID = {v: k for k, v in TEAM_ID_TO_ABBR.items()}

GAME_DATES_URL = (
    "https://raw.githubusercontent.com/gabriel1200/shot_data"
    "/refs/heads/master/game_dates.csv"
)

# Module-level cache so the index is only fetched once per session
_INDEX: pd.DataFrame | None = None


# ---------------------------------------------------------------------------
# Game-dates index  (game_id → set of team abbrs)
# ---------------------------------------------------------------------------

def _load_index(verbose: bool = True) -> pd.DataFrame:
    """
    Fetch game_dates.csv from GitHub and return a tidy DataFrame with columns:
        game_id (int), team (str abbr), game_type (str), season_year (int)

    Result is cached in _INDEX for the lifetime of the process.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    if verbose:
        print("Fetching game index from GitHub …")

    try:
        raw = pd.read_csv(GAME_DATES_URL, dtype={"GAME_ID": str, "TEAM_ID": str})
    except Exception as e:
        raise RuntimeError(
            f"Could not fetch game index from {GAME_DATES_URL}:\n{e}\n"
            "Check your internet connection."
        ) from e

    # Derive season_year from the season string (e.g. '2019-20' → 2020)
    raw["season_year"] = raw["season"].str.split("-").str[0].astype(int) + 1

    # Map team ID to abbreviation
    raw["team_abbr"] = raw["TEAM_ID"].apply(
        lambda tid: TEAM_ID_TO_ABBR.get(int(tid)) if tid.isdigit() else None
    )

    # Derive game type from game_id prefix
    raw["game_type"] = raw["GAME_ID"].apply(
        lambda gid: "playoffs" if gid.lstrip("0").startswith("4")
        else ("regular_season" if gid.lstrip("0").startswith("2") else "unknown")
    )

    raw["game_id_int"] = raw["GAME_ID"].str.lstrip("0").astype(int)

    _INDEX = raw[["game_id_int", "team_abbr", "game_type", "season_year"]].rename(
        columns={"game_id_int": "game_id", "team_abbr": "team"}
    ).dropna(subset=["team"]).drop_duplicates()

    if verbose:
        print(f"  Index loaded: {_INDEX['game_id'].nunique()} games, "
              f"{_INDEX['season_year'].nunique()} seasons.")

    return _INDEX


def _game_ids_for(
    years=None,
    teams=None,
    game_type: str = "both",
    verbose: bool = True,
) -> set[int]:
    """
    Return the set of game_ids that match the given filters, using only the
    in-memory index — no PBP files are read.
    """
    idx = _load_index(verbose=verbose)
    mask = pd.Series([True] * len(idx), index=idx.index)

    if years is not None:
        target_years = _normalize_years(years)
        mask &= idx["season_year"].isin(target_years)

    if teams is not None:
        target_teams = _normalize_teams(teams)
        unknown = target_teams - set(ABBR_TO_TEAM_ID.keys())
        if unknown:
            raise ValueError(
                f"Unknown team abbreviation(s): {unknown}\n"
                f"Valid options: {sorted(ABBR_TO_TEAM_ID.keys())}"
            )
        mask &= idx["team"].isin(target_teams)

    if game_type != "both":
        mask &= idx["game_type"] == game_type

    return set(idx.loc[mask, "game_id"].unique())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_teams(teams):
    if teams is None:
        return None
    if isinstance(teams, str):
        teams = [teams]
    return {t.upper().strip() for t in teams}


def _normalize_years(years):
    if years is None:
        return None
    if isinstance(years, int):
        return [years]
    return sorted(int(y) for y in years)


def _game_type_of(game_id: str) -> str:
    stripped = str(game_id).lstrip("0")
    if stripped.startswith("4"):
        return "playoffs"
    if stripped.startswith("2"):
        return "regular_season"
    return "unknown"


def _parse_filename(fname: str):
    """Return (year: int, game_id: int) from '2020_21900002.csv', or None."""
    m = re.match(r"(\d{4})_(\d+)\.csv$", fname)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------------------
# Main collection function
# ---------------------------------------------------------------------------

def collect(
    data_dir: str = "pbp_data",
    years=None,
    teams=None,
    game_type: str = "both",
    output: str | None = None,
    dry_run: bool = False,
    sort: bool = True,
    verbose: bool = True,
) -> pd.DataFrame | None:
    """
    Load and combine per-game PBP CSV files.

    Parameters
    ----------
    data_dir : str
        Directory containing the per-game CSV files (default: 'pbp_data').
    years : int | list[int] | None
        Season end-year(s) to include, e.g. 2020 for 2019-20.
        None = all years found.
    teams : str | list[str] | None
        Team abbreviation(s) to include, e.g. 'LAC' or ['LAC', 'LAL'].
        None = all teams (every game is included).
        When specified, only games in which that team participated are kept,
        but the returned DataFrame contains ALL rows for those games (both
        teams' actions), matching the same structure as the source files.
    game_type : str
        'regular_season', 'playoffs', or 'both' (default).
    output : str | None
        If given, save the combined DataFrame to this path (.csv or .parquet).
    dry_run : bool
        If True, print the files that would be loaded and return None.
    sort : bool
        Sort the combined DataFrame by (game_id, period, actionNumber).
    verbose : bool
        Print progress messages.

    Returns
    -------
    pd.DataFrame or None (dry_run=True)
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Directory not found: {data_dir}")

    # ── Build the target game_id set from the index (no files opened) ─────
    need_index = (teams is not None) or (game_type != "both")
    if need_index:
        target_game_ids = _game_ids_for(
            years=years, teams=teams, game_type=game_type, verbose=verbose
        )
    else:
        target_game_ids = None   # means "accept all"

    # ── Gather candidate files using only filenames ───────────────────────
    target_years = _normalize_years(years)
    if target_years:
        candidates = []
        for y in target_years:
            candidates.extend(glob.glob(str(data_dir / f"{y}_*.csv")))
    else:
        candidates = glob.glob(str(data_dir / "*.csv"))

    # Filter by game_id if we have a target set
    if target_game_ids is not None:
        filtered = []
        for path in candidates:
            parsed = _parse_filename(os.path.basename(path))
            if parsed and parsed[1] in target_game_ids:
                filtered.append(path)
        candidates = filtered

    candidates = sorted(candidates)

    if not candidates:
        print("No files matched the given filters.")
        return None

    if dry_run:
        print(f"Would load {len(candidates)} file(s):")
        for p in candidates:
            print(f"  {p}")
        return None

    # ── Load and combine ──────────────────────────────────────────────────
    if verbose:
        label_parts = []
        if target_years:
            label_parts.append(f"years={target_years}")
        if teams is not None:
            label_parts.append(f"teams={sorted(_normalize_teams(teams))}")
        if game_type != "both":
            label_parts.append(game_type)
        label = ", ".join(label_parts) or "all games"
        print(f"Loading {len(candidates)} file(s) [{label}] …")

    frames = []
    for path in candidates:
        try:
            frames.append(pd.read_csv(path, low_memory=False))
        except Exception as e:
            print(f"  Warning: could not read {path}: {e}")

    if not frames:
        print("No data loaded.")
        return None

    combined = pd.concat(frames, ignore_index=True)

    if sort:
        combined = combined.sort_values(
            ["game_id", "period", "actionNumber"]
        ).reset_index(drop=True)

    if verbose:
        unique_games = combined["game_id"].nunique()
        print(f"Combined: {len(combined):,} rows, {unique_games} games.")

    # ── Save ──────────────────────────────────────────────────────────────
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix == ".parquet":
            combined.to_parquet(out, index=False)
        else:
            combined.to_csv(out, index=False)
        if verbose:
            print(f"Saved → {out}")

    return combined


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def collect_season(year: int, **kwargs) -> pd.DataFrame:
    """All regular-season games for a single season end-year."""
    return collect(years=year, game_type="regular_season", **kwargs)


def collect_playoffs(year: int, **kwargs) -> pd.DataFrame:
    """All playoff games for a single season end-year."""
    return collect(years=year, game_type="playoffs", **kwargs)


def collect_team(team: str, years=None, **kwargs) -> pd.DataFrame:
    """All games (both regular season and playoffs) for a team."""
    return collect(teams=team, years=years, **kwargs)


def collect_team_season(team: str, year: int, **kwargs) -> pd.DataFrame:
    """Regular-season games for a specific team and year."""
    return collect(teams=team, years=year, game_type="regular_season", **kwargs)


def available_years(data_dir: str = "pbp_data") -> list[int]:
    """Return a sorted list of season end-years present in data_dir."""
    files = glob.glob(str(Path(data_dir) / "*.csv"))
    years = set()
    for f in files:
        m = re.match(r"(\d{4})_", os.path.basename(f))
        if m:
            years.add(int(m.group(1)))
    return sorted(years)


def available_teams(years=None, verbose: bool = False) -> list[str]:
    """
    Return a sorted list of all team abbreviations in the index.
    Optionally filter to specific season year(s).
    Does not require opening any PBP files.
    """
    idx = _load_index(verbose=verbose)
    if years is not None:
        idx = idx[idx["season_year"].isin(_normalize_years(years))]
    return sorted(idx["team"].dropna().unique())


def list_games(
    data_dir: str = "pbp_data",
    years=None,
    teams=None,
    game_type: str = "both",
) -> pd.DataFrame:
    """
    Return a DataFrame summarising available games without loading PBP data.
    Columns: filename, year, game_id, game_type, teams.

    Uses the game-dates index for team info — no PBP files are opened.
    """
    idx = _load_index(verbose=False)

    # Build game_id → teams lookup from the index
    game_teams = (
        idx.groupby("game_id")["team"]
        .apply(lambda s: "|".join(sorted(s.dropna())))
        .to_dict()
    )

    target_game_ids = _game_ids_for(
        years=years, teams=teams, game_type=game_type, verbose=False
    ) if (teams is not None or game_type != "both" or years is not None) else None

    target_years = _normalize_years(years)
    if target_years:
        files = []
        for y in target_years:
            files.extend(glob.glob(str(Path(data_dir) / f"{y}_*.csv")))
    else:
        files = glob.glob(str(Path(data_dir) / "*.csv"))

    rows = []
    for path in sorted(files):
        fname = os.path.basename(path)
        parsed = _parse_filename(fname)
        if not parsed:
            continue
        yr, gid = parsed
        if target_game_ids is not None and gid not in target_game_ids:
            continue
        gtype = _game_type_of(str(gid))
        rows.append({
            "filename":  fname,
            "year":      yr,
            "game_id":   gid,
            "game_type": gtype,
            "teams":     game_teams.get(gid, ""),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# CLI  (python collect_pbp.py --help)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect and combine per-game PBP CSV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # All LAC 2019-20 regular season games, save to CSV
  python collect_pbp.py --years 2020 --teams LAC --output LAC_2020_rs.csv

  # All games for 2020 and 2021 seasons, playoffs only
  python collect_pbp.py --years 2020 2021 --game-type playoffs

  # Show what files would be collected for LAL across three seasons
  python collect_pbp.py --years 2021 2022 2023 --teams LAL --dry-run

  # List available years and teams
  python collect_pbp.py --list-years
  python collect_pbp.py --list-teams
        """,
    )
    parser.add_argument("--data-dir",   default="pbp_data",
                        help="Directory containing per-game CSVs (default: pbp_data)")
    parser.add_argument("--years",      nargs="+", type=int,
                        help="Season end-year(s), e.g. 2020 2021")
    parser.add_argument("--teams",      nargs="+",
                        help="Team abbreviation(s), e.g. LAC LAL")
    parser.add_argument("--game-type",  default="both",
                        choices=["both", "regular_season", "playoffs"],
                        help="Filter by game type (default: both)")
    parser.add_argument("--output",     default=None,
                        help="Save combined data to this .csv or .parquet file")
    parser.add_argument("--dry-run",    action="store_true",
                        help="List files that would be loaded, don't load them")
    parser.add_argument("--list-years", action="store_true",
                        help="Print available season years and exit")
    parser.add_argument("--list-teams", action="store_true",
                        help="Print available team abbreviations and exit")
    parser.add_argument("--list-games", action="store_true",
                        help="Print a table of available games and exit")

    args = parser.parse_args()

    if args.list_years:
        yrs = available_years(args.data_dir)
        print("Available years:", yrs if yrs else "(none found)")

    elif args.list_teams:
        tms = available_teams(years=args.years)
        print("Available teams:", tms if tms else "(none found)")

    elif args.list_games:
        games = list_games(
            data_dir=args.data_dir,
            years=args.years,
            teams=args.teams,
            game_type=args.game_type,
        )
        if games.empty:
            print("No games matched.")
        else:
            print(games.to_string(index=False))

    else:
        collect(
            data_dir=args.data_dir,
            years=args.years,
            teams=args.teams,
            game_type=args.game_type,
            output=args.output,
            dry_run=args.dry_run,
        )
"""Stitch outright NQ contracts into one front-month minute series.

Front month is the highest-volume outright each session. Prices are not
back-adjusted. Do not compute a return across a contract change.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.paths import repo_root


def build_front_month(year_files: list[Path], out_path: Path | None = None) -> pd.DataFrame:
    """Concatenate yearly outright files and keep the front month each session."""
    frames = [pd.read_parquet(path) for path in year_files]
    nq = pd.concat(frames, ignore_index=True)

    volume = nq.groupby(["session_end_date", "ticker"])["volume"].sum().reset_index()
    front = volume.loc[
        volume.groupby("session_end_date")["volume"].idxmax(),
        ["session_end_date", "ticker"],
    ]
    nq = nq.merge(front, on=["session_end_date", "ticker"])
    nq["time"] = (
        pd.to_datetime(nq["window_start"], unit="ns", utc=True)
        .dt.tz_convert("America/New_York")
    )
    nq = (
        nq.sort_values("time")
        .set_index("time")[["ticker", "open", "high", "low", "close", "volume"]]
    )

    destination = Path(out_path) if out_path is not None else repo_root() / "data" / "nq_1m_front.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    nq.to_parquet(destination)
    return nq

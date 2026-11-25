"""Build hourly OHLC bars from the front-month minute series.

Hours are floored in UTC, then labeled in New York time. Grouping by ticker
prevents a single hour from mixing two contracts on a roll.
"""

from __future__ import annotations

import pandas as pd


def build_hourly_bars(nq: pd.DataFrame) -> pd.DataFrame:
    hour_key = nq.index.tz_convert("UTC").floor("1h").rename("hour")
    hourly = (
        nq.groupby([nq["ticker"], hour_key])
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
        )
        .reset_index()
        .sort_values("hour")
        .reset_index(drop=True)
    )
    hourly["hour"] = hourly["hour"].dt.tz_convert("America/New_York")
    return hourly

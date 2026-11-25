"""Spike z-scores on hourly bars.

Returns are blanked when the ticker changes, so a roll is not a return.
Volatility is the trailing standard deviation of those returns, shifted by
one bar so the current bar is not included in its own threshold.
"""

from __future__ import annotations

import pandas as pd

RTH_HOUR_MIN = 9
RTH_HOUR_MAX = 14  # signal hour; the next clock hour is still inside the cash session


def add_return_zscore(hourly: pd.DataFrame, vol_bars: int = 100, min_periods: int = 50) -> pd.DataFrame:
    out = hourly.copy()
    same_contract = out["ticker"] == out["ticker"].shift()
    out["r"] = out["close"].pct_change().where(same_contract)
    out["vol"] = out["r"].rolling(vol_bars, min_periods=min_periods).std().shift(1)
    out["z"] = out["r"] / out["vol"]
    return out


def rth_up_spike_signals(hourly: pd.DataFrame, z_cut: float = 2.0) -> pd.DataFrame:
    """RTH hours whose return exceeded ``z_cut`` sigma, with a real next hour.

    ``move_pts`` is the next-hour close minus nothing: entry close minus next
    close. Positive means the price pulled back (the short would have gained
    before costs).
    """
    nxt = hourly.shift(-1)
    next_is_contiguous = (nxt["ticker"] == hourly["ticker"]) & (
        nxt["hour"] - hourly["hour"] == pd.Timedelta(hours=1)
    )
    in_rth = hourly["hour"].dt.hour.between(RTH_HOUR_MIN, RTH_HOUR_MAX)
    signals = hourly[(hourly["z"] > z_cut) & in_rth & next_is_contiguous].copy()
    signals["next_close"] = nxt.loc[signals.index, "close"]
    signals["move_pts"] = signals["close"] - signals["next_close"]
    return signals


def return_zscore_series(close: pd.Series, window: int) -> pd.DataFrame:
    """Z-score of simple returns for a single price series (Yahoo bars)."""
    returns = close.pct_change()
    vol = returns.rolling(window).std().shift(1)
    return pd.DataFrame({"close": close, "r": returns, "vol": vol, "z": returns / vol})

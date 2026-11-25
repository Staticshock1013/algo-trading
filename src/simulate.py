"""Trade simulators for the spike-fade study.

``simulate_minute`` walks the minute bars inside the hour after a signal and
can fill a volatility-scaled stop or target. ``simulate_hourly_bar`` is the
first, flawed backtest: it only sees the next hourly bar, so a stop and a
target inside that bar cannot be ordered.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _apply_daily_loss_limit(trades: pd.DataFrame, daily_loss_limit: float) -> pd.DataFrame:
    kept = []
    day_pnl: dict = {}
    for i, row in trades.iterrows():
        if day_pnl.get(row.date, 0) <= -daily_loss_limit:
            continue
        day_pnl[row.date] = day_pnl.get(row.date, 0) + row.pnl
        kept.append(i)
    return trades.loc[kept].reset_index(drop=True)


def _pnl(points: float, contracts: int, point_value: float, commission_rt: float) -> float:
    return points * point_value * contracts - commission_rt * contracts


def simulate_minute(
    nq: pd.DataFrame,
    signals: pd.DataFrame,
    stop_sigma: float | None = None,
    target_sigma: float | None = None,
    contracts: int = 2,
    point_value: float = 2.0,
    commission_rt: float = 1.50,
    slippage_pts: float = 1.0,
    daily_loss_limit: float = 1000,
) -> pd.DataFrame:
    """Short the signal-hour close. Manage the short on the next hour's minutes.

    If stop and target print in the same minute, the stop is assumed to fill
    first. With no stop and no target this is a time exit at the next hour's
    close. ``pts`` is after the round-trip slippage allowance.
    """
    index = nq.index
    highs = nq["high"].to_numpy()
    lows = nq["low"].to_numpy()
    rows = []
    for _, signal in signals.iterrows():
        entry = signal["close"]
        sigma_pts = signal["vol"] * entry
        stop = entry + stop_sigma * sigma_pts if stop_sigma else np.inf
        target = entry - target_sigma * sigma_pts if target_sigma else -np.inf

        start = signal["hour"] + pd.Timedelta(hours=1)
        i0 = index.searchsorted(start)
        i1 = index.searchsorted(start + pd.Timedelta(hours=1))
        stop_hits = np.where(highs[i0:i1] >= stop)[0]
        target_hits = np.where(lows[i0:i1] <= target)[0]
        first_stop = stop_hits[0] if len(stop_hits) else 10**9
        first_target = target_hits[0] if len(target_hits) else 10**9

        if first_stop < 10**9 and first_stop <= first_target:
            exit_price, outcome = stop, "stop"
        elif first_target < 10**9:
            exit_price, outcome = target, "target"
        else:
            exit_price, outcome = signal["next_close"], "time exit"

        points = entry - exit_price - slippage_pts
        rows.append(
            {
                "time": signal["hour"],
                "date": signal["hour"].date(),
                "pts": points,
                "pnl": _pnl(points, contracts, point_value, commission_rt),
                "outcome": outcome,
            }
        )
    trades = pd.DataFrame(rows)
    return _apply_daily_loss_limit(trades, daily_loss_limit)


def simulate_hourly_bar(
    bars: pd.DataFrame,
    z: pd.Series,
    z_cut: float = 2.0,
    stop_pts: float = 20,
    target_pts: float = 15,
    contracts: int = 2,
    point_value: float = 2.0,
    commission_rt: float = 1.50,
    slippage_pts: float = 1.0,
    daily_loss_limit: float = 1000,
    hour_min: int = 9,
    hour_max: int = 14,
    vol_warmup: int = 100,
) -> pd.DataFrame:
    """First backtest. Decisions use only the next hourly OHLC bar.

    If that bar touches both the stop and the target, the stop is assumed.
    That assumption is not identified from hourly data; see the minute simulator.
    """
    trades = []
    for i in range(vol_warmup + 1, len(bars) - 1):
        t0 = bars.index[i]
        t1 = bars.index[i + 1]
        if not (z.iloc[i] > z_cut and hour_min <= t0.hour <= hour_max):
            continue
        if t1 - t0 != pd.Timedelta(hours=1):
            continue

        entry = bars["Close"].iloc[i]
        nxt = bars.iloc[i + 1]
        stop = entry + stop_pts
        target = entry - target_pts
        if nxt["High"] >= stop:
            exit_price, outcome = stop, "stop"
        elif nxt["Low"] <= target:
            exit_price, outcome = target, "target"
        else:
            exit_price, outcome = nxt["Close"], "time exit"

        points = entry - exit_price - slippage_pts
        trades.append(
            {
                "time": t0,
                "date": t0.date(),
                "pts": points,
                "pnl": _pnl(points, contracts, point_value, commission_rt),
                "outcome": outcome,
            }
        )
    return _apply_daily_loss_limit(pd.DataFrame(trades), daily_loss_limit)


def time_exit_points(bars: pd.DataFrame, trades: pd.DataFrame, slippage_pts: float = 1.0) -> pd.Series:
    """Mark each hourly trade to the next close, ignoring stop and target."""
    raw = []
    for _, row in trades.iterrows():
        i = bars.index.get_loc(row.time)
        entry = bars["Close"].iloc[i]
        nxt = bars.iloc[i + 1]
        raw.append(entry - nxt["Close"] - slippage_pts)
    return pd.Series(raw, index=trades.index)

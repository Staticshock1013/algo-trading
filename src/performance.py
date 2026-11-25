"""P&L summaries and the monthly walk-forward filter."""

from __future__ import annotations

import numpy as np
import pandas as pd


def equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    out["equity"] = out["pnl"].cumsum()
    peak = out["equity"].cummax().clip(lower=0)
    out["drawdown"] = out["equity"] - peak
    return out


def profit_factor(trades: pd.DataFrame) -> float:
    wins = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    losses = trades.loc[trades["pnl"] <= 0, "pnl"].sum()
    if losses == 0:
        return float("inf")
    return float(wins / abs(losses))


def summary(trades: pd.DataFrame, label: str) -> dict:
    """Print one result line and return the same stats."""
    curve = equity_curve(trades)
    wins = trades[trades["pnl"] > 0]
    stats = {
        "label": label,
        "trades": int(len(trades)),
        "win_rate": float(len(wins) / len(trades)) if len(trades) else float("nan"),
        "avg_pts": float(trades["pts"].mean()) if len(trades) else float("nan"),
        "pnl": float(trades["pnl"].sum()) if len(trades) else 0.0,
        "profit_factor": profit_factor(trades) if len(trades) else float("nan"),
        "max_drawdown": float(curve["drawdown"].min()) if len(trades) else 0.0,
    }
    print(
        f"{label:26} {stats['trades']:4} trades | win {stats['win_rate']:.0%} | "
        f"avg {stats['avg_pts']:+6.1f} pts | P&L ${stats['pnl']:+9,.0f} | "
        f"PF {stats['profit_factor']:.2f} | max DD ${stats['max_drawdown']:,.0f}"
    )
    return stats


def yearly_summary(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in trades.groupby(trades["time"].dt.year):
        rows.append(
            {
                "year": int(year),
                "trades": int(len(group)),
                "win_rate": float((group["pnl"] > 0).mean()),
                "avg_pts": float(group["pts"].mean()),
                "pnl": float(group["pnl"].sum()),
            }
        )
        print(
            f"  {year}: {len(group):3} trades | win {(group.pnl > 0).mean():.0%} | "
            f"avg {group.pts.mean():+6.1f} pts | P&L ${group.pnl.sum():+,.0f}"
        )
    return pd.DataFrame(rows)


def walk_forward_month_filter(trades: pd.DataFrame, window: int = 100) -> pd.DataFrame:
    """Keep months whose trailing ``window`` trades averaged more than 0 pts.

    The average uses only trades before the month starts (``shift(1)`` inside
    the rolling mean, then the first value of the month). No trade in the
    month can turn the filter on for itself.
    """
    out = trades.copy().reset_index(drop=True)
    out["trailing_avg"] = out["pts"].rolling(window).mean().shift(1)
    out["month"] = out["time"].dt.strftime("%Y-%m")
    month_on = out.groupby("month")["trailing_avg"].first() > 0
    out["active"] = out["month"].map(month_on).fillna(False)
    return out

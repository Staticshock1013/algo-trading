"""Chart indicators used in the exploratory notebook.

These are descriptive overlays. They are not the signal tested later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def keltner(
    frame: pd.DataFrame,
    ema_span: int = 20,
    atr_span: int = 20,
    multiplier: float = 2.25,
) -> pd.DataFrame:
    out = frame.copy()
    out["EMA20"] = ema(out["Close"], ema_span)
    prev_close = out["Close"].shift(1)
    true_range = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - prev_close).abs(),
            (out["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(span=atr_span, adjust=False).mean()
    out["KC_upper"] = out["EMA20"] + multiplier * atr
    out["KC_lower"] = out["EMA20"] - multiplier * atr
    return out


def range_filter(src: pd.Series, period: int = 100, mult: float = 3.0) -> pd.Series:
    avg_range = src.diff().abs().ewm(span=period, adjust=False).mean()
    smooth_range = avg_range.ewm(span=period * 2 - 1, adjust=False).mean() * mult
    prices = src.to_numpy()
    band = smooth_range.to_numpy()
    filtered = np.empty(len(prices))
    filtered[0] = prices[0]
    for i in range(1, len(prices)):
        if prices[i] > filtered[i - 1]:
            filtered[i] = max(filtered[i - 1], prices[i] - band[i])
        else:
            filtered[i] = min(filtered[i - 1], prices[i] + band[i])
    return pd.Series(filtered, index=src.index, name="RangeFilter")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"MACD": macd_line, "Signal": signal_line, "Hist": hist})

"""
XAUUSD M15 Combined Strategy Backtest
=====================================
Three independent layers:
  1. GARCH(1,1) on M15 returns   -> volatility forecast (size + go/no-go)
  2. H1 momentum (EMA + ADX)     -> directional bias
  3. M15 structure entry         -> precise entry trigger

Designed for an FTMO $25k challenge. Risk-first: hard daily loss limit,
fixed fractional sizing scaled by vol regime, structural stops.

USAGE
-----
    python xauusd_backtest.py path/to/XAUUSD_M15.csv

The loader auto-detects common formats:
  - MetaTrader 5 export (tab/comma, Date Time O H L C V)
  - HistData.com (DDMMYYYY HHMMSS;O;H;L;C;V, no header)
  - Generic CSV with a datetime column + OHLC

All evaluation is walk-forward. No look-ahead. Costs included.
"""

import sys
import argparse
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from arch import arch_model

# ── Config ────────────────────────────────────────────────────────────────────

ACCOUNT_SIZE      = 25_000
BASE_RISK_PCT     = 0.005          # 0.5% base risk per trade
DAILY_LOSS_LIMIT  = 0.05           # FTMO 5% daily
MAX_DRAWDOWN      = 0.10           # FTMO 10% overall
PROFIT_TARGET     = 0.10           # FTMO 10% target

# GARCH
GARCH_WINDOW      = 2000           # rolling candles (~3 weeks of M15)
VOL_HIGH_MULT     = 1.5            # > this x median vol => high regime
VOL_LOW_MULT      = 0.8           # < this x median vol => low regime

# Momentum (H1)
EMA_FAST          = 20
EMA_SLOW          = 50
ADX_PERIOD        = 14
ADX_THRESHOLD     = 25            # below this = ranging, no trade

# Entry / exit (defaults; overridden by instrument preset / CLI)
RR_TARGET         = 2.5           # reward:risk
ATR_PERIOD        = 14
STOP_ATR_MULT     = 1.5           # stop distance in ATRs
MAX_TRADES_DAY    = 2

# Per-instrument presets: session window (GMT) + cost model.
# Sessions chosen where each instrument has the cleanest structure.
PRESETS = {
    "xauusd": {  # Gold — London-NY overlap
        "session_start": "12:00", "session_end": "17:00",
        "spread_points": 0.20, "commission_per_lot": 7.0,
    },
    "btcusd": {  # Crypto — 24/7, so use US active hours but no hard session edge
        "session_start": "13:00", "session_end": "21:00",
        "spread_points": 5.0, "commission_per_lot": 0.0,
    },
    "nas100": {  # Index — US cash open (09:30 ET = 14:30 GMT)
        "session_start": "14:30", "session_end": "19:00",
        "spread_points": 1.0, "commission_per_lot": 0.0,
    },
    "us30": {
        "session_start": "14:30", "session_end": "19:00",
        "spread_points": 2.0, "commission_per_lot": 0.0,
    },
    "spx": {
        "session_start": "14:30", "session_end": "19:00",
        "spread_points": 0.5, "commission_per_lot": 0.0,
    },
}

# Runtime config — populated from preset + CLI in main(). session_start/end are
# stored as minutes-since-midnight (GMT) so the filter can express e.g. 14:30.
CFG = {
    "session_start": 12 * 60, "session_end": 17 * 60,
    "spread_points": 0.20, "commission_per_lot": 7.0,
}


def parse_hhmm(s) -> int:
    """'14:30' or '14' -> minutes since midnight. Accepts int too."""
    if isinstance(s, int):
        return s * 60
    s = str(s).strip()
    if ":" in s:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    return int(s) * 60


# ── 1. Data loading (auto-detect) ─────────────────────────────────────────────

def load_data(path: str) -> pd.DataFrame:
    """Load XAUUSD data from common formats, return M15 OHLC DataFrame (UTC)."""
    # Try HistData format first (semicolon, no header)
    with open(path) as f:
        first = f.readline()

    if ";" in first:
        df = pd.read_csv(path, sep=";", header=None,
                         names=["dt", "open", "high", "low", "close", "vol"])
        df["datetime"] = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S")
    elif "\t" in first or "Date" in first or "DATE" in first:
        df = pd.read_csv(path, sep=None, engine="python")
        df.columns = [c.strip().lower().replace("<", "").replace(">", "")
                      for c in df.columns]
        # Combine date + time if separate
        if "date" in df.columns and "time" in df.columns:
            df["datetime"] = pd.to_datetime(
                df["date"].astype(str) + " " + df["time"].astype(str),
                errors="coerce")
        else:
            dcol = [c for c in df.columns if "date" in c or "time" in c][0]
            df["datetime"] = pd.to_datetime(df[dcol], errors="coerce")
    else:
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        dcol = [c for c in df.columns if "date" in c or "time" in c][0]
        df["datetime"] = pd.to_datetime(df[dcol], errors="coerce")

    # Normalise OHLC column names
    rename = {}
    for col in df.columns:
        cl = col.lower()
        if cl in ("open", "o"):  rename[col] = "open"
        elif cl in ("high", "h"): rename[col] = "high"
        elif cl in ("low", "l"):  rename[col] = "low"
        elif cl in ("close", "c"): rename[col] = "close"
    df = df.rename(columns=rename)

    df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
    df = df[["open", "high", "low", "close"]].astype(float)

    # Resample to clean M15 (in case source is M1)
    o = df["open"].resample("15min").first()
    h = df["high"].resample("15min").max()
    l = df["low"].resample("15min").min()
    c = df["close"].resample("15min").last()
    m15 = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()

    print(f"Loaded {len(m15):,} M15 candles: "
          f"{m15.index[0].date()} to {m15.index[-1].date()}")
    return m15


# ── 2. Indicators ─────────────────────────────────────────────────────────────

def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm  = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr_ = pd.Series(tr).ewm(span=period, adjust=False).mean()
    plus_di  = 100 * pd.Series(plus_dm,  index=df.index).ewm(span=period, adjust=False).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(span=period, adjust=False).mean()


# ── 3. H1 momentum bias ───────────────────────────────────────────────────────

def compute_h1_bias(m15: pd.DataFrame) -> pd.DataFrame:
    """Resample to H1, compute EMA bias + ADX strength, reindex back to M15."""
    h1 = m15["close"].resample("1h").last().dropna().to_frame("close")
    h1["high"]  = m15["high"].resample("1h").max()
    h1["low"]   = m15["low"].resample("1h").min()
    h1["ema_f"] = ema(h1["close"], EMA_FAST)
    h1["ema_s"] = ema(h1["close"], EMA_SLOW)
    h1["adx"]   = adx(h1, ADX_PERIOD)

    h1["bias"] = 0
    h1.loc[(h1["ema_f"] > h1["ema_s"]) & (h1["adx"] > ADX_THRESHOLD), "bias"] = 1
    h1.loc[(h1["ema_f"] < h1["ema_s"]) & (h1["adx"] > ADX_THRESHOLD), "bias"] = -1

    # Forward-fill H1 bias onto M15 grid (shift 1 to avoid look-ahead)
    bias = h1["bias"].shift(1).reindex(m15.index, method="ffill")
    adx_v = h1["adx"].shift(1).reindex(m15.index, method="ffill")
    return pd.DataFrame({"h1_bias": bias, "h1_adx": adx_v}, index=m15.index)


# ── 4. GARCH vol regime (rolling, walk-forward) ──────────────────────────────

def compute_vol_regime(m15: pd.DataFrame, window: int = GARCH_WINDOW,
                       refit_every: int = 50) -> pd.Series:
    """
    Rolling GARCH(1,1) on M15 log returns -> 1-step-ahead conditional vol.
    Refit every `refit_every` candles for speed (forecast updated between fits
    using the last fitted params). Returns conditional vol (decimal) per candle.
    """
    rets = (np.log(m15["close"] / m15["close"].shift(1)).dropna() * 100)
    vol_fc = pd.Series(index=rets.index, dtype=float)
    n = len(rets)

    last_res = None
    for t in range(window, n - 1):
        if (t - window) % refit_every == 0:
            data = rets.iloc[t - window:t]
            try:
                last_res = arch_model(data, vol="Garch", p=1, q=1,
                                      dist="normal", rescale=False
                                      ).fit(disp="off", show_warning=False)
            except Exception:
                pass
        if last_res is not None:
            try:
                fc = last_res.forecast(horizon=1, reindex=False)
                cv = fc.variance.values[-1, 0]
                vol_fc.iloc[t + 1] = np.sqrt(cv) / 100   # decimal per-candle vol
            except Exception:
                vol_fc.iloc[t + 1] = vol_fc.iloc[t]
        if (t - window) % 5000 == 0:
            print(f"  GARCH: {100*(t-window)/(n-window):.0f}% ...")

    return vol_fc.reindex(m15.index)


def vol_size_multiplier(vol_fc: pd.Series) -> pd.Series:
    """Map vol forecast to a position-size multiplier vs rolling median vol."""
    med = vol_fc.rolling(GARCH_WINDOW, min_periods=200).median()
    ratio = vol_fc / med
    mult = pd.Series(1.0, index=vol_fc.index)        # normal regime
    mult[ratio > VOL_HIGH_MULT] = 0.5                # high vol -> half size
    mult[ratio < VOL_LOW_MULT]  = 1.5                # low vol  -> 1.5x size
    mult[ratio.isna()] = 0.0                          # no forecast -> no trade
    return mult


# ── 5. M15 structure entry signal ────────────────────────────────────────────

def structure_signals(m15: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    Simple, falsifiable structure trigger:
      +1 long  : close breaks above prior `lookback` high then this candle
                 closes back inside after wicking through (sweep + reclaim),
                 OR clean break-and-close above recent range.
      -1 short : mirror.
    Returns signal per candle (decision made at candle close).
    """
    hi = m15["high"].rolling(lookback).max().shift(1)
    lo = m15["low"].rolling(lookback).min().shift(1)
    c  = m15["close"]
    h  = m15["high"]
    l  = m15["low"]

    sig = pd.Series(0, index=m15.index)

    # Sweep + reclaim long: wick below recent low, close back above it
    sweep_long = (l < lo) & (c > lo)
    # Breakout long: close above recent high
    break_long = (c > hi)

    sweep_short = (h > hi) & (c < hi)
    break_short = (c < lo)

    sig[sweep_long | break_long]  = 1
    sig[sweep_short | break_short] = -1
    return sig


# ── 6. Backtest engine ────────────────────────────────────────────────────────

def backtest(m15: pd.DataFrame) -> dict:
    print("Computing H1 momentum bias...")
    h1 = compute_h1_bias(m15)

    print("Computing GARCH vol regime (this is the slow part)...")
    vol_fc = compute_vol_regime(m15)
    size_mult = vol_size_multiplier(vol_fc)

    print("Computing M15 structure signals + ATR...")
    struct = structure_signals(m15)
    atr_v  = atr(m15, ATR_PERIOD)

    df = m15.copy()
    df["h1_bias"]   = h1["h1_bias"]
    df["size_mult"] = size_mult
    df["struct"]    = struct
    df["atr"]       = atr_v
    df["hour"]      = df.index.hour
    df["tod_min"]   = df.index.hour * 60 + df.index.minute
    df = df.dropna(subset=["h1_bias", "size_mult", "atr"])

    equity = ACCOUNT_SIZE
    peak   = ACCOUNT_SIZE
    trades = []
    day_pnl = {}
    current_day = None
    trades_today = 0
    open_trade = None

    for ts, row in df.iterrows():
        day = ts.date()
        if day != current_day:
            current_day = day
            trades_today = 0
            day_pnl[day] = 0.0

        # ---- manage open trade ----
        if open_trade is not None:
            hit_sl = (row["low"] <= open_trade["sl"]) if open_trade["dir"] == 1 \
                     else (row["high"] >= open_trade["sl"])
            hit_tp = (row["high"] >= open_trade["tp"]) if open_trade["dir"] == 1 \
                     else (row["low"] <= open_trade["tp"])
            exit_reason = None
            if hit_sl:
                pnl = -open_trade["risk"]; exit_reason = "SL"
            elif hit_tp:
                pnl = open_trade["risk"] * RR_TARGET; exit_reason = "TP"
            # time stop at session end
            elif row["tod_min"] >= CFG["session_end"]:
                move = (row["close"] - open_trade["entry"]) * open_trade["dir"]
                pnl = open_trade["risk"] * (move / open_trade["stop_dist"])
                exit_reason = "EOD"

            if exit_reason:
                pnl -= open_trade["cost"]
                equity += pnl
                day_pnl[day] += pnl
                peak = max(peak, equity)
                trades.append({**open_trade, "exit": ts, "pnl": pnl,
                               "reason": exit_reason, "equity": equity})
                open_trade = None

        # ---- daily loss limit: stop trading for the day ----
        if day_pnl[day] <= -DAILY_LOSS_LIMIT * ACCOUNT_SIZE:
            continue

        # ---- look for new entry ----
        in_session = CFG["session_start"] <= row["tod_min"] < CFG["session_end"]
        if (open_trade is None and in_session and trades_today < MAX_TRADES_DAY
                and row["size_mult"] > 0 and row["struct"] != 0
                and row["struct"] == row["h1_bias"]):     # all 3 layers agree

            direction = int(row["struct"])
            stop_dist = STOP_ATR_MULT * row["atr"]
            risk_usd  = ACCOUNT_SIZE * BASE_RISK_PCT * row["size_mult"]
            entry = row["close"]
            sl = entry - direction * stop_dist
            tp = entry + direction * stop_dist * RR_TARGET
            cost = CFG["spread_points"] * (risk_usd / stop_dist) + CFG["commission_per_lot"]

            open_trade = {"entry_time": ts, "dir": direction, "entry": entry,
                          "sl": sl, "tp": tp, "risk": risk_usd,
                          "stop_dist": stop_dist, "cost": cost,
                          "size_mult": row["size_mult"]}
            trades_today += 1

    return summarise(trades, day_pnl)


# ── 7. Reporting ──────────────────────────────────────────────────────────────

def summarise(trades: list, day_pnl: dict) -> dict:
    if not trades:
        print("\nNo trades generated. Loosen filters or check data range.")
        return {}

    tdf = pd.DataFrame(trades)
    wins = tdf[tdf["pnl"] > 0]
    losses = tdf[tdf["pnl"] <= 0]
    total_pnl = tdf["pnl"].sum()
    win_rate = len(wins) / len(tdf)
    avg_win = wins["pnl"].mean() if len(wins) else 0
    avg_loss = losses["pnl"].mean() if len(losses) else 0
    expectancy = tdf["pnl"].mean()

    eq = tdf["equity"]
    max_dd = ((eq.cummax() - eq) / eq.cummax()).max()
    final_eq = eq.iloc[-1]
    ret_pct = (final_eq - ACCOUNT_SIZE) / ACCOUNT_SIZE

    daily = pd.Series(day_pnl)
    worst_day_pct = daily.min() / ACCOUNT_SIZE

    # FTMO pass/fail
    breached_daily = worst_day_pct <= -DAILY_LOSS_LIMIT
    breached_total = max_dd >= MAX_DRAWDOWN
    hit_target = ret_pct >= PROFIT_TARGET
    passed = hit_target and not breached_daily and not breached_total

    print("\n" + "=" * 55)
    print("BACKTEST RESULTS — XAUUSD M15 Combined Strategy")
    print("=" * 55)
    print(f"Total trades        : {len(tdf)}")
    print(f"Win rate            : {win_rate*100:.1f}%")
    print(f"Avg win / avg loss  : ${avg_win:.0f} / ${avg_loss:.0f}")
    print(f"Expectancy/trade    : ${expectancy:.2f}")
    print(f"Total P&L           : ${total_pnl:.0f} ({ret_pct*100:+.1f}%)")
    print(f"Max drawdown        : {max_dd*100:.1f}%  (FTMO limit 10%)")
    print(f"Worst day           : {worst_day_pct*100:.1f}%  (FTMO limit 5%)")
    print("-" * 55)
    print(f"Hit 10% target      : {'YES' if hit_target else 'no'}")
    print(f"Breached daily limit: {'YES' if breached_daily else 'no'}")
    print(f"Breached total DD   : {'YES' if breached_total else 'no'}")
    print(f"==> FTMO CHALLENGE  : {'PASS' if passed else 'FAIL'}")
    print("=" * 55)

    tdf.to_csv("results/trades.csv", index=False)
    print("Trade log saved -> results/trades.csv")

    return {"trades": tdf, "passed": passed, "return": ret_pct,
            "max_dd": max_dd, "win_rate": win_rate}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="XAUUSD/BTC/Index M15 combined-strategy FTMO backtest.")
    p.add_argument("csv", help="Path to M15 OHLC CSV")
    p.add_argument("-i", "--instrument", default="xauusd",
                   choices=list(PRESETS.keys()),
                   help="Instrument preset (sets session window + cost model). "
                        "Default: xauusd")
    p.add_argument("--session-start",
                   help="Override session start, HH:MM or HH (GMT). e.g. 14:30")
    p.add_argument("--session-end",
                   help="Override session end, HH:MM or HH (GMT). e.g. 19:00")
    p.add_argument("--spread", type=float,
                   help="Override spread in price points")
    p.add_argument("--commission", type=float,
                   help="Override round-turn commission per lot (USD)")
    args = p.parse_args()

    # Load preset (HH:MM strings) and convert session bounds to minutes
    preset = PRESETS[args.instrument]
    CFG.update(preset)
    CFG["session_start"] = parse_hhmm(preset["session_start"])
    CFG["session_end"]   = parse_hhmm(preset["session_end"])
    # Apply explicit CLI overrides
    if args.session_start is not None: CFG["session_start"] = parse_hhmm(args.session_start)
    if args.session_end   is not None: CFG["session_end"]   = parse_hhmm(args.session_end)
    if args.spread        is not None: CFG["spread_points"] = args.spread
    if args.commission    is not None: CFG["commission_per_lot"] = args.commission

    def fmt(mins): return f"{mins // 60:02d}:{mins % 60:02d}"
    print(f"Instrument: {args.instrument.upper()}  |  "
          f"Session {fmt(CFG['session_start'])}–{fmt(CFG['session_end'])} GMT  |  "
          f"Spread {CFG['spread_points']}  Comm {CFG['commission_per_lot']}/lot")

    data = load_data(args.csv)
    backtest(data)


if __name__ == "__main__":
    main()

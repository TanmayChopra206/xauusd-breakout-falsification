# Compiled Diagnostic Results

All results are walk-forward and net of modelled transaction costs (spread plus $7 per round-turn commission), XAUUSD 2012 to 2022.

## Layer isolation (M15, EOD disabled, hold to SL/TP)

| Variant | Win rate | Break-even WR | Verdict |
|---|---|---|---|
| Structure only | 28.6% | 33.5% | Negative |
| Structure + momentum | 30.1% | 34.0% | Negative |
| Structure + GARCH | 28.7% | 33.1% | Negative |
| Inverted structure only | 30.2% | 33.6% | Negative (net) |

Filters reduce the number of losing trades but cannot create edge that the entry itself lacks.

## Cost attribution (inverted entry)

| Quantity | Value |
|---|---|
| Net P&L | -$63,580 |
| Total cost drag | $78,559 |
| **Gross P&L** | **+$14,979** |
| **Gross expectancy per trade** | **+$3.40** |
| Per-trade cost (reconciled) | approx. $17.70 (roughly 0.54 lots x $0.20 spread plus $7 commission) |

The inverted signal has positive gross expectancy, but it is trapped beneath the cost floor.

## Target widening (M15 inverted)

| Target | Trades | Win rate | Gross exp/trade |
|---|---|---|---|
| 2.5R | 4,431 | 30.2% | $3.38 |
| 3.0R | 4,213 | 26.8% | $3.46 |
| 4.0R | 3,959 | 22.3% | $3.14 |
| 5.0R | 3,714 | 19.5% | $2.68 |

Gross expectancy flatlines; the edge lives entirely in the first move off entry.

## Timeframe step-up (inverted structure only)

| Timeframe | Trades | Gross exp/trade | Net P&L | Time-stop exits |
|---|---|---|---|---|
| M15 | 4,431 | +$3.38 | -$63,580 | 129 / 4,431 |
| H1 | 2,214 | -$1.18 | -$29,934 | 506 / 2,214 |
| H4 | 1,084 | +$2.81 (confounded) | -$7,340 | 728 / 1,084 |

**H4 caveat:** 67% of H4 trades exited via the 24-hour time-stop rather than SL/TP, so the H4 figure measures the time-stop as much as the signal and is inconclusive on its own. The M15 flatline and H1 sign-flip independently reject the "scales up" thesis.

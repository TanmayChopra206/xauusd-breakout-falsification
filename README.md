# Fading Intraday Breakouts on Gold: A Falsification Study

A walk-forward, cost-inclusive backtest looking at whether a mechanical breakout/sweep entry has any tradeable edge on XAUUSD intraday. It does not, and this repo documents precisely why.

The interesting part is not the strategy (it loses). It is the teardown: pinning down where a faint real edge lives, attributing the net loss to its true cause, and controlling for the confounds that make weak backtests misleading.

![Gross edge vs cost floor](figures/m15_expectancy_flatline.png)

## The finding in one line

Fading M15 Gold breakouts has a small but real gross edge (roughly $3.40 per trade) that is structurally trapped beneath a cost floor of around $17.70 per trade. It does not scale with target size and does not survive a timeframe change. A genuine microstructure effect, but not tradeable at retail-accessible costs.

## What is in here

| File | What it is |
|---|---|
| [`RESEARCH_NOTE.md`](RESEARCH_NOTE.md) | The full write-up: hypothesis, method, the falsification chain, results, honest limitations |
| [`src/xauusd_backtest.py`](src/xauusd_backtest.py) | The backtest engine: walk-forward GARCH, momentum, structure entry, FTMO risk accounting |
| `figures/` | Result charts |
| `results/` | Compiled diagnostic tables |

## Method at a glance

- Walk-forward rolling GARCH(1,1) with no look-ahead bias
- Three isolated layers: GARCH vol regime, H1 momentum bias, M15 structure entry
- Costs applied to every trade and reconciled to model arithmetic
- Falsification chain: exit fix, layer isolation, signal inversion, cost attribution, target widening, timeframe step-up
- Confound controls: trade-count monotonicity, time-stop contamination flagged, price-scaling validated across timeframes

## How to run

```bash
pip install arch pandas numpy matplotlib
python src/xauusd_backtest.py path/to/XAUUSD_M15.csv -i xauusd
```

Free M15 data is available from a MetaTrader 5 demo account (History Centre > XAUUSD > M15 > export) or HistData.com.

## The honest takeaway

Simple mechanical rules on liquid, retail-saturated intraday instruments are close to efficient at the level such rules can access. If any edge exists, it is more likely to come from execution quality, regime-conditioning, or less-efficient niches than from a mechanical entry rule. This study rules out the most common beginner trap empirically rather than by assertion.

*This is a falsification study. The negative result is the result.*

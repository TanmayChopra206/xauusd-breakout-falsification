# A Faint but Untradeable Edge: Fading Intraday Breakouts on Gold

**A falsification study of mechanical breakout/sweep entries on XAUUSD**

*Walk-forward backtest, 10 years of M15 data (2012–2022), all results net of modelled transaction costs.*

---

## TL;DR

I tested whether a mechanical structure-based entry (breakout / liquidity-sweep) has tradeable edge on Gold intraday. It does not. The original breakout-following entry loses money net of costs. Its inverse — *fading* breakouts — has a small but real **gross** edge of ~$3.40 per trade, which is structurally trapped beneath a ~$17.70 per-trade cost floor. The effect is localised to the M15 timeframe: it does not scale with a wider target, and it does not survive a move to H1 or H4. Conclusion: a genuine microstructure phenomenon that is not tradeable with retail-accessible costs.

The point of this note is not the (negative) result. It is the teardown — isolating where an apparent edge lives, attributing the loss to its true cause, and controlling the confounds that make weak backtests lie.

---

## 1. Motivation and hypothesis

"Liquidity sweep" / "structure break" entries are popular in retail trading communities but rarely subjected to rigorous, cost-inclusive, walk-forward testing. The intuition — that price reverts after sweeping a recent swing high/low where stops cluster — is testable. I formalised it into a mechanical rule and asked a single question:

> Does a mechanical breakout/sweep entry on XAUUSD have positive expectancy net of realistic transaction costs?

A null result was the expected outcome. Liquid, retail-saturated intraday markets are close to efficient at the level a simple mechanical rule can access. The aim was to *measure* the failure precisely, not to find a winner.

## 2. Setup

**Instrument / data.** XAUUSD, M15 candles, 2012-05-15 to 2022-03-04 (≈230k candles). Prices validated against the known Gold range for the period (min $1047, max $2070, mean $1424).

**Entry signal (mechanical structure).** Long on a sweep-and-reclaim of the recent N-bar low, or a clean close above the recent N-bar high; short is the mirror. The inverted variant flips the sign (fade the move).

**Three independent layers**, tested both combined and in isolation:
1. **GARCH(1,1)** on M15 returns — rolling, walk-forward, 1-step-ahead conditional volatility → position-size scaling and a high-vol go/no-go filter.
2. **H1 momentum** — EMA(20/50) crossover with an ADX>25 trend-strength filter → directional bias.
3. **M15 structure** — the entry trigger above.

**Risk model.** 0.5% base risk per trade, vol-scaled; structural stops at 1.5× ATR; 2.5:1 reward:risk target; FTMO-style daily-loss and max-drawdown accounting.

**Cost model.** Spread (proportional to position size) + $7 flat commission per round-turn. The flat commission is the decisive term for small intraday positions.

**Validation discipline.** GARCH is re-fit on a rolling window — strictly walk-forward, no look-ahead. Costs are applied to every trade. Layers are isolated to attribute edge. Trade counts are checked for logical consistency (a filter can only reduce trade count). Cost magnitude is reconciled against the model arithmetic.

## 3. The diagnostic sequence

The study proceeded as a chain of falsification steps. Each step was designed to rule out a specific benign explanation for the loss.

### 3.1 Is the exit cutting winners?

The baseline closed positions at session end. This suppressed the realised reward:risk ratio (1.48 vs a 2.5 target) by truncating winners. Removing the session stop (holding to SL/TP, 24h cap) lifted realised R:R to ~1.98 — confirming the exit *was* bleeding winners — but win rate fell from 36.3% to 30.1%, leaving expectancy negative. **The exit was a real defect, but fixing it did not create edge.**

### 3.2 Where does the (lack of) edge live? — layer isolation

| Variant | Win rate | Break-even WR | Verdict |
|---|---|---|---|
| Structure only | 28.6% | 33.5% | Negative |
| Structure + momentum | 30.1% | 34.0% | Negative |
| Structure + GARCH | 28.7% | 33.1% | Negative |

The raw entry is unprofitable in isolation. Filters reduce the *number* of losing trades but cannot manufacture an edge that the entry lacks. This is the central result: **the entry signal, not the filtering, is where a strategy must earn its edge — and this entry has none.**

### 3.3 Is the signal anti-predictive? — inversion

Inverting the entry (fading breakouts) improved win rate only marginally (28.6% → 30.2%), still below break-even. Crucially, the inverted result was **not a mirror image** of the original — both lost. That signature points to *noise plus costs*, not a directional edge being discarded.

### 3.4 The decisive check — cost attribution

This is where the real story emerged. On the inverted entry:

- Net P&L: **−$63,580**
- Total cost drag: **$78,559**
- **Gross P&L: +$14,979** → **+$3.40 / trade gross**

The inverted signal has *positive gross expectancy*. Fading intraday Gold breakouts captures a real, tiny reversion — consistent with retail stop-clusters being swept at M15 pivots. But the reaction is smaller than the cost floor. Per-trade cost reconciled cleanly to the model: ~0.54 lots × $0.20 spread + $7 commission ≈ $17.70. The flat commission dominates and is punitive on small intraday positions.

**This reframes the conclusion from "no edge" to "faint real edge, swallowed by fixed costs"** — a materially different and more precise claim.

## 4. Can the edge escape the cost floor?

Two routes, both tested and both rejected.

### 4.1 Widen the target (amortise cost over a larger move)

| Target | Trades | Win rate | Gross exp/trade |
|---|---|---|---|
| 2.5R | 4,431 | 30.2% | $3.38 |
| 3.0R | 4,213 | 26.8% | $3.46 |
| 4.0R | 3,959 | 22.3% | $3.14 |
| 5.0R | 3,714 | 19.5% | $2.68 |

Gross expectancy per trade **flatlines** (~$3) as the target widens and win rate decays in lockstep. The entire edge lives in the first move off the entry; there is no continuation to harvest. Net loss shrinks at 5R only because fewer trades pay less total spread — not because the edge grew.

### 4.2 Step up timeframe (make fixed cost negligible)

| Timeframe | Trades | Gross exp/trade | Net P&L | Time-stop exits |
|---|---|---|---|---|
| H1 | 2,214 | **−$1.18** | −$29,934 | 506 / 2,214 |
| H4 | 1,084 | +$2.81 | −$7,340 | **728 / 1,084** |

On **H1** the gross edge *inverts to negative* — fading H1 breakouts is mechanically wrong, not merely weak. On **H4** gross expectancy is positive but no larger than M15, so the cost-amortisation thesis fails.

> **Limitation (stated, not buried).** The H4 test is confounded: 728 of 1,084 trades (67%) exited via the 24h time-stop rather than SL/TP. The H4 figure therefore measures the time-stop as much as the signal and is **inconclusive on its own**. It does not need to carry the verdict — the M15 flatline and the H1 sign-flip independently kill the "scales up" thesis. A clean H4 test would require a hold horizon matched to the timeframe and is left as future work.

The non-monotonic behaviour across adjacent timeframes (M15 positive, H1 negative, H4 positive-but-confounded) is itself the evidence: this is not a stable phenomenon being scaled, but an M15-specific microstructure effect.

## 5. Conclusion

Fading intraday breakouts on Gold is a **genuine but untradeable** phenomenon. A small reversion edge (~$3.40/trade gross) exists at M15, consistent with retail liquidity being swept at short-horizon pivots. It is structurally trapped beneath the bid/ask + commission cost floor, does not scale with target size, and does not survive a timeframe change. No version of this mechanical entry funds an account net of retail-accessible costs.

More broadly, the result is the expected one: simple mechanical rules on liquid, retail-saturated intraday instruments are close to efficient at the level such rules can access. The contribution here is methodological — locating the edge precisely in time, attributing the net loss to its true cause, and resisting the confounds (exit truncation, filter-count inconsistency, time-stop contamination) that make weak backtests appear to say more than they do.

## 6. What I would do differently / next

- **Match hold horizon to timeframe** to obtain a clean (unconfounded) H4 test.
- **Sub-period stability** as a distribution (per-year Sharpe), not a single 10-year aggregate, on any variant showing net positive — to detect regime concentration (2013 and 2020 were exceptional Gold-vol years).
- **Accept the broader lesson:** edge on liquid intraday instruments, if it exists, is more likely in execution, regime-conditioning, or less-efficient niches than in a simple mechanical entry rule.

---

### Methods appendix — reproducibility notes

- Walk-forward GARCH(1,1), rolling window, 1-step-ahead forecast; no look-ahead.
- All P&L net of modelled spread + commission; cost magnitude reconciled to model arithmetic.
- Layer isolation harness with cached GARCH/momentum computations (keyed to dataset + parameters; identical across exit/layer variants).
- Trade-count monotonicity verified under matched exit configurations (a filter strictly reduces trade count).
- Price-scaling auto-detection validated independently on M15, H1, and H4 feeds against the known Gold price range.

*This is a falsification study. The negative result is the result.*

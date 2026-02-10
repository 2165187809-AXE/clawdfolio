# Options Strategy Playbook v2.1

This document is the core options framework behind `clawdfolio` option workflows.

## Provenance

This playbook is based on:

- structured study from multiple authoritative options books and courses,
- rigorous data analysis and backtesting,
- multi-year live options trading experience.

The goal is not to predict every move. The goal is to express views, control risk, and compound cashflow with discipline.

## Scope and Safety

- This is a strategy framework, not financial advice.
- `clawdfolio` options workflows are designed for monitoring, decision support, and execution planning.
- Keep strict risk controls for margin, leverage, and assignment handling.

## 1. Core Worldview

### 1.1 Options are tools, not beliefs

Options are instruments for:

- view expression,
- risk transfer,
- cashflow engineering.

Without investment judgment, options amplify mistakes.

### 1.2 Investing remains simple

Long-term return improvement comes from:

- improving exit prices,
- reducing entry cost basis.

### 1.3 Seller edge

Long-run edge in option selling comes from:

- time decay (theta),
- implied volatility (IV) mean reversion.

High-IV panic regimes usually provide better premium quality than low-IV calm regimes.

### 1.4 Main seller risks

- Gamma risk spikes near expiry and near ATM.
- Margin and leverage expansion can force liquidation before a thesis plays out.

### 1.5 Keep priority clear

In covered-call income mode:

- stock return is the main dish,
- option premium is the side dish.

Do not sacrifice large upside for small premium.

## 2. Covered Call (CC) Playbook

### 2.1 Core positioning

Covered call is a trade-off:

- adds premium cashflow,
- caps part of upside.

It is usually suitable for investors already willing to hold the underlying.

### 2.2 Scenario A: Income collection (starter mode)

#### Preconditions

- long-term hold intent exists,
- underlying is relatively stable,
- option chain has good liquidity.

#### Opening process

- Select underlying first.
- Start with monthly expiries for lower management pressure.
- Choose OTM strike with a view component.
- If no strong view, use a systematic anchor around `delta ~= 0.20`.

#### Management at/near expiry

When spot breaks strike:

- allow assignment only if you truly want to exit,
- buy back if stock ownership is priority,
- or roll (most common) by buying back current call and selling a farther expiry call.

When spot stays below strike:

- let expire and reopen next cycle, or
- roll earlier if assignment risk rises near close.

#### Pause condition

Pause CC when:

- trend is strongly bullish,
- IV is low,
- premium is too thin for the upside you are giving away.

### 2.3 Scenario B: Take-profit with structure

#### Passive take-profit

- Use farther OTM calls.
- Strike equals your predefined acceptable exit price.
- Prefer expiries >= 1 month to reduce noise decisions.

#### Active take-profit

- If you already want to exit soon, use ATM/ITM calls to lock gains and collect residual time value.
- If fundamentals materially deteriorate, exit stock directly instead of waiting for option decay.

### 2.4 Scenario C: Cost-basis reduction in weak environments

Use CC to offset part of entry cost when:

- you still want long-term ownership,
- short-term breakout probability is limited,
- IV is elevated in stress.

Practical bias:

- medium expiry (often >= 1 month),
- OTM strikes with room for upside,
- commonly around `delta ~= 0.30` depending on conviction.

### 2.5 Scenario D: Tactical hedge (not permanent)

CC hedge is partial and temporary:

- use only when near-term downside risk is elevated,
- accept upside cap as hedge cost,
- do not maintain perpetual hedge against a long-term bullish thesis.

Typical setup:

- strike closer to ATM than income mode,
- expiry around 1-2 months.

### 2.6 Strike selection via delta

Core abstraction:

- selecting strike is selecting portfolio delta.
- covered call delta is approximately `1 - call_delta`.

Dynamic behavior:

- if price rises, call delta rises, portfolio delta falls (auto de-risking),
- if price falls, call delta falls, portfolio delta rises (hedge weakens).

Do not evaluate only entry delta. Evaluate path-dependent delta after price moves.

## 3. Sell Put Playbook

### 3.1 Core positioning

Selling puts is a bullish strategy:

- best outcome: keep premium,
- adverse outcome: buy stock at strike (with premium offset).

Think of it as a paid limit order only when you are comfortable owning the stock.

### 3.2 Opening triad

#### Underlying

- thesis must be bullish,
- fundamentals must justify ownership under drawdown.

#### Expiry

- shorter tenor emphasizes theta harvesting,
- longer tenor emphasizes directional delta and IV normalization.
- monthly tenor is generally a balanced starting point.

#### Strike

Trade-off triangle:

- probability of success,
- directional participation,
- premium amount.

Reference anchor for beginners: OTM `delta ~= 0.30`.

### 3.3 Management by scenario

#### Price drops below strike

Three valid paths:

- accept assignment and own shares (cost basis = strike - premium),
- roll forward (buy back old put, sell new farther expiry put),
- stop-loss and exit when thesis is structurally broken.

Roll only if thesis is still intact.

#### Price rallies and option decays fast

Two choices:

- hold to expiry for simplicity,
- close early to free margin and redeploy if a better setup exists.

#### Price sits near ATM close to expiry

Gamma risk is high. Early roll is often cleaner than forcing last-day resolution unless assignment is explicitly desired.

### 3.4 Early assignment handling

Early assignment can happen, especially with deep ITM and low remaining extrinsic value.

Mitigation:

- avoid waiting to the final days,
- roll or close earlier.

If assigned early:

- treat it as a state change, not a strategy failure,
- reframe with stock + new option structure according to the current thesis.

### 3.5 Delta framework and CC parity

For short puts:

- ATM put delta around `0.5`,
- OTM put around `0.3`,
- ITM put around `0.7` (more aggressive).

As spot falls, put delta rises and risk accelerates.
As spot rises, put delta falls and participation decays.

Covered call and short put are tightly related by put-call parity. Manage the whole payoff shape, not isolated legs.

## 4. Risk Control and No-Go Zones

### 4.1 Avoid naked short call for beginners

Reasons:

- limited edge in many regimes,
- theoretically unlimited loss,
- difficult recovery dynamics in strong uptrends.

### 4.2 Margin and leverage first

Approximate margin intuition for short ATM put:

- `margin ~= strike * 100 * 20%` (broker- and regime-dependent).

Risk is not just initial margin. Risk is margin expansion during adverse moves.

Operational guardrails:

- keep meaningful unused margin buffer,
- do not run near max margin utilization,
- manage account-level leverage, not just single positions.

Practical leverage reference:

- beginners: keep leverage around `<= 1.6`,
- advanced with robust risk process: can extend, but only with strict controls.

## 5. Operational Decision Checklist

Before opening:

- Is thesis clear and testable?
- Is IV regime favorable?
- Is liquidity acceptable?
- Is margin buffer still safe after stress move assumptions?

Before expiry week:

- Is gamma risk acceptable?
- Do you prefer assignment, roll, or close?
- Has thesis changed?

After adverse move:

- Is this noise or thesis break?
- If thesis intact, is roll/assignment plan pre-defined?
- If thesis broken, cut and reset.

## 6. Mapping to Clawdfolio Features

`clawdfolio` supports this framework through:

- option quote and Greeks inspection (`clawdfolio options quote`),
- chain structure and strike scouting (`clawdfolio options chain`),
- expiry selection context (`clawdfolio options expiries`),
- stateful buyback trigger monitoring (`clawdfolio options buyback`),
- workflow automation in `clawdfolio finance`.

## 7. Version Notes

### v2.1

- Added this dedicated strategy playbook as the canonical options methodology reference.
- Standardized CC and Sell Put logic with explicit delta, gamma, margin, and lifecycle management.
- Formalized risk guardrails based on backtested and live-trading practice.

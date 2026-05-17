"""Hand-written framing text per observation type (DEC-008).

Every entry has three fields the UI surfaces verbatim, with `{ticker}` substituted:
    - headline
    - what_camps_read_into_it
    - what_to_consider

No buy/sell language anywhere (DEC-001). If you find yourself adding a new
observation type, take the time to write the framing thoughtfully — that
friction is the point.
"""

from __future__ import annotations

OBSERVATION_TEMPLATES: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------
    "ma_crossover_bullish": {
        "headline": "50-day moving average crossed above the 200-day on {ticker} (a 'golden cross')",
        "what_camps_read_into_it": (
            "Trend-following traders treat a golden cross as momentum confirmation — "
            "evidence the medium-term trend has turned up. Contrarians point out that "
            "moving-average crossovers are lagging by construction: the cross fires "
            "after a meaningful price move has already happened, so by the time it "
            "appears the move it's confirming may be nearly over. Academic studies "
            "(Brock-Lakonishok-LeBaron 1992 and later replications) found weak and "
            "regime-dependent excess returns from MA rules on US equities; the effect "
            "is much smaller after transaction costs and largely disappears in the "
            "modern era. The disagreement is genuine and longstanding."
        ),
        "what_to_consider": (
            "1. Is this confirming news you'd already accounted for, or is it new information?\n"
            "2. What was the underlying reason for the price rise that drove the cross — "
            "earnings, sentiment, macro, or just noise?\n"
            "3. How does the price now compare to where it was 6 and 12 months ago?\n"
            "4. If you'd bought every golden cross on {ticker} historically, would you "
            "have done well? (See the honesty layer below.)\n"
            "5. Would you be considering action if you'd never heard of this pattern?"
        ),
    },
    # ------------------------------------------------------------------
    "ma_crossover_bearish": {
        "headline": "50-day moving average crossed below the 200-day on {ticker} (a 'death cross')",
        "what_camps_read_into_it": (
            "Trend-followers read a death cross as confirmation that the medium-term "
            "trend has rolled over and treat it as a reason to reduce exposure. "
            "Contrarians and mean-reversion traders point out that, like the golden "
            "cross, this signal lags the actual move — by the time it fires, most of "
            "the decline it's flagging has often already happened, and the next-day "
            "reaction can be a bounce. Empirically, death crosses on the S&P 500 "
            "have preceded both deep bear markets (1929, 2008) and large bull-market "
            "head-fakes (2010, 2011, 2016, 2018). The signal alone does not "
            "distinguish between those cases."
        ),
        "what_to_consider": (
            "1. Has the fundamental story changed, or only the price?\n"
            "2. What event drove the price drop that produced the cross?\n"
            "3. Is the broader market also rolling over, or is {ticker} idiosyncratic?\n"
            "4. Historically on {ticker}, has a death cross led to further declines "
            "or to mean-reversion? (See the honesty layer below.)\n"
            "5. If you act now, what specifically would change your mind in 3 months?"
        ),
    },
    # ------------------------------------------------------------------
    "new_52w_high": {
        "headline": "{ticker} just closed at a new 52-week high",
        "what_camps_read_into_it": (
            "Momentum investors treat new highs as confirmation that an uptrend is "
            "intact — there are no overhead sellers from a higher price, since no "
            "one bought higher and is waiting to break even. Value investors and "
            "mean-reversion traders see the same data and read it as evidence the "
            "asset is at its most expensive in a year and likely to revert. "
            "Empirically, both camps are sometimes right: stocks at 52-week highs "
            "have outperformed on average (the 'high-momentum anomaly') but the "
            "distribution is wide and individual outcomes are very noisy."
        ),
        "what_to_consider": (
            "1. Are you considering action because of the high itself, or because "
            "of something the company actually did?\n"
            "2. What's the valuation now versus 6 months ago?\n"
            "3. Is the broader market also at highs, or is {ticker} unusual?\n"
            "4. If you'd bought {ticker} on every prior 52w high, how would you "
            "have done? (See the honesty layer below.)\n"
            "5. Is FOMO part of the reason you're looking at this right now?"
        ),
    },
    # ------------------------------------------------------------------
    "new_52w_low": {
        "headline": "{ticker} just closed at a new 52-week low",
        "what_camps_read_into_it": (
            "Momentum traders often treat new lows as a sell signal — the same "
            "logic in reverse: no one bought below this price and is waiting to "
            "exit, so there's no natural support. Value investors often treat new "
            "lows as a potential buying opportunity if the underlying business is "
            "unchanged — the cheaper the price, the higher the future expected "
            "return. The disagreement persists because new lows alone, without "
            "knowing why the price has fallen, don't determine which interpretation "
            "wins. Sometimes the market knows something you don't; sometimes it's "
            "overreacting."
        ),
        "what_to_consider": (
            "1. Why has the price fallen — has the fundamental story changed?\n"
            "2. Is this a sector- or market-wide drawdown, or company-specific?\n"
            "3. Have analyst estimates or guidance materially changed?\n"
            "4. Historically on {ticker}, did new 52w lows mark capitulation or "
            "continuation? (See the honesty layer below.)\n"
            "5. If you act, what's your exit plan if it keeps falling another 20%?"
        ),
    },
    # ------------------------------------------------------------------
    "vol_regime_elevated": {
        "headline": "30-day realized volatility on {ticker} is in the top 10% of its 2-year range",
        "what_camps_read_into_it": (
            "Risk-managed investors treat elevated vol as a reason to size positions "
            "down — the same dollar exposure now carries more risk. Vol-targeting "
            "strategies (popular with systematic funds) will mechanically reduce "
            "exposure in this regime. Active traders sometimes argue the opposite: "
            "high vol is when options are expensive but also when the biggest "
            "directional moves happen. Both views agree on the fact (vol is high) "
            "and disagree on what to do about it. There's no academic consensus on "
            "whether elevated vol precedes positive or negative returns; the effect "
            "is regime-dependent."
        ),
        "what_to_consider": (
            "1. What's driving the vol — a known event, or unexplained?\n"
            "2. Are you sizing this position assuming average vol or current vol?\n"
            "3. Are you about to act on a price move that's within normal "
            "high-vol noise?\n"
            "4. How have past elevated-vol regimes resolved on {ticker}? "
            "(See the honesty layer below.)\n"
            "5. If you act now and the vol resolves the other way, how does that "
            "feel?"
        ),
    },
    # ------------------------------------------------------------------
    "vol_regime_compressed": {
        "headline": "30-day realized volatility on {ticker} is in the bottom 10% of its 2-year range",
        "what_camps_read_into_it": (
            "One school of thought (associated with Hyman Minsky and revived by "
            "vol traders) holds that low vol is itself a risk signal — quiet "
            "periods tend to precede regime breaks, and 'low vol begets high vol.' "
            "Another view is the opposite: compressed vol simply reflects a stable "
            "fundamental environment and there's no information in it about future "
            "direction. The 2017-early 2018 stretch on US equities, ending in the "
            "February 2018 'volmageddon,' is the canonical example of the first "
            "camp being right; long stretches of the 2013-2016 period are examples "
            "of the second. The signal alone doesn't tell you which you're in."
        ),
        "what_to_consider": (
            "1. Are you sizing this position assuming current low vol persists?\n"
            "2. Is the asset cheap, expensive, or fair right now — independent "
            "of how quiet it is?\n"
            "3. Have you considered what happens to your position if vol triples?\n"
            "4. How have past compressed-vol regimes resolved on {ticker}? "
            "(See the honesty layer below.)\n"
            "5. If something breaks the calm — earnings miss, macro shock — what's "
            "your plan?"
        ),
    },
    # ------------------------------------------------------------------
    "drawdown_significant": {
        "headline": "{ticker} is currently more than 15% below its 1-year high",
        "what_camps_read_into_it": (
            "Value investors often treat a drawdown of this size on a fundamentally "
            "sound business as an opportunity — the cheaper the asset, the higher "
            "the future expected return, all else equal. Momentum and trend-following "
            "investors treat the same data as a warning: the market is repricing the "
            "asset, and 'cheap' assets can get cheaper for reasons that aren't "
            "obvious from a chart. Which view is right depends entirely on what "
            "caused the drawdown — multiple compression, earnings deterioration, "
            "or a one-off event — and the chart alone won't tell you."
        ),
        "what_to_consider": (
            "1. What specifically caused the drawdown — earnings, guidance, macro, "
            "sector rotation, or unexplained?\n"
            "2. Has the long-term thesis materially changed, or only the price?\n"
            "3. If you're considering buying, what's your exit plan if it falls "
            "another 20%?\n"
            "4. Historically on {ticker}, has a >15% drawdown marked the start "
            "of recovery or continuation? (See the honesty layer below.)\n"
            "5. Is this position already a large part of your portfolio? Adding "
            "to losers can compound concentration risk."
        ),
    },
    # ------------------------------------------------------------------
    "correlation_decoupling": {
        "headline": "{ticker}'s 60-day correlation with the benchmark has dropped sharply",
        "what_camps_read_into_it": (
            "When a stock decouples from its benchmark, that can mean one of two "
            "things: (1) something idiosyncratic is happening — a merger, a major "
            "product event, sector rotation — that's worth understanding; or "
            "(2) it's a statistical artifact from a noisy 60-day window and will "
            "revert. Diversification-minded investors notice decoupling as a "
            "(temporary) risk-reduction effect; factor investors may see it as "
            "evidence the stock has moved into a different style bucket. Without "
            "knowing the cause, neither read is more correct than the other."
        ),
        "what_to_consider": (
            "1. What story explains why {ticker} is moving differently from the "
            "market right now? Can you name it?\n"
            "2. Is the decoupling driven by {ticker} moving on its own, or by "
            "the market moving without it?\n"
            "3. Has anything material changed in the underlying business?\n"
            "4. How long do past decouplings on {ticker} typically last? "
            "(See the honesty layer below.)\n"
            "5. If the correlation re-couples next week, does that change your view?"
        ),
    },
}


def get_template(observation_type: str) -> dict[str, str] | None:
    """Return the template dict for an observation type, or None if unknown."""
    return OBSERVATION_TEMPLATES.get(observation_type)


def render_template(observation_type: str, ticker: str) -> dict[str, str] | None:
    """Return the template with `{ticker}` substituted. None if unknown type."""
    tmpl = OBSERVATION_TEMPLATES.get(observation_type)
    if tmpl is None:
        return None
    return {k: v.format(ticker=ticker) for k, v in tmpl.items()}

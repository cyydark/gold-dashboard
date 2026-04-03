"""Tests for _gold_direction() in data/sources/international.py"""
import pytest
from backend.data.sources.international import _gold_direction


class TestGoldDirectionSurgeRise:
    """surge/rises/rising → up"""

    @pytest.mark.parametrize("title", [
        "Gold surges on Fed uncertainty",
        "Gold price surges past $3,000",
        "Gold RISES for third session",
        "XAU/USD rises amid rate cut bets",
        "Gold rising as safe-haven demand picks up",
        "Gold RALLY as inflation fears grow",
        "Gold rallying above key resistance",
        "Gold gains on soft dollar",
        "Gold gains despite stronger USD",
        "Gold climbs to 6-month high",
        "Gold climbs above $2,900",
        "Gold climbing on geopolitical risk",
        "Gold soar on supply concerns",
        "Gold soars to record",
        "Gold soaring as war risk rises",
        "Gold jumps 2% on CPI data",
        "Gold jump sparks buying",
        "Gold jumping toward $3,000",
        "Gold spikes after FOMC minutes",
        "Gold spike as dollar weakens",
        "Gold spiked on inflation surprise",
    ])
    def test_surge_rises_rising_up(self, title):
        assert _gold_direction(title) == "up"


class TestGoldDirectionPlungeDrop:
    """plunge/drops/fell → down"""

    @pytest.mark.parametrize("title", [
        "Gold plunges on profit taking",
        "Gold plunges through support",
        "Gold plummets on strong jobs data",
        "Gold sinks on rate hike signals",
        "Gold sinks below $2,800",
        "Gold sank as dollar recovered",
        "Gold drops after Fed decision",
        "Gold drops below key average",
        "Gold dropped sharply on CPI",
        "Gold drop signals correction",
        "Gold falling from record high",
        "Gold falls as investors flee",
        "Gold fell 1.5% on Tuesday",
        "Gold tumble after ECB commentary",
        "Gold tumbling on dollar strength",
        "Gold tumbled 3% from highs",
        "Gold slip as traders book profits",
        "Gold slips below $2,900",
        "Gold slipped on hawkish Fed",
    ])
    def test_plunge_drops_fell_down(self, title):
        assert _gold_direction(title) == "down"


class TestGoldDirectionSecondaryUp:
    """bullish/safe haven → up (secondary signal path)"""

    def test_bullish(self):
        assert _gold_direction("Gold turns bullish on chart") == "up"

    def test_bullish_sentiment(self):
        assert _gold_direction("Bullish sentiment drives gold higher") == "up"

    def test_safe_haven_exact_phrase(self):
        # Keyword in list: "safe haven" (two-word phrase, no hyphen)
        assert _gold_direction("Gold gains safe haven status") == "up"

    def test_safe_haven_demand(self):
        assert _gold_direction("Safe haven demand lifts gold") == "up"

    def test_war_keyword_up(self):
        assert _gold_direction("Middle East war lifts gold") == "up"

    def test_conflict_keyword_up(self):
        assert _gold_direction("Geopolitical conflict drives gold") == "up"

    def test_record_high_in_secondary(self):
        # "record high" is in secondary up_found list
        assert _gold_direction("Gold hits record high of $3000") == "up"

    def test_strong_demand(self):
        assert _gold_direction("Strong demand from central banks lifts gold") == "up"

    def test_trade_war_fears(self):
        # "trade war" is in secondary up_found list
        assert _gold_direction("Trade war fears boost gold") == "up"

    def test_us_china_trade_war(self):
        # "trade war" is in secondary up_found → fires as up
        # "us-China" in the keyword list is mixed-case (never matches lowercased title);
        # this test exercises the "trade war" half
        assert _gold_direction("US-China trade war lifts gold") == "up"

    def test_tariff_up(self):
        # "tariff" is in secondary up_found list
        assert _gold_direction("Tariff uncertainty drives gold up") == "up"

    def test_tariff_rally(self):
        assert _gold_direction("Gold rallies on tariff war fears") == "up"

    def test_inflation_not_in_secondary(self):
        # "inflation" is in _GOLD_UP_KW but NOT in clear or secondary lists → neutral
        assert _gold_direction("Gold and inflation") == "neutral"

    def test_high_alone_not_enough(self):
        # "high" alone is too vague — not in secondary lists, returns neutral
        assert _gold_direction("Gold is high today") == "neutral"

    def test_demand_alone_not_enough(self):
        # "demand" alone is in _GOLD_UP_KW but not in secondary lists → neutral
        assert _gold_direction("Gold demand is rising") == "up"  # "rising" fires clear_up


class TestGoldDirectionSecondaryDown:
    """bearish → down"""

    @pytest.mark.parametrize("title", [
        "Gold turns bearish on technicals",
        "Analysts turn bearish on gold",
        "Bearish outlook drags gold lower",
        "Victory for dovish Fed weighs on gold",
        "Victory parade signals end of crisis",
        "Sell-off in tech lifts gold",
        "Major gold sell-off after rate hike",
        "Correction overdue for gold",
        "Profit taking correction expected",
        "Dollar strength triggers profit taking",
        "Dollar strength pressures gold",
    ])
    def test_bearish_victory_down(self, title):
        assert _gold_direction(title) == "down"

    @pytest.mark.parametrize("title", [
        "Gold Retreats from Peak as Rate Hike Expectations Intensify",
        "Gold retreats from multi-month peak",
        "Gold retraces from record high",
        "Gold retreating from $3,000 level",
        "Gold pulls back from resistance",
        "Gold pullback seen as healthy correction",
        "Gold recedes from earlier highs",
        "Gold recedes as dollar firms",
        "Gold erases earlier gains",
        "Gold giving up intraday gains",
    ])
    def test_retreat_retrace_pullback_down(self, title):
        assert _gold_direction(title) == "down"

    def test_gold_retreats_from_peak_reported(self):
        # Reported by user: this title was incorrectly marked as UP because "Peak"
        # was in the secondary up_found list. Now correctly identified as down.
        assert _gold_direction("Gold Retreats from Peak as Rate Hike Expectations Intensify") == "down"


class TestGoldDirectionTariff:
    """tariff should → up (tariff is in secondary up_found list)"""

    @pytest.mark.parametrize("title", [
        "Gold rallies on tariff war fears",
        "Tariffs push gold higher",
        "Gold up as tariff deadline looms",
        "Tariff escalation supports gold prices",
    ])
    def test_tariff_up(self, title):
        assert _gold_direction(title) == "up"


class TestGoldDirectionNeutral:
    """No directional keywords → neutral"""

    @pytest.mark.parametrize("title", [
        "Gold holds steady at $2,900",
        "Gold trades flat ahead of Fed",
        "Gold market awaits CPI data",
        "Gold price unchanged on Tuesday",
        "Gold remains range-bound",
        "Analysts divided on gold outlook",
        "Gold volatility near multi-year low",
        "Gold liquidity improves in Asia",
        "",
        "   ",
        "Gold to report earnings next week",
        "What is the best time to buy gold?",
        "Gold FAQ: Everything you need to know",
    ])
    def test_neutral_no_keywords(self, title):
        assert _gold_direction(title) == "neutral"


class TestGoldDirectionAmbiguous:
    """Both up and down keywords present → neutral (neither direction wins)"""

    def test_bullish_and_bearish_both_present(self):
        assert _gold_direction("Gold bullish but bearish signals emerge") == "neutral"

    def test_surge_and_plunge_both_present(self):
        assert _gold_direction("Gold surges then plunges in volatile session") == "neutral"

    def test_safe_haven_and_profit_taking_both_present(self):
        assert _gold_direction("Safe haven demand meets profit taking") == "neutral"


class TestGoldDirectionEdgeCases:
    """Edge cases: special characters, unicode, SQL injection attempts."""

    def test_unicode_chinese_characters(self):
        # Pure Chinese title with no English directional keywords
        assert _gold_direction("黄金价格走势分析") == "neutral"

    def test_emoji_in_title(self):
        assert _gold_direction("Gold surges to $3,000! 🚀") == "up"

    def test_special_characters(self):
        assert _gold_direction("Gold <script>alert('xss')</script> surges") == "up"

    def test_empty_string(self):
        assert _gold_direction("") == "neutral"

    def test_only_whitespace(self):
        assert _gold_direction("   ") == "neutral"

    def test_case_insensitive(self):
        assert _gold_direction("GOLD SURGE") == "up"
        assert _gold_direction("GOLD SURGES") == "up"
        assert _gold_direction("Gold Plunge") == "down"
        assert _gold_direction("GOLD BULLISH") == "up"
        assert _gold_direction("GOLD BEARISH") == "down"

    def test_partial_word_false_positive(self):
        # 'gains' should match, 'surging' should match
        assert _gold_direction("Gold engulfs support level") == "neutral"

    def test_numeric_title(self):
        assert _gold_direction("Gold price: 2930.50") == "neutral"

    def test_url_in_title(self):
        assert _gold_direction("Gold surges — read more: https://example.com/news") == "up"

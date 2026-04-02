"""Tests for _time_ago_minutes() in data/sources/international.py"""
import pytest
from backend.data.sources.international import _time_ago_minutes


class TestTimeAgoMinutes:
    """Valid inputs: minutes, hours, days."""

    def test_minutes_cn(self):
        assert _time_ago_minutes("5分钟前") == 5

    def test_minutes_en(self):
        assert _time_ago_minutes("3 min ago") == 3

    def test_minutes_en_spelled_out(self):
        assert _time_ago_minutes("10 minutes ago") == 10

    def test_minutes_single_digit(self):
        assert _time_ago_minutes("1分钟前") == 1

    def test_minutes_large_value(self):
        assert _time_ago_minutes("59分钟前") == 59

    def test_hours_cn(self):
        assert _time_ago_minutes("3小时前") == 180

    def test_hours_en(self):
        assert _time_ago_minutes("2 hours ago") == 120

    def test_hours_en_singular(self):
        assert _time_ago_minutes("1 hour ago") == 60

    def test_hours_large_value(self):
        assert _time_ago_minutes("24小时前") == 1440

    def test_days_cn(self):
        assert _time_ago_minutes("2天前") == 2880

    def test_days_cn_alt_char(self):
        assert _time_ago_minutes("3日前") == 4320

    def test_days_en(self):
        assert _time_ago_minutes("5 days ago") == 7200

    def test_days_en_singular(self):
        assert _time_ago_minutes("1 day ago") == 1440


class TestTimeAgoEdgeCases:
    """Boundary values and unusual inputs."""

    def test_zero_minutes(self):
        assert _time_ago_minutes("0分钟前") == 0

    def test_zero_hours(self):
        assert _time_ago_minutes("0小时前") == 0

    def test_zero_days(self):
        assert _time_ago_minutes("0天前") == 0

    def test_whitespace_before_number(self):
        # Leading/trailing whitespace is stripped at entry, so parse succeeds
        assert _time_ago_minutes(" 5分钟前") == 5
        assert _time_ago_minutes("5分钟前  ") == 5
        assert _time_ago_minutes("  3小时前  ") == 180

    def test_no_space_between_number_and_unit(self):
        assert _time_ago_minutes("5分钟前") == 5  # no space, matches (space is optional)

    def test_large_whitespace(self):
        assert _time_ago_minutes("5    分钟前") == 5

    def test_case_insensitive(self):
        assert _time_ago_minutes("5 MINUTES AGO") == 5
        assert _time_ago_minutes("3 HOURS AGO") == 180
        assert _time_ago_minutes("2 DAYS AGO") == 2880

    def test_cn_char_case_insensitive(self):
        assert _time_ago_minutes("3小时前") == 180  # Chinese not case-sensitive but should still match

    def test_leading_zeros(self):
        assert _time_ago_minutes("007分钟前") == 7


class TestTimeAgoUnknown:
    """Unknown or unparseable formats fall back to 999999 (sorts last)."""

    def test_empty_string(self):
        assert _time_ago_minutes("") == 999999

    def test_whitespace_only(self):
        assert _time_ago_minutes("   ") == 999999

    def test_unknown_unit(self):
        assert _time_ago_minutes("5秒前") == 999999  # seconds not supported

    def test_unknown_unit_en(self):
        assert _time_ago_minutes("3 weeks ago") == 999999  # weeks not supported

    def test_no_unit(self):
        assert _time_ago_minutes("5") == 999999

    def test_no_number(self):
        assert _time_ago_minutes("minutes ago") == 999999

    def test_random_text(self):
        assert _time_ago_minutes("just now") == 999999
        assert _time_ago_minutes("yesterday") == 999999
        assert _time_ago_minutes("earlier today") == 999999

    def test_malformed_number(self):
        assert _time_ago_minutes("abc分钟前") == 999999

    def test_decimal_number(self):
        # Regex \d+ only matches integers
        assert _time_ago_minutes("2.5小时前") == 999999

    def test_future_time(self):
        # "分钟后" contains "分钟" → regex matches 5 minutes → returns 5
        # The implementation does not distinguish past vs future
        assert _time_ago_minutes("5分钟后") == 5

    def test_just_number_no_unit(self):
        assert _time_ago_minutes("123") == 999999


class TestTimeAgoSortability:
    """Values should be monotonic for sorting (smaller = newer)."""

    def test_minute_less_than_hour(self):
        assert _time_ago_minutes("5分钟前") < _time_ago_minutes("1小时前")

    def test_hour_less_than_day(self):
        assert _time_ago_minutes("2小时前") < _time_ago_minutes("1天前")

    def test_day_less_than_unknown(self):
        assert _time_ago_minutes("1天前") < _time_ago_minutes("unknown format")

    def test_59_minutes_equals_59(self):
        assert _time_ago_minutes("59分钟前") == 59

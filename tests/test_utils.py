import pytest
from datetime import date
from core.utils import (
    days_word,
    gift_year,
    next_birthday,
    normalize_date_or_none,
    normalize_username_or_none,
)


class TestNormalizeDateOrNone:
    def test_valid_date(self):
        assert normalize_date_or_none("21.03") == "21.03"

    def test_single_digit_day_and_month(self):
        assert normalize_date_or_none("1.3") == "01.03"

    def test_leading_spaces(self):
        assert normalize_date_or_none("  5.09  ") == "05.09"

    def test_29_feb_treated_as_valid(self):
        assert normalize_date_or_none("29.02") == "29.02"

    def test_invalid_format_returns_none(self):
        assert normalize_date_or_none("21-03") is None

    def test_non_string_returns_none(self):
        assert normalize_date_or_none(None) is None  # type: ignore
        assert normalize_date_or_none(2103) is None  # type: ignore

    def test_empty_string_returns_none(self):
        assert normalize_date_or_none("") is None

    def test_text_returns_none(self):
        assert normalize_date_or_none("birthday") is None

    def test_invalid_month_returns_none(self):
        assert normalize_date_or_none("01.13") is None
        assert normalize_date_or_none("01.00") is None

    def test_invalid_day_returns_none(self):
        assert normalize_date_or_none("30.02") is None
        assert normalize_date_or_none("31.04") is None
        assert normalize_date_or_none("00.05") is None


class TestNormalizeUsernameOrNone:
    def test_valid_username(self):
        assert normalize_username_or_none("Alice123") == "alice123"

    def test_with_at_prefix(self):
        assert normalize_username_or_none("@alice123") == "alice123"

    def test_lowercased(self):
        assert normalize_username_or_none("JOHN_DOE") == "john_doe"

    def test_too_short_returns_none(self):
        assert normalize_username_or_none("ab") is None
        assert normalize_username_or_none("abcd") is None

    def test_min_length_5_is_valid(self):
        assert normalize_username_or_none("abcde") == "abcde"

    def test_too_long_returns_none(self):
        assert normalize_username_or_none("a" * 33) is None

    def test_max_length_32_is_valid(self):
        assert normalize_username_or_none("a" * 32) == "a" * 32

    def test_invalid_chars_returns_none(self):
        assert normalize_username_or_none("alice.doe") is None
        assert normalize_username_or_none("alice-doe") is None
        assert normalize_username_or_none("alice doe") is None

    def test_none_input_returns_none(self):
        assert normalize_username_or_none(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_username_or_none("") is None

    def test_only_at_returns_none(self):
        assert normalize_username_or_none("@") is None


class TestNextBirthday:
    def test_later_this_year(self):
        assert next_birthday("15.10", date(2026, 10, 14)) == date(2026, 10, 15)

    def test_today(self):
        assert next_birthday("14.10", date(2026, 10, 14)) == date(2026, 10, 14)

    def test_already_passed_goes_to_next_year(self):
        assert next_birthday("13.10", date(2026, 10, 14)) == date(2027, 10, 13)

    def test_29_feb_in_non_leap_year(self):
        assert next_birthday("29.02", date(2026, 1, 1)) == date(2026, 2, 28)

    def test_29_feb_in_leap_year(self):
        assert next_birthday("29.02", date(2028, 1, 1)) == date(2028, 2, 29)

    def test_invalid_returns_none(self):
        assert next_birthday("not-a-date", date(2026, 1, 1)) is None
        assert next_birthday(None, date(2026, 1, 1)) is None  # type: ignore


class TestGiftYear:
    def test_birthday_within_week(self):
        assert gift_year("20.10", date(2026, 10, 14)) == 2026

    def test_birthday_already_passed_this_year(self):
        assert gift_year("01.10", date(2026, 10, 14)) == 2026

    def test_birthday_far_ahead_belongs_to_last_year(self):
        assert gift_year("01.12", date(2026, 10, 14)) == 2025

    def test_new_year_wrap(self):
        assert gift_year("02.01", date(2026, 12, 28)) == 2027

    def test_invalid_date_falls_back_to_current_year(self):
        assert gift_year(None, date(2026, 10, 14)) == 2026  # type: ignore


class TestDaysWord:
    @pytest.mark.parametrize("n,word", [
        (1, "день"), (2, "дня"), (4, "дня"), (5, "дней"), (11, "дней"),
        (12, "дней"), (21, "день"), (22, "дня"), (25, "дней"),
    ])
    def test_forms(self, n, word):
        assert days_word(n) == word

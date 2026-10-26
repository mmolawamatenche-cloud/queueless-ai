"""Privacy-focused tests for Home Affairs demo identity validation.

These use synthetic numbers only and do not test identity with Home Affairs.
"""
from backend.main import _is_valid_sa_id, _masked_id


def _synthetic_id_with_check_digit(prefix: str) -> str:
    assert len(prefix) == 12 and prefix.isdigit()
    digits = [int(ch) for ch in prefix]
    odd_sum = sum(digits[0:12:2])
    even_joined = "".join(str(digit) for digit in digits[1:12:2])
    doubled_sum = sum(int(ch) for ch in str(int(even_joined) * 2))
    check_digit = (10 - ((odd_sum + doubled_sum) % 10)) % 10
    return prefix + str(check_digit)


def test_synthetic_valid_format_and_check_digit():
    sample = _synthetic_id_with_check_digit("000101500908")
    assert _is_valid_sa_id(sample)
    assert _masked_id(sample) == "•••••••••" + sample[-4:]


def test_rejects_wrong_length():
    assert not _is_valid_sa_id("123456789012")


def test_rejects_non_digits():
    assert not _is_valid_sa_id("12345678901a3")


def test_rejects_bad_check_digit():
    sample = _synthetic_id_with_check_digit("000101500908")
    wrong = sample[:-1] + str((int(sample[-1]) + 1) % 10)
    assert not _is_valid_sa_id(wrong)


def test_rejects_invalid_date_and_citizenship_digit():
    valid_prefix = "000101500908"
    invalid_day = "0002305009080"
    invalid_citizenship_digit = valid_prefix[:10] + "2" + valid_prefix[11:] + "0"
    assert not _is_valid_sa_id(invalid_day)
    assert not _is_valid_sa_id(invalid_citizenship_digit)

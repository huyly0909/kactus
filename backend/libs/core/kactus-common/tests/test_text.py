"""Tests for the shared search-normalisation helper."""

from kactus_common.text import normalize_search


def test_strips_vietnamese_tone_marks():
    assert normalize_search("Thành Đức") == "thanh duc"
    assert normalize_search("Hồng Cúc") == "hong cuc"
    assert normalize_search("Tiến Sơn") == "tien son"


def test_folds_d_with_stroke():
    # đ/Đ is its own letter, so NFD alone leaves it — the explicit fold matters.
    assert normalize_search("Đường") == "duong"
    assert normalize_search("đỗ") == "do"


def test_is_case_insensitive_and_trimmed():
    assert normalize_search("  ALICE  ") == "alice"


def test_unaccented_query_matches_accented_name():
    assert normalize_search("duc") in normalize_search("Thành Đức")
    assert normalize_search("SON") in normalize_search("Tiến Sơn")


def test_handles_empty_and_none():
    assert normalize_search("") == ""
    assert normalize_search(None) == ""


def test_is_idempotent():
    once = normalize_search("Nguyễn Đình Chiểu")
    assert normalize_search(once) == once

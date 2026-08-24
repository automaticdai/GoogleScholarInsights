"""Tests for venue ranking utilities."""
from scripts.ranking_utils import (
    get_venue_metrics,
    get_venue_rank,
    load_rankings,
    normalize_venue_name,
)


def test_load_rankings_is_non_empty_dict():
    ranks = load_rankings()
    assert isinstance(ranks, dict)
    assert len(ranks) > 0


def test_normalize_lowercases_and_strips():
    assert normalize_venue_name('  IEEE Transactions  ') == 'ieee transactions'


def test_normalize_ampersand_to_and():
    assert normalize_venue_name('IEEE & ACM') == 'ieee and acm'


def test_normalize_removes_parentheses_and_commas():
    assert normalize_venue_name('(RTSS), 2020') == 'rtss 2020'


def test_get_venue_rank_nonexistent_is_unranked():
    assert get_venue_rank('ZZZ totally nonexistent venue 12345') == 'Unranked'


def test_get_venue_metrics_returns_tuple_with_rank():
    assert get_venue_metrics('ZZZ totally nonexistent venue') == ('Unranked', None, None)

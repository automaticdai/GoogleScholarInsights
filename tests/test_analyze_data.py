"""Tests for the ScholarAnalyzer class."""
from scripts.analyze_data import ScholarAnalyzer


def make_author(pubs=None, **overrides):
    data = {
        "name": "Xiaotian Dai",
        "citedby": 100,
        "cites_per_year": {"2020": 10, "2021": 20},
        "publications": pubs or [],
    }
    data.update(overrides)
    return data


def test_citation_metrics():
    analyzer = ScholarAnalyzer(make_author())
    metrics = analyzer.get_citation_metrics()
    assert metrics["total_citations"] == 100
    assert metrics["trends"] == [("2020", 10), ("2021", 20)]


def test_empty_publications_return_zero_stats():
    analyzer = ScholarAnalyzer(make_author())
    assert analyzer.get_authorship_stats() == {
        "First": 0,
        "Last": 0,
        "Middle": 0,
        "Single": 0,
    }
    assert analyzer.get_publication_ranks()["A*"] == 0
    assert analyzer.get_research_areas() == []

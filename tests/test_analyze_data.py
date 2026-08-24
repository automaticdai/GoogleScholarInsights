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


def test_research_areas_capture_acronyms_and_domain_terms():
    pubs = [
        {"bib": {"title": "Real-Time Scheduling for AI Systems"}},
        {"bib": {"title": "Deep Learning in Networks"}},
    ]
    analyzer = ScholarAnalyzer(make_author(pubs=pubs))
    areas = dict(analyzer.get_research_areas(20))
    assert "ai" in areas
    assert "real-time" in areas
    assert "system" in areas  # "systems" normalizes to "system"
    assert "learning" in areas
    assert "network" in areas


def test_authorship_positions():
    pubs = [
        {"bib": {"author": "Xiaotian Dai"}},
        {"bib": {"author": "Xiaotian Dai and Alan Burns"}},
        {"bib": {"author": "Alan Burns and Xiaotian Dai"}},
        {"bib": {"author": "Alan Burns and Xiaotian Dai and Iain Bate"}},
    ]
    analyzer = ScholarAnalyzer(make_author(pubs=pubs))
    assert analyzer.get_authorship_stats() == {
        "First": 1,
        "Last": 1,
        "Middle": 1,
        "Single": 1,
    }


def test_authorship_word_boundary_prevents_substring_match():
    # surname "Li" must not match "Alice"
    pubs = [{"bib": {"author": "Alice Smith and Wei Li"}}]
    analyzer = ScholarAnalyzer(make_author(name="Wei Li", pubs=pubs))
    assert analyzer.get_authorship_stats()["Last"] == 1


def test_authorship_disambiguates_shared_surname_by_initial():
    pubs = [{"bib": {"author": "Alice Li and Wei Li"}}]
    analyzer = ScholarAnalyzer(make_author(name="Wei Li", pubs=pubs))
    assert analyzer.get_authorship_stats()["Last"] == 1

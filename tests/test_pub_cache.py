"""Tests for the per-author publication cache."""
import json
import os

from scripts.pub_cache import (
    cache_path_for,
    load_cache,
    merge,
    needs_fetch,
    save_cache,
)


def make_stub(pub_id="AAA:1", citations=10, **overrides):
    """A publication as it arrives in the author-level listing (unfilled)."""
    stub = {
        "author_pub_id": pub_id,
        "filled": False,
        "num_citations": citations,
        "bib": {"title": "Scheduling analysis", "pub_year": "2021"},
    }
    stub.update(overrides)
    return stub


def make_filled(pub_id="AAA:1", citations=10, **overrides):
    """A publication after scholarly.fill() — carries the static fields."""
    pub = {
        "author_pub_id": pub_id,
        "filled": True,
        "num_citations": citations,
        "pub_url": "https://example.org/paper",
        "cites_per_year": {"2021": 4, "2022": 6},
        "bib": {
            "title": "Scheduling analysis",
            "pub_year": "2021",
            "abstract": "A long abstract that costs a request to obtain.",
            "author": "X Dai and A Burns",
            "journal": "Real-Time Systems",
        },
    }
    pub.update(overrides)
    return pub


# --- cache location -------------------------------------------------------


def test_each_author_gets_its_own_cache_file(tmp_path):
    a = cache_path_for("AAAAAAAAAAAA", str(tmp_path))
    b = cache_path_for("BBBBBBBBBBBB", str(tmp_path))
    assert a != b
    assert os.path.dirname(a) == os.path.dirname(b) == str(tmp_path)


def test_cache_path_ignores_directory_traversal_in_scholar_id(tmp_path):
    path = cache_path_for("../../etc/passwd", str(tmp_path))
    assert os.path.dirname(os.path.abspath(path)) == str(tmp_path)


# --- persistence ----------------------------------------------------------


def test_missing_cache_file_loads_as_empty(tmp_path):
    assert load_cache(str(tmp_path / "nothing.json")) == {}


def test_corrupt_cache_file_loads_as_empty(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json at all")
    assert load_cache(str(path)) == {}


def test_save_then_load_round_trips_entries(tmp_path):
    path = cache_path_for("AAAAAAAAAAAA", str(tmp_path))
    entries = {"AAA:1": make_filled("AAA:1")}

    save_cache(path, entries, scholar_id="AAAAAAAAAAAA")

    assert load_cache(path) == entries


def test_save_creates_the_cache_directory(tmp_path):
    path = cache_path_for("AAAAAAAAAAAA", str(tmp_path / "nested" / "cache"))
    save_cache(path, {"AAA:1": make_filled()}, scholar_id="AAAAAAAAAAAA")
    assert os.path.exists(path)


def test_switching_authors_and_back_keeps_the_first_authors_cache(tmp_path):
    """Fetching a second author must not evict the first author's entries."""
    cache_dir = str(tmp_path)
    path_a = cache_path_for("AUTHORAAAAAA", cache_dir)
    path_b = cache_path_for("AUTHORBBBBBB", cache_dir)

    save_cache(path_a, {"AUTHORAAAAAA:1": make_filled("AUTHORAAAAAA:1")},
               scholar_id="AUTHORAAAAAA")
    save_cache(path_b, {"AUTHORBBBBBB:1": make_filled("AUTHORBBBBBB:1")},
               scholar_id="AUTHORBBBBBB")

    back_to_a = load_cache(cache_path_for("AUTHORAAAAAA", cache_dir))
    assert set(back_to_a) == {"AUTHORAAAAAA:1"}
    assert back_to_a["AUTHORAAAAAA:1"]["bib"]["abstract"]


def test_saved_file_records_the_scholar_id(tmp_path):
    path = cache_path_for("AAAAAAAAAAAA", str(tmp_path))
    save_cache(path, {"AAA:1": make_filled()}, scholar_id="AAAAAAAAAAAA")

    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    assert raw["scholar_id"] == "AAAAAAAAAAAA"


# --- fetch decisions ------------------------------------------------------


def test_uncached_publication_needs_a_fetch():
    assert needs_fetch(make_stub(), None) is True


def test_cached_publication_does_not_need_a_fetch():
    assert needs_fetch(make_stub(), make_filled()) is False


def test_stub_without_citation_count_needs_a_fetch():
    """The whole optimisation rests on the listing carrying num_citations.

    If it ever does not, fall back to fetching rather than serving a stale
    count from the cache.
    """
    stub = make_stub()
    del stub["num_citations"]
    assert needs_fetch(stub, make_filled()) is True


def test_unfilled_cache_entry_needs_a_fetch():
    assert needs_fetch(make_stub(), make_stub()) is True


# --- merging --------------------------------------------------------------


def test_merge_keeps_the_expensive_static_fields():
    merged = merge(make_stub(citations=99), make_filled(citations=10))
    assert merged["bib"]["abstract"] == "A long abstract that costs a request to obtain."
    assert merged["bib"]["author"] == "X Dai and A Burns"
    assert merged["pub_url"] == "https://example.org/paper"
    assert merged["filled"] is True


def test_merge_takes_the_fresh_citation_count():
    merged = merge(make_stub(citations=99), make_filled(citations=10))
    assert merged["num_citations"] == 99


def test_merge_takes_the_fresh_cites_per_year():
    stub = make_stub(citations=99, cites_per_year={"2021": 4, "2022": 6, "2023": 89})
    merged = merge(stub, make_filled(citations=10))
    assert merged["cites_per_year"] == {"2021": 4, "2022": 6, "2023": 89}


def test_merge_keeps_cached_cites_per_year_when_the_stub_has_none():
    merged = merge(make_stub(citations=99), make_filled(citations=10))
    assert merged["cites_per_year"] == {"2021": 4, "2022": 6}


def test_merge_does_not_mutate_the_cached_entry():
    cached = make_filled(citations=10)
    merge(make_stub(citations=99), cached)
    assert cached["num_citations"] == 10


# --- resolving a listing against the cache --------------------------------


class RecordingFetcher:
    """Stands in for scholarly.fill, counting the requests it would make."""

    def __init__(self, failures=()):
        self.calls = []
        self.failures = set(failures)

    def __call__(self, stub):
        pub_id = stub.get("author_pub_id")
        self.calls.append(pub_id)
        if pub_id in self.failures:
            return None
        return make_filled(pub_id, citations=stub.get("num_citations", 0))


class RecordingWaiter:
    def __init__(self):
        self.waits = 0

    def __call__(self):
        self.waits += 1


def test_cache_hit_makes_no_request_and_no_wait():
    from scripts.pub_cache import resolve_publications

    fetcher = RecordingFetcher()
    waiter = RecordingWaiter()
    cached = {"AAA:1": make_filled("AAA:1", citations=10)}

    pubs, entries = resolve_publications(
        [make_stub("AAA:1", citations=99)], cached, fetcher, waiter)

    assert fetcher.calls == []
    assert waiter.waits == 0
    assert pubs[0]["num_citations"] == 99
    assert pubs[0]["bib"]["abstract"]
    assert entries["AAA:1"]["bib"]["abstract"]


def test_cache_miss_fetches_and_records_the_entry():
    from scripts.pub_cache import resolve_publications

    fetcher = RecordingFetcher()
    pubs, entries = resolve_publications(
        [make_stub("AAA:2", citations=5)], {}, fetcher, RecordingWaiter())

    assert fetcher.calls == ["AAA:2"]
    assert pubs[0]["filled"] is True
    assert entries["AAA:2"]["author_pub_id"] == "AAA:2"


def test_only_new_publications_are_fetched():
    from scripts.pub_cache import resolve_publications

    fetcher = RecordingFetcher()
    cached = {"AAA:1": make_filled("AAA:1")}
    stubs = [make_stub("AAA:1"), make_stub("AAA:2"), make_stub("AAA:3")]

    pubs, entries = resolve_publications(stubs, cached, fetcher, RecordingWaiter())

    assert fetcher.calls == ["AAA:2", "AAA:3"]
    assert len(pubs) == 3
    assert set(entries) == {"AAA:1", "AAA:2", "AAA:3"}


def test_waits_between_fetches_but_not_after_the_last_one():
    from scripts.pub_cache import resolve_publications

    waiter = RecordingWaiter()
    stubs = [make_stub("AAA:1"), make_stub("AAA:2"), make_stub("AAA:3")]

    resolve_publications(stubs, {}, RecordingFetcher(), waiter)

    assert waiter.waits == 2


def test_a_failed_fetch_keeps_the_stub_and_is_not_cached():
    from scripts.pub_cache import resolve_publications

    fetcher = RecordingFetcher(failures=["AAA:2"])
    pubs, entries = resolve_publications(
        [make_stub("AAA:2", citations=7)], {}, fetcher, RecordingWaiter())

    assert pubs[0]["num_citations"] == 7
    assert pubs[0].get("filled") is False
    assert entries == {}


def test_refresh_refetches_everything_despite_a_full_cache():
    from scripts.pub_cache import resolve_publications

    fetcher = RecordingFetcher()
    cached = {"AAA:1": make_filled("AAA:1")}

    resolve_publications([make_stub("AAA:1")], cached, fetcher,
                         RecordingWaiter(), refresh=True)

    assert fetcher.calls == ["AAA:1"]


def test_publications_without_an_id_are_always_fetched():
    from scripts.pub_cache import resolve_publications

    fetcher = RecordingFetcher()
    stub = make_stub("AAA:4")
    del stub["author_pub_id"]

    pubs, entries = resolve_publications([stub], {}, fetcher, RecordingWaiter())

    assert len(pubs) == 1
    assert entries == {}


def test_entries_for_authors_no_longer_listed_are_kept():
    """A --limit run must not drop the rest of the author's cached work."""
    from scripts.pub_cache import resolve_publications

    cached = {"AAA:1": make_filled("AAA:1"), "AAA:9": make_filled("AAA:9")}

    pubs, entries = resolve_publications(
        [make_stub("AAA:1")], cached, RecordingFetcher(), RecordingWaiter())

    assert len(pubs) == 1
    assert set(entries) == {"AAA:1", "AAA:9"}


def test_entries_are_recorded_as_each_fetch_completes():
    """An interrupted long run must still be able to save what it got."""
    from scripts.pub_cache import resolve_publications

    def fetch_then_interrupt(stub):
        if stub["author_pub_id"] == "AAA:2":
            raise KeyboardInterrupt
        return make_filled(stub["author_pub_id"])

    entries = {}
    stubs = [make_stub("AAA:1"), make_stub("AAA:2")]

    try:
        resolve_publications(stubs, entries, fetch_then_interrupt, RecordingWaiter())
    except KeyboardInterrupt:
        pass

    assert set(entries) == {"AAA:1"}

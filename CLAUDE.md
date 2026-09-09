# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ScholarInsights is a Python toolkit for fetching, analyzing, and visualizing Google Scholar author profiles. It produces an interactive web dashboard with citation trends, venue rankings, authorship positions, and keyword analysis.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Fetch author data by Scholar ID (outputs author_data.json)
python3 scripts/fetch_data.py --id "SCHOLAR_ID" --limit 100

# Fetch with custom rate limiting
python3 scripts/fetch_data.py --id "SCHOLAR_ID" --limit 50 --min-delay 5.0 --max-delay 10.0

# Refetch every publication, ignoring the cache
python3 scripts/fetch_data.py --id "SCHOLAR_ID" --refresh

# Search by author name (lists matching candidates)
python3 scripts/fetch_data.py --author "Author Name"

# Run analysis on fetched data
python3 scripts/analyze_data.py --file author_data.json
python3 scripts/analyze_data.py --file author_data.json --verbose-ranking

# Start Flask dashboard (http://localhost:5000)
python3 app.py

# Run manual test
python3 scripts/test_fetch.py

# Run test suite
python3 -m pytest
```

A pytest suite lives in `tests/` (run with `python3 -m pytest`). No linter or build system is configured.

## Architecture

**Data pipeline:** `fetch_data.py` → `author_data.json` → `analyze_data.py` / `app.py` → dashboard

- **`scripts/fetch_data.py`** — Fetches author profiles from Google Scholar via the `scholarly` library. Includes rate limiting (randomized delays), exponential backoff retries, rotating user-agents, and optional proxy support to avoid IP bans. Per-publication requests go through `pub_cache.resolve_publications`, so only uncached papers cost a request.
- **`scripts/analyze_data.py`** — `ScholarAnalyzer` class processes `author_data.json` to compute citation metrics, publication trends, keyword extraction (with normalization for plurals, compounds, hyphens), and authorship position analysis (first/middle/last/single).
- **`scripts/pub_cache.py`** — Per-author publication cache keyed by Scholar's `author_pub_id`, stored in `.scholar_cache/<scholar_id>.json`. Publication details are static, so only new papers cost a request; citation counts are refreshed from the author listing on every run. Imports nothing from `scholarly`, which is what makes it unit-testable — `fetch_data.py` itself is not.
- **`scripts/ranking_utils.py`** — Maps publication venues to CORE rankings (A\*, A, B, C) using fuzzy matching against `scripts/venue_ranks.json`. Handles acronyms, punctuation variations, and "&" vs "and" normalization. Extended entries include Impact Factor and SJR.
- **`app.py`** — Flask server with three routes: `GET /` (dashboard HTML), `GET /api/data` (raw JSON), `GET /api/analysis` (processed analysis via `ScholarAnalyzer`).
- **`templates/index.html`** — Single-page dashboard using Chart.js (via CDN) and vanilla JS. Fetches from `/api/analysis` to render a masthead, a 4-metric band, 5 charts, and a numbered top-20 bibliography. Colours are CSS custom properties read once into a JS palette object, so retheming happens in the `:root` block alone. The venue ramp is an ordinal single-hue scale — replacing it with unordered hues would break rank legibility.

## Key Data Files

- **`author_data.json`** — Generated output from fetch_data.py; consumed by analysis and the dashboard. Not a static fixture.
- **`.scholar_cache/<scholar_id>.json`** — Generated per-author publication cache (gitignored). Safe to delete; the next fetch rebuilds it.
- **`scripts/venue_ranks.json`** — Editable venue ranking database (~150+ venues). Supports both simple format (`"venue": "A*"`) and extended format (`"venue": {"rank": "A*", "impact_factor": 2.5, "sjr": 1.1}`).

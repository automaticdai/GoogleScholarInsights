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

# Search by author name (lists matching candidates)
python3 scripts/fetch_data.py --author "Author Name"

# Run analysis on fetched data
python3 scripts/analyze_data.py --file author_data.json
python3 scripts/analyze_data.py --file author_data.json --verbose-ranking

# Start Flask dashboard (http://localhost:5000)
python3 app.py

# Run manual test
python3 scripts/test_fetch.py
```

No formal test framework, linter, or build system is configured.

## Architecture

**Data pipeline:** `fetch_data.py` → `author_data.json` → `analyze_data.py` / `app.py` → dashboard

- **`scripts/fetch_data.py`** — Fetches author profiles from Google Scholar via the `scholarly` library. Includes rate limiting (randomized delays), exponential backoff retries, rotating user-agents, and optional proxy support to avoid IP bans.
- **`scripts/analyze_data.py`** — `ScholarAnalyzer` class processes `author_data.json` to compute citation metrics, publication trends, keyword extraction (with normalization for plurals, compounds, hyphens), and authorship position analysis (first/middle/last/single).
- **`scripts/ranking_utils.py`** — Maps publication venues to CORE rankings (A\*, A, B, C) using fuzzy matching against `scripts/venue_ranks.json`. Handles acronyms, punctuation variations, and "&" vs "and" normalization. Extended entries include Impact Factor and SJR.
- **`app.py`** — Flask server with three routes: `GET /` (dashboard HTML), `GET /api/data` (raw JSON), `GET /api/analysis` (processed analysis via `ScholarAnalyzer`).
- **`templates/index.html`** — Single-page dashboard using Chart.js (via CDN) and vanilla JS. Fetches from `/api/analysis` to render 4 stat cards, 4 charts, and a top-20 publications list.

## Key Data Files

- **`author_data.json`** — Generated output from fetch_data.py; consumed by analysis and the dashboard. Not a static fixture.
- **`scripts/venue_ranks.json`** — Editable venue ranking database (~150+ venues). Supports both simple format (`"venue": "A*"`) and extended format (`"venue": {"rank": "A*", "impact_factor": 2.5, "sjr": 1.1}`).

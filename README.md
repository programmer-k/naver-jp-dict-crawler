# naver-jp-dict-crawler

This repository contains a Playwright-based scraper for extracting JLPT N1~N5 word lists from Naver Japanese Dictionary (ja.dict.naver.com).

Scraper files are at repository root:

- `scraper.py` — main scraper CLI
- `playwright_helpers.py` — Playwright browser helpers
- `output_utils.py` — CSV writing utilities
- `validate.py` — simple CSV validation tool

Quick start

1. Create and activate a virtual environment (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies and Playwright browsers:

```bash
python -m pip install -r requirements.txt
python -m playwright install
```

3. Run scraper (example):

```bash
python scraper.py --levels 1,2,3,4,5 --pos all --out-dir outputs
```

4. Validate outputs:

```bash
python validate.py outputs
```

Notes
- `--pos all` discovers POS buttons on the site and creates one CSV per POS per level.
- Filenames: `N{level}_{pos}.csv` containing columns `level,pos,japanese,reading,korean,source_url`.
- Respect site load: avoid high concurrency and add delays if needed.

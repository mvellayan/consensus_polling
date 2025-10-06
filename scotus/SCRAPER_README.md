# Supreme Court Case Scraper

This script scrapes Supreme Court case information from Justia.com using Playwright.

## Installation

1. Install Python dependencies:
```bash
pip install playwright
```

2. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

Run the scraper with a Justia Supreme Court case URL:

```bash
python supreme_court_scraper.py "https://supreme.justia.com/cases/federal/us/604/22-7466/"
```

## Output

The scraper will create the following JSON files:

1. **{case_number}_syllabus.json** - Contains the case syllabus
2. **{case_number}_{judge}_{opinion_type}.json** - One file for each opinion (e.g., `22-7466_sotomayor_opinion.json`)

## Example

```bash
python supreme_court_scraper.py "https://supreme.justia.com/cases/federal/us/604/22-7466/"
```

This will create:
- `22-7466_syllabus.json`
- `22-7466_sotomayor_opinion.json`
- `22-7466_barrett_opinion.json`
- `22-7466_thomas_dissent.json`

## Features

- Extracts syllabus text automatically
- Clicks each opinion button and extracts the full opinion text
- Saves each opinion separately with judge name and opinion type
- Handles multiple opinion types (Opinion, Dissent, Concurrence)

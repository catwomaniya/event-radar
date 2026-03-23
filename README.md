# Event Radar

Scrape Luma event guest lists and pulls X bios for each attendee. Prints results to terminal or export results to Google Sheets (detailed process on how to set this up is below)

## Requirements

- Python 3.10+
- A Luma account (you need to register and get access to the event + event should have guest list visible for the tool to read it)
- An X (Twitter) account (don't use your primary account for this, best option is to create a throwaway account cos it might get blocked for bot behavior, hasnt happened yet but better to be safe)

## Setup

```bash
cd scrape-luma
uv sync
uv run playwright install chromium
```

## Login Sessions

Both Luma and X require browser login sessions saved locally. These are one-time steps (re-run if sessions expire).

### 1. Luma Login (required for private guest lists)

```bash
uv run scrape-luma luma-login
```

A browser window opens to `lu.ma/signin`. Log in with your account. The session is saved to `auth/luma_browser_state.json` automatically once login completes.

### 2. X/Twitter Login (required for bio scraping)

```bash
uv run scrape-luma x-login
```

Same flow — browser opens to `x.com/login`, you log in manually, session is saved to `auth/x_browser_state.json`.

## Usage

### Scrape event + X bios (full pipeline)

```bash
uv run scrape-luma scrape "https://lu.ma/your-event-slug"
```

This will:
1. Open the Luma event page (using your saved Luma session)
2. Extract the guest list (names, X handles)
3. Visit each guest's X profile (using your saved X session)
4. Print a table with Name, X Handle, Bio, Location, Followers

### Scrape guest list only (skip X)

```bash
uv run scrape-luma scrape "https://lu.ma/your-event-slug" --skip-x
```

### Multiple events

```bash
uv run scrape-luma scrape "https://lu.ma/event-1" "https://lu.ma/event-2"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--no-headless` | headless | Show the browser window (useful for debugging) |
| `--skip-x` | off | Skip X/Twitter bio scraping |
| `--max-guests N` | 0 (all) | Limit number of guests scraped |
| `--delay-min` | 3.0 | Min seconds between X profile visits |
| `--delay-max` | 7.0 | Max seconds between X profile visits |

## How It Works

- **Luma scraping**: Playwright opens the event page with your logged-in session. It intercepts the API responses that Luma's frontend fetches (Next.js app), extracting guest data from JSON. Falls back to DOM scraping if API interception yields nothing.
- **X scraping**: For each guest with an X handle, visits `x.com/{handle}` using `data-testid` selectors to extract bio, location, website, and follower count. Random delays between visits to avoid rate limiting.
- **Session storage**: Browser state (cookies, localStorage) is saved as JSON files in `auth/`. These are gitignored.

## Setting up Google Sheets (to get exported data directly)
1. Create service account
- Go to https://console.cloud.google.com/
- Create a project → open Service Accounts
- Click Create Service Account

2. Download credentials
- Open your service account
- Go to Keys → Add Key → JSON
- Download the file
- Move it to:
creds/service_account.json

3. Enable APIs
Enable these in Google Cloud:
- Google Sheets API
- Google Drive API

4. Share your sheet
- Create a Google Sheet
- Click Share
- Add the service account email (from JSON file)
- Give Editor access to that email

## File Structure

```
scrape-luma/
├── pyproject.toml
├── auth/                        # gitignored - saved browser sessions
│   ├── luma_browser_state.json
│   └── x_browser_state.json
├── creds/                       # gitignored - Google service account
└── src/scrape_luma/
    ├── cli.py                   # Typer CLI commands
    ├── config.py                # Paths, timing constants
    ├── models.py                # Pydantic data models
    ├── luma_scraper.py          # Luma guest list scraping + login
    ├── x_scraper.py             # X/Twitter profile scraping + login
    └── sheets.py                # Google Sheets writer (not wired up yet)
```

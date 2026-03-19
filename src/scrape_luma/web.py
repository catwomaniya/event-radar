from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from scrape_luma.config import X_BROWSER_STATE_PATH
from scrape_luma.models import GuestRow

web_app = FastAPI(title="Event Radar")


_BASE_CSS = """
  :root {
    --bg: #0b0f17;
    --panel: #0f172a;
    --panel2: #0b1222;
    --text: #e5e7eb;
    --muted: #9ca3af;
    --border: rgba(148, 163, 184, 0.18);
    --accent: #22c55e;
    --danger: #ef4444;
    --warn: #f59e0b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
    background: radial-gradient(1200px 600px at 20% 0%, rgba(34,197,94,.14), transparent 60%),
                radial-gradient(900px 500px at 90% 10%, rgba(59,130,246,.12), transparent 55%),
                var(--bg);
    color: var(--text);
  }
  .wrap { max-width: 980px; margin: 40px auto; padding: 0 18px; }
  .title { font-size: 28px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 8px; }
  .subtitle { margin: 0 0 22px; color: var(--muted); line-height: 1.4; }
  .card {
    background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 18px 40px rgba(0,0,0,.35);
  }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
  label { display: block; font-size: 13px; color: var(--muted); margin: 10px 0 6px; }
  input[type="text"], input[type="url"], input[type="number"] {
    width: 100%;
    background: rgba(15, 23, 42, .75);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--text);
    outline: none;
  }
  input[type="text"]:focus, input[type="url"]:focus, input[type="number"]:focus {
    border-color: rgba(34,197,94,.55);
    box-shadow: 0 0 0 4px rgba(34,197,94,.16);
  }
  .row { display: flex; gap: 10px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
  .check {
    display: flex; gap: 10px; align-items: center;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: rgba(15, 23, 42, .45);
  }
  .check span { color: var(--muted); font-size: 13px; }
  .btn {
    display: inline-flex; align-items: center; justify-content: center;
    padding: 10px 14px;
    background: linear-gradient(180deg, rgba(34,197,94,.95), rgba(34,197,94,.78));
    color: #07110b;
    font-weight: 800;
    border: 0;
    border-radius: 12px;
    cursor: pointer;
    box-shadow: 0 12px 26px rgba(34,197,94,.18);
  }
  .btn:active { transform: translateY(1px); }
  .note { margin-top: 14px; color: var(--muted); font-size: 13px; line-height: 1.5; }
  .alert {
    margin-top: 12px;
    padding: 10px 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: rgba(239, 68, 68, .10);
    color: #fecaca;
  }
  .warn {
    background: rgba(245, 158, 11, .10);
    color: #fde68a;
  }
  table { width: 100%; border-collapse: collapse; margin-top: 18px; overflow: hidden; border-radius: 12px; }
  th, td { border-bottom: 1px solid var(--border); padding: 10px 10px; vertical-align: top; }
  th { text-align: left; color: var(--muted); font-size: 12px; letter-spacing: .02em; }
  tr:hover td { background: rgba(255,255,255,.02); }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>{_BASE_CSS}</style>
  </head>
  <body>
    <div class="wrap">
      {body}
    </div>
  </body>
</html>"""


def _form(
    *,
    event_url: str = "",
    skip_x: bool = False,
    show_browser: bool = False,
    max_guests: int = 0,
    delay_min: float = 3.0,
    delay_max: float = 7.0,
    sheet_id: str = "",
    message_html: str = "",
) -> str:
    x_session_exists = X_BROWSER_STATE_PATH.exists()
    x_session_note = (
        "<div class='alert warn'>X session not found. Run <span class='mono'>scrape-luma x-login</span> before scraping bios, or check “Skip X bio scraping”.</div>"
        if not x_session_exists
        else ""
    )

    body = f"""
      <h1 class="title">Event Radar</h1>
      <p class="subtitle">Paste a Luma event URL, choose options, and run the scrape from your browser.</p>
      <div class="card">
        {message_html}
        {x_session_note}
        <form method="post" action="/scrape">
          <label for="event_url">Luma event URL</label>
          <input id="event_url" name="event_url" type="url" required placeholder="https://lu.ma/your-event-slug" value="{escape(event_url)}" />

          <div class="grid">
            <div>
              <label for="max_guests">Max guests (0 = all)</label>
              <input id="max_guests" name="max_guests" type="number" min="0" step="1" value="{max_guests}" />
            </div>
            <div>
              <label for="sheet_id">Optional Google Sheet ID</label>
              <input id="sheet_id" name="sheet_id" type="text" placeholder="1AbC... (share with service account first)" value="{escape(sheet_id)}" />
            </div>
          </div>

          <div class="grid">
            <div>
              <label for="delay_min">X delay min (sec)</label>
              <input id="delay_min" name="delay_min" type="number" min="0" step="0.1" value="{delay_min}" />
            </div>
            <div>
              <label for="delay_max">X delay max (sec)</label>
              <input id="delay_max" name="delay_max" type="number" min="0" step="0.1" value="{delay_max}" />
            </div>
          </div>

          <div class="row">
            <label class="check">
              <input type="checkbox" name="skip_x" value="1" {"checked" if skip_x else ""} />
              <span>Skip X bio scraping</span>
            </label>
            <label class="check">
              <input type="checkbox" name="show_browser" value="1" {"checked" if show_browser else ""} />
              <span>Show browser window (non-headless)</span>
            </label>
            <button class="btn" type="submit">Run scrape</button>
          </div>

          <div class="note">
            This uses your locally saved browser sessions in <span class="mono">auth/</span>.
            Check the README file here if you're stuck &lt;URL&gt;.
          </div>
        </form>
      </div>
    """
    return _page("Event Radar", body)


@web_app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(_form())


@web_app.post("/scrape", response_class=HTMLResponse)
def run_scrape(
    event_url: str = Form(...),
    skip_x: Optional[str] = Form(None),
    show_browser: Optional[str] = Form(None),
    max_guests: int = Form(0),
    delay_min: float = Form(3.0),
    delay_max: float = Form(7.0),
    sheet_id: str = Form(""),
) -> HTMLResponse:
    from scrape_luma import luma_scraper, sheets, x_scraper

    skip_x_bool = bool(skip_x)
    headless = not bool(show_browser)
    sheet_id = sheet_id.strip()

    # Validate X session exists if needed
    if not skip_x_bool and not X_BROWSER_STATE_PATH.exists():
        msg = "<div class='alert'>X session not found. Run <span class='mono'>scrape-luma x-login</span> first, or enable “Skip X bio scraping”.</div>"
        return HTMLResponse(
            _form(
                event_url=event_url,
                skip_x=skip_x_bool,
                show_browser=not headless,
                max_guests=max_guests,
                delay_min=delay_min,
                delay_max=delay_max,
                sheet_id=sheet_id,
                message_html=msg,
            )
        )

    guests, event_name = luma_scraper.scrape_event_guests(
        event_url=event_url,
        headless=headless,
        max_guests=max_guests,
    )

    if not guests:
        msg = "<div class='alert'>No guests found for that event URL.</div>"
        return HTMLResponse(
            _form(
                event_url=event_url,
                skip_x=skip_x_bool,
                show_browser=not headless,
                max_guests=max_guests,
                delay_min=delay_min,
                delay_max=delay_max,
                sheet_id=sheet_id,
                message_html=msg,
            )
        )

    x_profiles: dict = {}
    handles = [g.x_handle for g in guests if g.x_handle]
    if (not skip_x_bool) and handles:
        x_profiles = x_scraper.scrape_profiles(
            handles=handles,
            headless=headless,
            delay_min=delay_min,
            delay_max=delay_max,
            progress_callback=None,
        )

    rows = [GuestRow.from_guest_and_profile(g, x_profiles.get(g.x_handle) if g.x_handle else None) for g in guests]

    sheet_result_html = ""
    if sheet_id:
        try:
            spreadsheet = sheets.open_by_id(sheet_id)
            tab_name_base = (event_name or event_url.split("/")[-1].split("?")[0]).strip() or "Event"
            tab_name = tab_name_base[:80]
            worksheet = sheets.write_guests(spreadsheet, rows, tab_name=tab_name)
            tab_url = f"{spreadsheet.url}#gid={worksheet.id}"
            sheet_result_html = f"<div class='alert warn'>Wrote {len(rows)} rows to Google Sheets tab: <a href='{escape(tab_url)}' target='_blank' rel='noreferrer'>{escape(worksheet.title)}</a></div>"
        except FileNotFoundError:
            sheet_result_html = "<div class='alert'>Google Sheets credentials not found at <span class='mono'>creds/gspread_service_account.json</span>.</div>"
        except Exception as e:
            sheet_result_html = f"<div class='alert'>Sheets export failed: <span class='mono'>{escape(str(e))}</span></div>"

    title = escape(event_name or "Scrape results")

    def td(x: str) -> str:
        return escape(x or "")

    table_rows = []
    for i, r in enumerate(rows, 1):
        handle = f"@{r.x_handle}" if r.x_handle else ""
        table_rows.append(
            "<tr>"
            f"<td class='mono'>{i}</td>"
            f"<td>{td(r.name)}</td>"
            f"<td class='mono'>{td(handle)}</td>"
            f"<td>{td(r.x_bio or '')}</td>"
            f"<td>{td(r.x_location or '')}</td>"
            f"<td class='mono'>{td(r.x_followers or '')}</td>"
            f"<td class='mono'>{td(r.scrape_status)}</td>"
            "</tr>"
        )

    body = f"""
      <h1 class="title">{title}</h1>
      <p class="subtitle">Found <b>{len(rows)}</b> guests. <a href="/">Run another</a>.</p>
      {sheet_result_html}
      <div class="card">
        <div class="note"><span class="mono">{escape(event_url)}</span></div>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>X</th>
              <th>Bio</th>
              <th>Location</th>
              <th>Followers</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {''.join(table_rows)}
          </tbody>
        </table>
      </div>
    """

    return HTMLResponse(_page("Scrape results", body))


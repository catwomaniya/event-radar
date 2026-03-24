import json
import re

from playwright.sync_api import Page, sync_playwright
from rich.console import Console

from scrape_luma.config import AUTH_DIR, LUMA_BROWSER_STATE_PATH, PAGE_LOAD_TIMEOUT_MS
from scrape_luma.models import LumaGuest

console = Console()


def save_login_session() -> None:
    """Open a visible browser for the user to log into Luma. Save session state."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://lu.ma/signin", timeout=30_000)
        console.print("[bold]Log into Luma in the browser window.[/bold]")
        console.print("Waiting up to 5 minutes for login to complete...")

        try:
            page.wait_for_url(
                lambda url: "signin" not in url and "login" not in url,
                timeout=300_000,  # 5 minutes
            )
            page.wait_for_timeout(2000)
        except Exception:
            console.print("[red]Timeout waiting for login. Try again.[/red]")
            browser.close()
            return

        context.storage_state(path=str(LUMA_BROWSER_STATE_PATH))
        console.print(f"[green]Luma session saved to {LUMA_BROWSER_STATE_PATH}[/green]")
        browser.close()


def _parse_featured_guest(user: dict) -> LumaGuest:
    """Parse a guest from the featured_guests array in __NEXT_DATA__."""
    name = user.get("name", "")
    twitter_handle = user.get("twitter_handle")
    x_handle = twitter_handle.lstrip("@") if twitter_handle else None
    username = user.get("username")

    return LumaGuest(
        name=name,
        avatar_url=user.get("avatar_url"),
        x_handle=x_handle,
        x_profile_url=f"https://x.com/{x_handle}" if x_handle else None,
        luma_profile_url=f"https://lu.ma/user/{username}" if username else None,
    )


def _parse_api_guest_entry(entry: dict) -> LumaGuest | None:
    """Parse a guest from a Luma API response entry."""
    user_data = entry.get("user", {})
    guest_data = entry.get("guest", {})

    name = user_data.get("name") or guest_data.get("name") or ""
    if not name:
        return None

    x_handle = None
    twitter_handle = user_data.get("twitter_handle")
    if twitter_handle:
        x_handle = twitter_handle.lstrip("@")

    username = user_data.get("username")

    return LumaGuest(
        name=name,
        avatar_url=user_data.get("avatar_url"),
        x_handle=x_handle,
        x_profile_url=f"https://x.com/{x_handle}" if x_handle else None,
        luma_profile_url=f"https://lu.ma/user/{username}" if username else None,
    )


def _extract_next_data(page: Page) -> dict | None:
    """Extract __NEXT_DATA__ JSON from the page."""
    try:
        data = page.evaluate("() => window.__NEXT_DATA__")
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Fallback: parse from HTML
    try:
        el = page.query_selector("script#__NEXT_DATA__")
        if el:
            return json.loads(el.inner_text())
    except Exception:
        pass

    return None


def _fetch_all_guests_via_api(page: Page, event_api_id: str) -> list[dict]:
    """Fetch the full guest list using Luma's internal API via the browser context."""
    all_entries: list[dict] = []
    seen_ids: set[str] = set()
    cursor = None

    for _ in range(20):  # safety limit
        cursor_param = f'&cursor={cursor}' if cursor else ''
        url = f"https://api2.luma.com/event/get-guest-list?event_api_id={event_api_id}&limit=100{cursor_param}"

        try:
            result = page.evaluate("""
                async (url) => {
                    const resp = await fetch(url, {
                        credentials: 'include',
                        headers: { 'x-luma-client-type': 'luma-web' },
                    });
                    return await resp.json();
                }
            """, url)
        except Exception as e:
            console.print(f"[yellow]API fetch error: {e}[/yellow]")
            break

        if not isinstance(result, dict):
            break

        entries = result.get("entries", [])
        new_count = 0
        for entry in entries:
            api_id = entry.get("api_id", "")
            if api_id not in seen_ids:
                seen_ids.add(api_id)
                all_entries.append(entry)
                new_count += 1

        console.print(f"  Fetched {new_count} new guests (total: {len(all_entries)})")

        if new_count == 0 or not result.get("has_more"):
            break
        cursor = result.get("next_cursor")
        if not cursor:
            break

    return all_entries


def scrape_event_guests(
    event_url: str,
    headless: bool = True,
    max_guests: int = 0,
) -> tuple[list[LumaGuest], str | None]:
    """Scrape guest list from a Luma event page. Returns (guests, event_name)."""
    all_guests: list[LumaGuest] = []
    seen_names: set[str] = set()
    event_name: str | None = None

    def add_guest(guest: LumaGuest) -> None:
        if guest.name and guest.name not in seen_names:
            seen_names.add(guest.name)
            all_guests.append(guest)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context_kwargs = {}
        if LUMA_BROWSER_STATE_PATH.exists():
            context_kwargs["storage_state"] = str(LUMA_BROWSER_STATE_PATH)
            console.print("[dim]Using saved Luma session.[/dim]")
        else:
            console.print(
                "[yellow]No Luma session found. Browsing as logged-out user.[/yellow]\n"
                "[yellow]Run `scrape-luma luma-login` to access private guest lists.[/yellow]"
            )
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        console.print(f"Navigating to [bold]{event_url}[/bold]...")
        page.goto(event_url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Extract __NEXT_DATA__ for event info and featured guests
        next_data = _extract_next_data(page)
        if not next_data:
            console.print("[red]Could not extract page data.[/red]")
            browser.close()
            return []

        page_data = next_data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("data", {})
        event_data = page_data.get("event", {})
        event_api_id = event_data.get("api_id")
        guest_count = page_data.get("guest_count", 0)
        show_guest_list = event_data.get("show_guest_list", False)

        event_name = event_data.get("name") or None
        console.print(f"Event: [bold]{event_name or 'Unknown'}[/bold]")
        console.print(f"Guest count: {guest_count}, Guest list visible: {show_guest_list}")

        # Get featured guests from initial page data
        featured = page_data.get("featured_guests", [])
        for user in featured:
            add_guest(_parse_featured_guest(user))
        console.print(f"Got {len(featured)} featured guests from page data.")

        # Fetch full guest list via API if we have event ID
        if event_api_id and show_guest_list:
            console.print("Fetching full guest list via API...")
            entries = _fetch_all_guests_via_api(page, event_api_id)
            for entry in entries:
                guest = _parse_api_guest_entry(entry)
                if guest:
                    add_guest(guest)
            console.print(f"Total unique guests: [bold]{len(all_guests)}[/bold]")
        elif not show_guest_list:
            console.print("[yellow]Guest list is not public for this event.[/yellow]")

        browser.close()

    if not all_guests:
        console.print("[red]No guests found.[/red]")

    if max_guests > 0:
        all_guests = all_guests[:max_guests]

    return all_guests, event_name

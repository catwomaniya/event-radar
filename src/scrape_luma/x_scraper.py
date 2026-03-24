import random
import time
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from rich.console import Console

from scrape_luma.config import (
    AUTH_DIR,
    MAX_RATE_LIMIT_RETRIES,
    PAGE_LOAD_TIMEOUT_MS,
    RATE_LIMIT_BACKOFF,
    X_BROWSER_STATE_PATH,
    X_DELAY_MAX,
    X_DELAY_MIN,
    X_LOGIN_TIMEOUT_MS,
)
from scrape_luma.models import XProfile

console = Console()


_ANTI_DETECT_ARGS = [
    "--disable-blink-features=AutomationControlled",
]


def save_login_session() -> None:
    """Open a visible browser for the user to log into X. Save session state."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    profile_dir = str(AUTH_DIR / "x_profile")

    with sync_playwright() as p:
        # Use persistent context — real browser profile, no webdriver flag
        context = p.chromium.launch_persistent_context(
            profile_dir,
            headless=False,
        )
        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://x.com/login", timeout=30_000)
        page.wait_for_timeout(2000)

        # X sometimes shows "Something went wrong" on first load — reload to fix
        if "Something went wrong" in page.content() or "something went wrong" in page.content().lower():
            page.reload(timeout=30_000)
            page.wait_for_timeout(2000)

        console.print("[bold]Log into X/Twitter in the browser window.[/bold]")
        console.print("Waiting up to 5 minutes for login to complete...")

        try:
            page.wait_for_url(
                "**/home**",
                timeout=300_000,  # 5 minutes
            )
        except Exception:
            console.print("[red]Timeout waiting for login. Try again.[/red]")
            context.close()
            return

        context.storage_state(path=str(X_BROWSER_STATE_PATH))
        console.print(
            f"[green]Session saved to {X_BROWSER_STATE_PATH}[/green]"
        )
        context.close()


@contextmanager
def x_browser(
    headless: bool = True,
) -> Generator[tuple[BrowserContext, Browser], None, None]:
    """Context manager that yields a browser context with saved X session."""
    if not X_BROWSER_STATE_PATH.exists():
        raise FileNotFoundError(
            f"X browser state not found at {X_BROWSER_STATE_PATH}. "
            "Run `scrape-luma x-login` first."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
        )
        context = browser.new_context(
            storage_state=str(X_BROWSER_STATE_PATH),
        )
        try:
            yield context, browser
        finally:
            context.close()
            browser.close()


def _extract_text(page: Page, selector: str) -> str | None:
    el = page.query_selector(selector)
    if el:
        text = el.inner_text().strip()
        return text if text else None
    return None


def _check_rate_limit(page: Page) -> bool:
    """Return True if the page shows a rate limit message."""
    content = page.content()
    return "Rate limit" in content or "rate limit" in content.lower()


def _check_suspended(page: Page) -> str | None:
    """Return an error string if the account is suspended or not found."""
    content = page.content()
    if "Account suspended" in content:
        return "account_suspended"
    if "This account doesn" in content:
        return "account_not_found"
    # Check for "doesn't exist" or similar
    not_found = page.query_selector('[data-testid="empty_state_header_text"]')
    if not_found:
        return "account_not_found"
    return None


def scrape_profile(
    page: Page,
    handle: str,
) -> XProfile:
    """Scrape a single X profile. Caller manages the browser/page lifecycle."""
    url = f"https://x.com/{handle}"
    try:
        page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        # Give the page a moment to hydrate
        page.wait_for_timeout(2000)
    except Exception as e:
        return XProfile(handle=handle, error=f"navigation_error: {e}")

    # Check for login redirect (session expired)
    if "/login" in page.url or "/i/flow/login" in page.url:
        return XProfile(handle=handle, error="session_expired")

    # Check rate limit
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        if not _check_rate_limit(page):
            break
        if attempt == MAX_RATE_LIMIT_RETRIES:
            return XProfile(handle=handle, error="rate_limited")
        wait = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
        console.print(f"[yellow]Rate limited. Waiting {wait}s...[/yellow]")
        time.sleep(wait)
        page.reload(timeout=PAGE_LOAD_TIMEOUT_MS)
        page.wait_for_timeout(2000)

    # Check suspended / not found
    status_error = _check_suspended(page)
    if status_error:
        return XProfile(handle=handle, error=status_error)

    # Extract profile data using data-testid selectors
    bio = _extract_text(page, '[data-testid="UserDescription"]')
    display_name = None
    name_el = page.query_selector('[data-testid="UserName"]')
    if name_el:
        # UserName contains both display name and @handle in nested spans
        spans = name_el.query_selector_all("span")
        if spans:
            display_name = spans[0].inner_text().strip()

    location = _extract_text(page, '[data-testid="UserLocation"]')
    website = _extract_text(page, '[data-testid="UserUrl"]')

    # Followers/following — look for links containing /followers or /following
    followers = None
    followers_link = page.query_selector(f'a[href="/{handle}/verified_followers"]')
    if not followers_link:
        followers_link = page.query_selector(f'a[href="/{handle}/followers"]')
    if followers_link:
        followers = followers_link.inner_text().strip()

    following_count = None
    following_link = page.query_selector(f'a[href="/{handle}/following"]')
    if following_link:
        following_count = following_link.inner_text().strip()

    return XProfile(
        handle=handle,
        display_name=display_name,
        bio=bio,
        location=location,
        website=website,
        followers=followers,
        following=following_count,
    )


def scrape_profiles(
    handles: list[str],
    headless: bool = True,
    delay_min: float = X_DELAY_MIN,
    delay_max: float = X_DELAY_MAX,
    progress_callback: object | None = None,
) -> dict[str, XProfile]:
    """Scrape multiple X profiles. Returns a dict of handle -> XProfile."""
    results: dict[str, XProfile] = {}
    session_expired = False

    with x_browser(headless=headless) as (context, browser):
        page = context.new_page()

        for i, handle in enumerate(handles):
            if session_expired:
                results[handle] = XProfile(handle=handle, error="session_expired")
                if progress_callback:
                    progress_callback(i + 1)  # type: ignore[operator]
                continue

            profile = scrape_profile(page, handle)
            results[handle] = profile

            if profile.error == "session_expired":
                session_expired = True
                console.print(
                    "[red]X session expired. Remaining profiles will be skipped.[/red]"
                )
                console.print("Run `scrape-luma x-login` to re-authenticate.")

            if progress_callback:
                progress_callback(i + 1)  # type: ignore[operator]

            # Random delay between requests
            if i < len(handles) - 1:
                delay = random.uniform(delay_min, delay_max)
                time.sleep(delay)

        page.close()

    return results

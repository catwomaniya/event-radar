from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from scrape_luma.config import X_BROWSER_STATE_PATH

app = typer.Typer(
    name="scrape-luma",
    help="Scrape Luma event guest lists and X/Twitter bios.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def scrape(
    event_urls: Annotated[list[str], typer.Argument(help="One or more Luma event URLs")],
    headless: Annotated[bool, typer.Option(help="Run browser in headless mode")] = True,
    max_guests: Annotated[int, typer.Option(help="Maximum guests per event (0 = all)")] = 0,
    skip_x: Annotated[bool, typer.Option("--skip-x", help="Skip X/Twitter bio scraping")] = False,
    delay_min: Annotated[float, typer.Option(help="Min delay between X profile visits (sec)")] = 3.0,
    delay_max: Annotated[float, typer.Option(help="Max delay between X profile visits (sec)")] = 7.0,
    sheet_id: Annotated[Optional[str], typer.Option("--sheet-id", help="Google Sheet ID to write results to (share it with the service account first)")] = None,
) -> None:
    """Scrape Luma event guest list(s), fetch X bios, and print results."""
    from scrape_luma import luma_scraper, x_scraper

    # Validate X session exists if needed
    if not skip_x and not X_BROWSER_STATE_PATH.exists():
        console.print(
            "[red]X browser session not found.[/red] "
            "Run [bold]scrape-luma x-login[/bold] first, or use [bold]--skip-x[/bold]."
        )
        raise typer.Exit(1)

    for event_url in event_urls:
        console.print(f"\n[bold]Step 1:[/bold] Scraping guest list from {event_url}")
        guests, event_name = luma_scraper.scrape_event_guests(
            event_url=event_url,
            headless=headless,
            max_guests=max_guests,
        )

        if not guests:
            console.print("[red]No guests found.[/red]")
            continue

        console.print(f"[green]Found {len(guests)} guests.[/green]")

        # Scrape X profiles
        x_profiles: dict = {}
        handles = [g.x_handle for g in guests if g.x_handle]

        if not skip_x and handles:
            console.print(f"\n[bold]Step 2:[/bold] Scraping {len(handles)} X profiles...")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Scraping X profiles", total=len(handles))

                def update_progress(completed: int) -> None:
                    progress.update(task, completed=completed)

                x_profiles = x_scraper.scrape_profiles(
                    handles=handles,
                    headless=headless,
                    delay_min=delay_min,
                    delay_max=delay_max,
                    progress_callback=update_progress,
                )

            ok = sum(1 for p in x_profiles.values() if not p.error)
            errored = sum(1 for p in x_profiles.values() if p.error)
            console.print(f"[green]Scraped {ok} X profiles.[/green]")
            if errored:
                console.print(f"[yellow]{errored} profiles had errors.[/yellow]")

        # Print results table
        table = Table(title=f"Guests ({len(guests)})")
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style="bold")
        table.add_column("X Handle", style="cyan")
        table.add_column("X Bio")
        table.add_column("X Location", style="dim")
        table.add_column("Followers", style="dim")

        for i, g in enumerate(guests, 1):
            profile = x_profiles.get(g.x_handle) if g.x_handle else None
            table.add_row(
                str(i),
                g.name,
                f"@{g.x_handle}" if g.x_handle else "",
                (profile.bio or profile.error or "") if profile else "",
                (profile.location or "") if profile else "",
                (profile.followers or "") if profile else "",
            )

        console.print(table)

        x_count = sum(1 for g in guests if g.x_handle)
        console.print(
            f"  [green]{len(guests)}[/green] guests, "
            f"[cyan]{x_count}[/cyan] with X handles"
        )

        # Export to Google Sheets if requested
        if sheet_id:
            from datetime import datetime
            from scrape_luma import sheets
            from scrape_luma.models import GuestRow

            console.print(f"\n[bold]Step 3:[/bold] Writing to Google Sheet...")
            try:
                guest_rows = [
                    GuestRow.from_guest_and_profile(
                        g, x_profiles.get(g.x_handle) if g.x_handle else None
                    )
                    for g in guests
                ]
                spreadsheet = sheets.open_by_id(sheet_id)

                # Tab name: "Event Name (YYYY-MM-DD)"
                date_str = datetime.now().strftime("%Y-%m-%d")
                base = event_name or event_url.split("/")[-1].split("?")[0]
                tab_name = f"{base} ({date_str})"

                worksheet = sheets.write_guests(spreadsheet, guest_rows, tab_name=tab_name)
                tab_url = f"{spreadsheet.url}#gid={worksheet.id}"
                console.print(f"[green]Done![/green] Tab '{worksheet.title}': [link={tab_url}]{tab_url}[/link]")
            except FileNotFoundError:
                console.print(
                    "[red]Google Sheets credentials not found.[/red]\n"
                    "Place your service account file at creds/gspread_service_account.json"
                )
            except Exception as e:
                console.print(f"[red]Sheets export failed: {e}[/red]")


@app.command("luma-login")
def luma_login() -> None:
    """Open a browser to log into Luma. Saves session for accessing private guest lists."""
    from scrape_luma.luma_scraper import save_login_session

    console.print("Opening browser for Luma login...")
    save_login_session()


@app.command("x-login")
def x_login() -> None:
    """Open a browser to log into X/Twitter. Saves session for reuse."""
    from scrape_luma.x_scraper import save_login_session

    console.print("Opening browser for X/Twitter login...")
    save_login_session()


@app.command("ui")
def ui(
    host: Annotated[str, typer.Option(help="Host to bind (use 0.0.0.0 for LAN)")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on")] = 8000,
    reload: Annotated[bool, typer.Option(help="Auto-reload on code changes")] = False,
) -> None:
    """Start a local web UI for entering event URLs."""
    import uvicorn

    console.print(f"Starting UI at http://{host}:{port}")
    uvicorn.run(
        "scrape_luma.web:web_app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command("test-sheets")
def test_sheets(
    sheet_id: Annotated[str, typer.Argument(help="Google Sheet ID to test writing to")],
) -> None:
    """Write a test row to an existing Google Sheet to verify credentials work."""
    from scrape_luma.sheets import test_connection

    console.print("Testing Google Sheets connection...")
    try:
        url = test_connection(sheet_id=sheet_id)
        console.print(f"[green]Success![/green] Sheet: [link={url}]{url}[/link]")
    except FileNotFoundError:
        console.print(
            "[red]Service account credentials not found.[/red]\n"
            "Place your credentials at creds/gspread_service_account.json"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        raise typer.Exit(1)

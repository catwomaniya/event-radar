import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from scrape_luma.config import DEFAULT_CREDENTIALS_PATH
from scrape_luma.models import GuestRow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_creds(credentials_path: str | None = None) -> Credentials:
    path = credentials_path or str(DEFAULT_CREDENTIALS_PATH)
    return Credentials.from_service_account_file(path, scopes=SCOPES)


def _get_client(credentials_path: str | None = None) -> gspread.Client:
    return gspread.authorize(_get_creds(credentials_path))


def open_by_id(
    sheet_id: str,
    credentials_path: str | None = None,
) -> gspread.Spreadsheet:
    """Open an existing spreadsheet by its ID."""
    client = _get_client(credentials_path)
    return client.open_by_key(sheet_id)


def write_guests(
    spreadsheet: gspread.Spreadsheet,
    guests: list[GuestRow],
    tab_name: str | None = None,
) -> gspread.Worksheet:
    """Write guests to a worksheet tab. Creates a new tab if tab_name is given."""
    if tab_name:
        # Truncate to Google Sheets' 100-char tab name limit
        tab_name = tab_name[:100]
        try:
            worksheet = spreadsheet.worksheet(tab_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=20)
    else:
        worksheet = spreadsheet.sheet1
        worksheet.clear()

    rows = [GuestRow.header()] + [g.to_row() for g in guests]
    worksheet.update(rows, value_input_option="USER_ENTERED")

    # Bold the header row
    worksheet.format("1:1", {"textFormat": {"bold": True}})
    return worksheet


def test_connection(
    sheet_id: str,
    credentials_path: str | None = None,
) -> str:
    """Write to an existing spreadsheet to verify credentials work."""
    spreadsheet = open_by_id(sheet_id, credentials_path=credentials_path)
    ws = spreadsheet.sheet1
    ws.update([["Connection test successful"]], value_input_option="USER_ENTERED")
    return spreadsheet.url

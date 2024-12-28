from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import mm_calls
from log import logging
from src.config import SERVICE_ACCOUNT_FILE, SPREADSHEET_ID



# Scope for Sheets API access
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Authenticate and create a service object
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

service = build("sheets", "v4", credentials=credentials)


# Google Sheets function to write data
def write_to_sheet(sheet_name, data):

    try:
        # Write data to Google Sheets
        sheet_range = sheet_name + "!A1"
        body = {"values": data}
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_range,
            body=body,
            valueInputOption="RAW",
        ).execute()
        logging.info(f"Successfully wrote data to {sheet_name}")
    except HttpError as err:
        logging.error(f"Error occurred while writing to Google Sheets: {err}")


def extract_event_data_for_sheets(mm_instance):
    """
    Extracts event and market data from mm_instance.sport_events and returns it
    in a list-of-lists format suitable for Google Sheets.

    Each row could represent:
    Event Name | Market Type | Selection Name | Line ID
    """

    # Define headers for the sheet
    data_to_write = [
        [
            "Event ID",
            "Event Scheduled Time",
            "Event Name",
            "Event Competitor 1",
            "Event Competitor 1 Abbreviation",
            "Event Competitor 1 Side",
            "Event Competitor 2",
            "Event Competitor 2 Abbreviation",
            "Event Competitor 2 Side",
            "Market ID",
            "Market Name",
            "Market Type",
            "Market Status",
            "Market Line ID",
            "Market Line Name", 
            "Market Line",
            "Market Line Favourite",
            "Market Line Type",
            "Selection ID",
            "Selection Name",
            "Selection Odds",
            "Event Status",
            "Selection Stake",
            "Selection Value",
            "Market Updated",
        ]
    ]

    for event_id, event_data in mm_instance.sport_events.items():
        for market in event_data.get("markets", []):
            if "market_lines" in market.keys():
                for market_line in market.get("market_lines", []):
                    for selection in market_line.get("selections", []):
                        data_to_write.append(
                        # Create row data dictionary
                        [
                            event_id,
                            event_data.get("scheduled", ""),
                            event_data.get("display_name", ""),
                            event_data.get("competitors", [{}])[0].get(
                                "display_name", ""
                            ),
                            event_data.get("competitors", [{}])[0].get(
                                "abbreviation", ""
                            ),
                            event_data.get("competitors", [{}])[0].get("side", ""),
                            event_data.get("competitors", [{}])[1].get(
                                "display_name", ""
                            ),
                            event_data.get("competitors", [{}])[1].get(
                                "abbreviation", ""
                            ),
                            event_data.get("competitors", [{}])[1].get("side", ""),
                            market.get("id", ""),
                            market.get("name", ""),
                            market.get("type", ""),
                            market.get("status", ""),
                            market_line.get("id", ""),
                            market_line.get("name", ""),
                            market_line.get("line", ""),
                            market_line.get("favourite", "NA"),
                            market_line.get("type", ""),
                            selection[0].get("line_id", ""),
                            selection[0].get("display_name", ""),
                            selection[0].get("odds", ""),
                            event_data.get("status", ""),
                            selection[0].get("stake", ""),
                            selection[0].get("value", ""),
                            datetime.fromtimestamp(
                                market.get("updated_at", "0") / 1e9
                            ).__str__(),
                        ]
                    )
            else:
                for selection in market.get("selections", []):
                    data_to_write.append(
                        # Create row data dictionary
                        [
                            event_id,
                            event_data.get("scheduled", ""),
                            event_data.get("display_name", ""),
                            event_data.get("competitors", [{}])[0].get(
                                "display_name", ""
                            ),
                            event_data.get("competitors", [{}])[0].get(
                                "abbreviation", ""
                            ),
                            event_data.get("competitors", [{}])[0].get("side", ""),
                            event_data.get("competitors", [{}])[1].get(
                                "display_name", ""
                            ),
                            event_data.get("competitors", [{}])[1].get(
                                "abbreviation", ""
                            ),
                            event_data.get("competitors", [{}])[1].get("side", ""),
                            market.get("id", ""),
                            market.get("name", ""),
                            market.get("type", ""),
                            market.get("status", ""),
                            "NA",
                            "NA",
                            "NA",
                            "NA",
                            "NA",
                            selection[0].get("line_id", ""),
                            selection[0].get("display_name", ""),
                            selection[0].get("odds", ""),
                            event_data.get("status", ""),
                            selection[0].get("stake", ""),
                            selection[0].get("value", ""),
                            datetime.fromtimestamp(
                                market.get("updated_at", "0") / 1e9
                            ).__str__(),
                        ]
                    )

    return data_to_write


# Main code execution
if __name__ == "__main__":
    logging.info("Testing MM api")

    mm_instance = mm_calls.MMInteractions()
    mm_instance.mm_login()
    mm_instance.get_balance()
    mm_instance.seeding()  # After this, mm_instance.sport_events should be populated
    mm_instance.subscribe()
    # mm_instance.auto_playing() # Commented out to prevent infinite loops while testing

    # Extract the event/market data to a format suitable for Sheets
    data_to_write = extract_event_data_for_sheets(mm_instance)

    # Print the data to verify its structure
    logging.info("Data to write to Google Sheets:")
    logging.info(data_to_write)

    # Write the data to Google Sheets
    logging.info("Writing data to Google Sheets...")
    write_to_sheet(
        "Sheet1", data_to_write
    )  # Replace "Sheet1" with your actual sheet name

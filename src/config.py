import json
from dotenv import load_dotenv
import os

load_dotenv(override=True)

# Get the absolute path of the file
file_path = os.path.join(os.path.dirname(__file__), "user_info.json")

with open(file_path) as fp:
    user_info_dict = json.load(fp)

MM_KEYS = {
    "access_key": user_info_dict["access_key"],
    "secret_key": user_info_dict["secret_key"],
}

TOURNAMENTS_INTERESTED = user_info_dict["tournaments"]

BASE_URL = "https://api-ss-sandbox.betprophet.co"
URL = {
    "mm_login": "partner/auth/login",
    "mm_refresh": "partner/auth/refresh",
    "mm_ping": "partner/mm/pusher/ping",
    "mm_auth": "partner/mm/pusher",
    "mm_tournaments": "partner/mm/get_tournaments",
    "mm_events": "partner/mm/get_sport_events",
    "mm_markets": "partner/mm/get_markets",
    "mm_multiple_markets": "partner/mm/get_multiple_markets",
    "mm_balance": "partner/mm/get_balance",
    "mm_place_wager": "partner/mm/place_wager",
    "mm_cancel_wager": "partner/mm/cancel_wager",
    "mm_odds_ladder": "partner/mm/get_odds_ladder",
    "mm_batch_cancel": "partner/mm/cancel_multiple_wagers",
    "mm_batch_place": "partner/mm/place_multiple_wagers",
    "mm_cancel_all_wagers": "partner/mm/cancel_all_wagers",
    "websocket_config": "partner/websocket/connection-config",
}

# Path to your service account key file
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

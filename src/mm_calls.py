import time            # Provides time-related functions, such as sleep
import requests        # Allows us to send HTTP requests easily
import json            # For working with JSON data
import pysher          # A Python client for interacting with Pusher (WebSockets)
import base64          # For encoding/decoding data in Base64 format
import schedule        # Allows scheduling tasks at specific intervals
import random          # For generating random numbers
import threading       # For running tasks in parallel threads
import uuid            # For generating unique identifiers

from urllib.parse import urljoin  # Helps safely combine parts of URLs
import config                     # Custom config file (likely storing constants, keys, etc.)
from log import logging           # Custom log module for logging messages
import constants                  # Another custom file storing constants

class MMInteractions:
    base_url: str = None          # Base URL for the API
    balance: float = 0            # User's current balance
    mm_keys: dict = dict()        # Dictionary to store keys (access/secret) for authentication
    mm_session: dict = dict()     # Dictionary to store session-related info (tokens)
    all_tournaments: dict = dict()# Stores all tournaments from the API
    my_tournaments: dict = dict() # Stores only the tournaments we are interested in
    sport_events: dict = dict()   # Stores event details keyed by event_id, including markets
    wagers: dict = dict()         # Stores placed wagers keyed by some unique identifier
    valid_odds: list = []         # Stores valid odds retrieved from the API
    pusher = None                 # Will hold the Pusher (WebSocket) connection object

    def __init__(self):
        self.base_url = config.BASE_URL      # Set the base URL from config
        self.mm_keys = config.MM_KEYS        # Set the mm_keys (access/secret) from config

    def mm_login(self) -> dict:
        """
        Logs into the MM API using the provided keys and saves the session details.
        """
        login_url = urljoin(self.base_url, config.URL['mm_login'])   # Build full login URL
        request_body = {
            'access_key': self.mm_keys.get('access_key'),            # Include the access key
            'secret_key': self.mm_keys.get('secret_key'),            # Include the secret key
        }
        response = requests.post(login_url, data=json.dumps(request_body)) # Send POST request to login
        if response.status_code != 200:                               # Check if login failed
            logging.debug(response)
            logging.debug("Please check your access key and secrete key to the user_info.json")
            raise Exception("login failed")                           # Stop if login isn't successful
        mm_session = json.loads(response.content)['data']            # Extract session data from response
        logging.info(mm_session)
        self.mm_session = mm_session                                 # Store session for later use
        logging.info("MM session started")
        return mm_session

    def seeding(self):
        """
        This method:
        1. Gets a list of valid odds from the API.
        2. Retrieves all tournaments, filters those we are interested in.
        3. For each interested tournament, fetches associated events and their markets.
        """
        logging.info("start to get odds ladder")
        odds_ladder_url = urljoin(self.base_url, config.URL['mm_odds_ladder'])   # URL for odds ladder
        odds_response = requests.get(odds_ladder_url, headers=self.__get_auth_header()) # GET request for odds
        if odds_response.status_code != 200:      # If we can't get odds from the API
            logging.info("not able to get valid odds from api, fall back to local constants")
            self.valid_odds = constants.VALID_ODDS_BACKUP  # Use backup odds if API fails
        else:
            self.valid_odds = odds_response.json()['data']   # Store the valid odds from the API

        logging.info("start seeding tournaments/events/markets")
        t_url = urljoin(self.base_url, config.URL['mm_tournaments'])  # URL for tournaments
        headers = self.__get_auth_header()                            # Authorization header
        all_tournaments_response = requests.get(t_url, headers=headers) # GET all tournaments
        if all_tournaments_response.status_code != 200:
            raise Exception("not able to seed tournaments")            # Stop if tournaments can't be retrieved
        all_tournaments = json.loads(all_tournaments_response.content).get('data', {}).get('tournaments', {})
        self.all_tournaments = all_tournaments                        # Store all tournaments retrieved

        event_url = urljoin(self.base_url, config.URL['mm_events'])           # URL for events
        multiple_markets_url = urljoin(self.base_url, config.URL['mm_multiple_markets']) # URL for multiple markets

        # Loop through all tournaments returned
        for one_t in all_tournaments:
            # Check if tournament name is in the list we care about
            if one_t['name'] in config.TOURNAMENTS_INTERESTED:
                self.my_tournaments[one_t['id']] = one_t  # Add it to my_tournaments dictionary
                events_response = requests.get(event_url, params={'tournament_id': one_t['id']}, headers=headers)
                if events_response.status_code == 200:
                    events = json.loads(events_response.content).get('data', {}).get('sport_events')
                    #logging.info("printing events")
                    #print(events)
                    if events is None: # If no events for this tournament, continue to next
                        continue

                    # Collect event_ids to fetch their markets in one go
                    event_ids = ','.join([str(event['event_id']) for event in events])
                    multiple_markets_response = requests.get(multiple_markets_url, params={'event_ids': event_ids},
                                                             headers=headers)
                    if multiple_markets_response.status_code == 200:
                        # Get a dictionary mapping event_id to their market data
                        map_market_by_event_id = json.loads(multiple_markets_response.content).get('data', {})
                        for event in events:
                            # Ensure that we have market info for this event
                            if str(event['event_id']) not in map_market_by_event_id:
                                continue
                            event['markets'] = map_market_by_event_id[str(event['event_id'])] # Attach markets to event
                            self.sport_events[event['event_id']] = event                     # Store the full event data
                            logging.info(f'successfully get markets of events {event["name"]}')
                            #print(self.sport_events)
                    else:
                        logging.info(f'failed to get markets of events ids: {",".join([str(event["event_id"]) for event in events])}')
                else:
                    logging.info(f'skip tournament {one_t["name"]} as api request failed')

        logging.info("Done, seeding")
        logging.info(f"found {len(self.my_tournaments)} tournament, ingested {len(self.sport_events)} "
                     f"sport events from {len(config.TOURNAMENTS_INTERESTED)} tournaments")

    def _get_channels(self, socket_id: float):
        """
        Retrieves authorized channels (public/private) for this user.
        """
        auth_endpoint_url = urljoin(self.base_url, config.URL['mm_auth'])   # URL for auth endpoint
        channels_response = requests.post(auth_endpoint_url,
                                          data={'socket_id': socket_id},
                                          headers=self.__get_auth_header())
        if channels_response.status_code != 200:
            logging.error("failed to get channels")
            raise Exception("failed to get channels")
        channels = channels_response.json()
        return channels.get('data', {}).get('authorized_channel', [])

    def _get_connection_config(self):
        """
        Gets configuration settings for connecting to the Pusher WebSocket service.
        """
        connection_config_url = urljoin(self.base_url, config.URL['websocket_config']) # URL for websocket config
        connection_response = requests.get(connection_config_url, headers=self.__get_auth_header())
        if connection_response.status_code != 200:
            logging.error("failed to get connection configs")
            raise Exception("failed to get channels")
        conn_configs = connection_response.json()
        return conn_configs

    def subscribe(self):
        """
        1. Get WebSocket connection config.
        2. Connect to Pusher WebSocket using our credentials.
        3. On successful connection, subscribe to channels and events we are interested in.
        """
        connection_config = self._get_connection_config()  # Get pusher configs
        key = connection_config['key']
        cluster = connection_config['cluster']

        auth_endpoint_url = urljoin(self.base_url, config.URL['mm_auth'])
        auth_header = self.__get_auth_header()
        auth_headers = {
            "Authorization": auth_header['Authorization'],
            "header-subscriptions": '''[{"type":"tournament","ids":[]}]''',
        }

        self.pusher = pysher.Pusher(key=key, cluster=cluster,
                                    auth_endpoint=auth_endpoint_url,
                                    auth_endpoint_headers=auth_headers)

        def public_event_handler(*args, **kwargs):
            # Handler for events from public channels
            print("processing public, Args:", args)
            print(f"event details {base64.b64decode(json.loads(args[0]).get('payload', '{}'))}")
            print("processing public, Kwargs:", kwargs)

        def private_event_handler(*args, **kwargs):
            # Handler for events from private channels
            print("processing private, Args:", args)
            print(f"event details {base64.b64decode(json.loads(args[0]).get('payload', '{}'))}")
            print("processing private, Kwargs:", kwargs)

        def connect_handler(data):
            # This runs once connection is established
            socket_id = json.loads(data)['socket_id']
            available_channels = self._get_channels(socket_id)
            broadcast_channel_name = None
            private_channel_name = None
            private_events = None
            # Extract channel names from the available channels
            for channel in available_channels:
                if 'broadcast' in channel['channel_name']:
                    broadcast_channel_name = channel['channel_name']
                else:
                    private_channel_name = channel['channel_name']
                    private_events = channel['binding_events']

            # Subscribe to the broadcast (public) and private channels
            broadcast_channel = self.pusher.subscribe(broadcast_channel_name)
            private_channel = self.pusher.subscribe(private_channel_name)

            # For each tournament we're interested in, bind public events
            for t_id in self.my_tournaments:
                event_name = f'tournament_{t_id}'
                broadcast_channel.bind(event_name, public_event_handler)
                logging.info(f"subscribed to public channel, event name: {event_name}, successfully")

            # For each private event, bind the private event handler
            for private_event in private_events:
                private_channel.bind(private_event['name'], private_event_handler)
                logging.info(f"subscribed to private channel, event name: {private_event['name']}, successfully")

        # Bind the connect handler to run when we're connected
        self.pusher.connection.bind('pusher:connection_established', connect_handler)
        self.pusher.connect()  # Initiate the connection

    def get_balance(self):
        """
        Fetches and logs the user's current balance.
        """
        balance_url = urljoin(self.base_url, config.URL['mm_balance'])
        response = requests.get(balance_url, headers=self.__get_auth_header())
        if response.status_code != 200:
            logging.error("failed to get balance")
            return
        self.balance = json.loads(response.content).get('data', {}).get('balance', 0)
        logging.info(f"still have ${self.balance} left")

    def start_playing(self):
        """
        Example function showing how to place wagers (both single and batch).
        Randomly decides when and how to place bets on events' moneyline markets.
        """
        logging.info("Start playing, randomly :)")
        play_url = urljoin(self.base_url, config.URL['mm_place_wager'])
        batch_play_url = urljoin(self.base_url, config.URL['mm_batch_place'])
        if '.prophetx.co' in play_url:
            # Safety check: do not run in production
            raise Exception("only allowed to run in non production environment")

        # Loop through all sport events
        for key in self.sport_events:
            one_event = self.sport_events[key]
            # Look for markets in the event
            for market in one_event.get('markets', []):
                if market['type'] == 'moneyline':
                    # We only consider moneyline bets here
                    if random.random() < 0.3: # 30% chance to consider this event
                        for selection in market.get('selections', []):
                            if random.random() < 0.3: # 30% chance to choose this selection
                                odds_to_play = self.__get_random_odds()
                                external_id = str(uuid.uuid1())  # Unique ID for the wager
                                logging.info(f"going to play on '{one_event['name']}' on moneyline, side {selection[0]['name']} with odds {odds_to_play}")
                                body_to_send = {
                                    'external_id': external_id,
                                    'line_id': selection[0]['line_id'],
                                    'odds': odds_to_play,
                                    'stake': 1.0
                                }
                                # Place single wager
                                play_response = requests.post(play_url, json=body_to_send,
                                                              headers=self.__get_auth_header())
                                if play_response.status_code != 200:
                                    logging.info(f"failed to play, error {play_response.content}")
                                else:
                                    logging.info("successfully")
                                    # Store this wager ID
                                    self.wagers[external_id] = json.loads(play_response.content).get('data', {})['wager']['id']

                                # Test batch wager placement
                                batch_n = 3  # Place 3 wagers at once
                                external_id_batch = [str(uuid.uuid1()) for x in range(batch_n)]
                                batch_body_to_send = [{
                                    'external_id': external_id_batch[x],
                                    'line_id': selection[0]['line_id'],
                                    'odds': odds_to_play,
                                    'stake': 1.0
                                } for x in range(batch_n)]
                                batch_play_response = requests.post(batch_play_url, json={"data": batch_body_to_send},
                                                                     headers=self.__get_auth_header())
                                if batch_play_response.status_code != 200:
                                    logging.info(f"failed to play, error {play_response.content}")
                                else:
                                    logging.info("successfully")
                                    # Store all newly placed wagers
                                    for wager in batch_play_response.json()['data']['succeed_wagers']:
                                        self.wagers[wager['external_id']] = wager['id']

    def cancel_all_wagers(self):
        """
        Cancels all open wagers placed so far.
        """
        logging.info("CANCELLING ALL WAGERS")
        cancel_all_url = urljoin(self.base_url, config.URL['mm_cancel_all_wagers'])
        body = {}
        response = requests.post(cancel_all_url, json=body, headers=self.__get_auth_header())
        if response.status_code != 200:
            if response.status_code == 404:
                logging.info("already cancelled")
            else:
                logging.info("failed to cancel")
        else:
            logging.info("cancelled successfully")
            self.wagers = dict() # Clear the wagers dictionary

    def random_cancel_wager(self):
        """
        Tries to randomly cancel some wagers one by one.
        """
        wager_keys = list(self.wagers.keys())
        for key in wager_keys:
            if key not in self.wagers:
                continue
            wager_id = self.wagers[key]
            cancel_url = urljoin(self.base_url, config.URL['mm_cancel_wager'])
            if random.random() < 0.5:  # 50% chance to attempt cancellation
                logging.info("start to cancel wager")
                body = {
                    'external_id': key,
                    'wager_id': wager_id,
                }
                response = requests.post(cancel_url, json=body, headers=self.__get_auth_header())
                if response.status_code != 200:
                    if response.status_code == 404:
                        logging.info("already cancelled")
                        if key in self.wagers:
                            self.wagers.pop(key)
                    else:
                        logging.info("failed to cancel")
                else:
                    logging.info("cancelled successfully")
                    self.wagers.pop(key) # Remove cancelled wager from dictionary

    def random_batch_cancel_wagers(self):
        """
        Tries to randomly cancel a batch of wagers at once.
        """
        wager_keys = list(self.wagers.keys())
        # Choose up to 4 random wagers to cancel
        batch_keys_to_cancel = random.choices(wager_keys, k=min(4, len(wager_keys)))
        batch_cancel_body = [{'wager_id': self.wagers[x],
                              'external_id': x} for x in batch_keys_to_cancel]
        batch_cancel_url = urljoin(self.base_url, config.URL['mm_batch_cancel'])
        response = requests.post(batch_cancel_url, json={'data': batch_cancel_body}, headers=self.__get_auth_header())
        if response.status_code != 200:
            if response.status_code == 404:
                logging.info("already cancelled")
                [self.wagers.pop(x) for x in batch_keys_to_cancel]
            else:
                logging.info("failed to cancel")
        else:
            logging.info("cancelled successfully")
            for key in batch_keys_to_cancel:
                try:
                    self.wagers.pop(key)
                except Exception as e:
                    print(e)

    def __run_forever_in_thread(self):
        """
        Runs the scheduled tasks forever in a separate thread.
        """
        while True:
            schedule.run_pending() # Check if any scheduled task is due and run it
            time.sleep(1)          # Wait 1 second before checking again

    def __auto_extend_session(self):
        """
        Automatically refreshes the session token before it expires and reconnects the WebSocket.
        """
        refresh_url = urljoin(self.base_url, config.URL['mm_refresh'])
        response = requests.post(refresh_url, json={'refresh_token': self.mm_session['refresh_token']},
                                 headers=self.__get_auth_header())
        if response.status_code != 200:
            logging.info("Failed to call refresh endpoint")
        else:
            # Update the session with new access token
            self.mm_session['access_token'] = response.json()['data']['access_token']
            if self.pusher is not None:
                self.pusher.disconnect()
                self.pusher = None
            self.subscribe() # Re-subscribe to channels with new token

    def auto_playing(self):
        """
        Schedules several tasks to run periodically:
        - Placing wagers every 10 seconds
        - Randomly cancel wagers every 9 seconds
        - Randomly cancel a batch of wagers every 7 seconds
        - Refresh session every 8 minutes
        """
        logging.info("schedule to play every 10 seconds!")
        schedule.every(10).seconds.do(self.start_playing)
        schedule.every(9).seconds.do(self.random_cancel_wager)
        schedule.every(7).seconds.do(self.random_batch_cancel_wagers)
        schedule.every(8).minutes.do(self.__auto_extend_session)
        # schedule.every(60).seconds.do(self.cancel_all_wagers) # Example commented out

        child_thread = threading.Thread(target=self.__run_forever_in_thread, daemon=False)
        child_thread.start()  # Start the thread that runs these scheduled tasks

    def keep_alive(self):
        """
        Keeps the script running indefinitely by starting the run_forever thread without scheduling tasks.
        """
        child_thread = threading.Thread(target=self.__run_forever_in_thread, daemon=False)
        child_thread.start()

    def __get_auth_header(self) -> dict:
        """
        Constructs the authorization header needed for API requests using the current access token.
        """
        return {
            'Authorization': f'Bearer {self.mm_session["access_token"]}',
        }

    def __get_random_odds(self):
        """
        Picks a random odds value from the valid odds list, sometimes negating it, and ensures it never stays at -100.
        """
        odds = self.valid_odds[random.randint(0, len(self.valid_odds) - 1)] # Pick a random odds from list
        odds = odds if random.random() < 0.5 else -1 * odds                 # 50% chance to flip sign
        if odds == -100:
            odds = 100   # Avoid having exactly -100 odds
        return odds

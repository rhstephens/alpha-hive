import json
import requests
import time

from db import hive_db
from accounts import ACCOUNTS
from bs4 import BeautifulSoup
import datetime

BASE = 'https://boardgamearena.com'
LOGIN = '/account/account/login.html'
RANKING = '/gamepanel/gamepanel/getRanking.html'
DATA = '/gamepanel?game=hive'
PLAYER = '/gamestats'
GAMES = '/gamestats/gamestats/getGames.html'
TABLE = '/table/table/tableinfos.html'
ARCHIVE = '/gamereview/gamereview/requestTableArchive.html'
REPLAY = '/archive/archive/logs.html'
GAME_ID = 79

DEPLETED = 'You have reached a limit (replay)'
NO_ACCESS = 'Sorry, you need to be registered more than 24 hours and have played at least 2 games to access this feature.'
EMPTY_ARCHIVE = 'Unfortunately the replay for this game has been lost'

sess_gen = None


def session_generator():
    # must be a verified bga account with >=2 games and >24 hours old
    for email, password in ACCOUNTS:
        sess = requests.Session()
        sess.email = email

        # request to a login page needed to produce request_token
        resp = sess.get(BASE + '/account')
        soup = BeautifulSoup(resp.content, 'html.parser')
        token = soup.find(id='request_token')['value']
        login_info = {'email': email, 'password': password, 'rememberme': 'off', 'redirect': 'join', 'form_id': 'loginform', 'request_token': token}
        sess.post(BASE + LOGIN, data=login_info)

        # pass token along the headers (needed for later calls)
        sess.headers['X-Request-Token'] = token
        sess.headers['X-Requested-With'] = 'XMLHttpRequest'
        
        yield sess
    
    print(f'session_generator(): ALL accounts exhausted')


def get_next_session():
    global sess_gen
    if not sess_gen:
        sess_gen = session_generator()

    return next(sess_gen, None)


def get_top_arena_tables(sess, player_ids, months_ago=12):
    """ Returns a set of unique table ids for given player_ids' games within the last months_ago months
    """

    all_tables = set()
    exclusion_set = hive_db.get_unique_table_ids()
    now = int(time.time())
    start = int((datetime.datetime.now() - datetime.timedelta(months=months_ago)).timestamp())
    #TODO: start_date, end_date = get_current_season_timestamps(sess)

    for player_id in player_ids:
        # now that we have a valid token, search every page of this player's match history
        params = {'page': 0,
                  'player': player_id,
                  'game_id': GAME_ID,
                  'start_date': start,
                  'end_date': now,
                  'finished': 1,
                  'updateStats': 0
                 }
        table_ids = set()
        while True:
            if (params['page'] > 500):
                print('over 500 pages...')
                break
            params['page'] += 1
            resp = sess.get(BASE + GAMES, params=params)

            tables = resp.json()['data']['tables']
            if len(tables) == 0:
                break

            # get tables that were not forfeit
            ids = [int(table['table_id']) for table in tables if table['concede'] != '1']
            table_ids.update(ids)

        # exclude tables we already have in our DB
        table_ids = table_ids - exclusion_set
        all_tables.update(table_ids)

    return all_tables


def get_players_by_rank(sess, num_players=10):
    """ Returns the 10 highest ranking players' ids for the current season
    """

    players = set()
    params = {'game': GAME_ID, 'mode': 'arena'}

    # paginate 10 at a time
    for start in range(0, num_players, 10):
        params['start'] = start
        resp = sess.get(BASE + RANKING, params=params)

        for player in resp.json()['data']['ranks']:
            if len(players) >= num_players:
                break
            players.add(int(player['id']))

    return players


def get_expansion_info(sess, table_id):
    """ Returns a 3 boolean tuple describing whether the given table_id has expansions:
        (mosquito, ladybug, pillbug)
    """
    if not sess:
        return
    
    # get general info from table
    resp = sess.get(BASE + TABLE, params={'id': table_id})

    j = resp.json()
    if 'error' in j:
        print(f'Unknown error: {j["error"]}')
        return
    
    try:
        m = j['data']['options']['100']['value'] == '2'
        l = j['data']['options']['101']['value'] == '2'
        p = j['data']['options']['102']['value'] == '2'
    except:
        print(f'Unknown error: {j["error"]}')
        return table_id
    
    return (m, l, p)


def analyze_table_data(sess, table_id):
    """ Returns all information about this table_id's replay in the form of:
        (player_id_white, player_id_black, winner, expansion booleans, every move history for this table_id game)
        Returns None if error, or the table_id if the account is unable to access further replays.
    """

    if not sess:
        return
    
    # get general info from table
    resp = sess.get(BASE + TABLE, params={'table': table_id})

    j = resp.json()
    if 'error' in j:
        print(f'Unknown error: {j["error"]}')
        return
    
    try:
        m = j['data']['options']['100']['value'] == '2'
        l = j['data']['options']['101']['value'] == '2'
        p = j['data']['options']['102']['value'] == '2'
    except:
        print(f'Unknown error: {j["error"]}')
        return table_id
    


    # seemingly required to produce log
    sess.get(BASE + ARCHIVE, params={'table': table_id})
    resp = sess.get(BASE + REPLAY, params={'table': table_id, 'translated': 'true'})

    j = resp.json()
    if 'error' in j:
        if j['error'] == DEPLETED:
            print('Account replay access depleted.', sess.email)
            return
        elif j['error'] == NO_ACCESS:
            print('Account cannot access any replays.', sess.email)
            return
        elif EMPTY_ARCHIVE in j['error']:
            print(f'Skipping table {table_id}, the replay has been lost or corrupted')
            return table_id
        elif 'disabled for your account' in j['error']:
            print('Account banned: ', sess.email)
            return
        else:
            print(f'Unknown error: {j["error"]}')
            return table_id

    if 'data' not in j:
        print(f'Response from table_id {table_id} does not contain data:', sess.email)
        print(j)
        return
    
    # GENERAL LAYOUT OF THE RESPONSE JSON:
    # data
    #   players
    #       color
    #   logs
    #       move_id
    #       data
    #           type (tokenPlayed, queenSurr, [offer|accept]Draw, message)
    #           log
    #           args
    #               notation
    #               type_copied (only there if its a mosquito copy action)
    #                
    try:
        players = [player for player in j['data']['players']]
        player_white = players[0]['id'] if players[0]['color'] == '#ffffff' else players[1]['id']
        player_black = players[0]['id'] if players[0]['color'] == '#000000' else players[1]['id']
        winner = -1

        logs = [log for log in j['data']['logs']]
        moves = [(move['move_id'], move['data']) for move in logs]
        all_actions = []

        for move_id, move in moves:
            actions = []
            for action in move:
                result = {
                    'move_number': move_id,
                    'type': action['type'],
                    'log': action['log']
                }

                if action['type'] == 'tokenPlayed':
                    result['notation'] = action['args']['notation']
                    result['type_copied'] = action['args']['type_copied'] if 'type_copied' in action['args'] else ''
                elif action['type'] == 'queenSurr':
                    winner = action['args']['winner']
                elif action['type'] == 'offerDraw':
                    pass
                elif action['type'] == 'acceptDraw':
                    pass
                elif action['type'] == 'message':
                    pass
                else:
                    # skip everything else
                    continue

                # only want to record relevant action types
                actions.append(result)
            all_actions.extend(actions)

        # check for tie or draw
        num_winners = [action['type'] for action in all_actions if action['type'] == 'queenSurr']
        if len(num_winners) < 1:
            winner = 0 #draw
        elif len(num_winners) > 1:
            winner = 1 #tie (aka sacrifice victory)

        return (player_white, player_black, winner, m, l, p, all_actions)

    except Exception as e:
        print(f'Error analyzing replay for table {table_id}: ', e)
        print(e.__traceback__.tb_lineno)
        return


# old way of retrieving request token from embedded javascript. Leaving here in case its needed again
'''
    # need to get a request token for each individual player in order to retrieve their table history
    params = {'player': player_id}
    resp = sess.get(BASE + PLAYER, params=params)

    # add req token to session header
    soup = BeautifulSoup(resp.content, 'html.parser')
    regex = re.compile(r"'(.*?)'") # used to extract token from raw quoted text
    for tag in soup.find_all('script'):
        tag_split = tag.string.split('requestToken: ')
        if len(tag_split) > 1:
            request_token = regex.match(tag_split[1]).group().strip("'")
            sess.headers['X-Request-Token'] = request_token
            sess.headers['X-Requested-With'] = 'HMLHttpRequest'
'''

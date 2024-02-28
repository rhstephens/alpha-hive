import json
import os.path
import re
import requests
import time
import hive_db
from accounts import ACCOUNTS
from bs4 import BeautifulSoup
from collections import Counter
from datetime import datetime

BASE = 'https://boardgamearena.com'
LOGIN = '/account/account/login.html'
RANKING = '/gamepanel/gamepanel/getRanking.html'
DATA = '/gamepanel?game=hive'
PLAYER = '/gamestats'
GAMES = '/gamestats/gamestats/getGames.html'
ARCHIVE = '/gamereview/gamereview/requestTableArchive.html'
REPLAY = '/archive/archive/logs.html'
GAME_ID = 79
# start and end dates
SEASONS= {
    16: (1700606490,1708537294)
}

DEPELETED = 'You have reached a limit (replay)'
NO_ACCESS = 'Sorry, you need to be registered more than 24 hours and have played at least 2 games to access this feature.'

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


def get_current_season_timestamps(sess):
    """ Returns a tuple containing the start and end dates of the current season in unix timestamp form.
    """

    resp = sess.get(BASE + DATA, params={'game_id': GAME_ID, 'with_ranking_info': 'false'})
    j = resp.json()
    #TODO: REMOVE
    print(resp)
    print(f'get_current_season response: {j}')
    #
    start_date = datetime.fromisoformat(j['currentArenaTimeSpan']['start'])
    end_date = datetime.fromisoformat(j['currentArenaTimeSpan']['end'])
    return (int(start_date.timestamp()), int(end_date.timestamp()))


def get_top_arena_tables(sess, player_ids, season=16):
    """ Returns a set of unique table ids for arena games from the given player_ids this season.
    """

    all_tables = set()
    exclusion_set = hive_db.get_unique_table_ids()
    start_date, end_date = SEASONS[season][0], SEASONS[season][1]
    #TODO: start_date, end_date = get_current_season_timestamps(sess)

    for player_id in player_ids:
        # now that we have a valid token, search every page of this player's match history
        params = {'page': 0, 'player': player_id, 'game_id': GAME_ID, 'start_date': start_date, 'end_date': end_date, 'finished': 1, 'updateStats': 0}
        table_ids = set()
        while True:
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
    """ Returns the highest 10 ids for the players at, or below, the given rank
    """

    players = set()
    params = {'game': GAME_ID, 'mode': 'arena'}

    # paginate 10 at a time
    for start in range(0, num_players, 10):
        params['start'] = start
        resp = sess.get(BASE + RANKING, params=params)

        #TODO lookup player_ids and see the last update time to reduce number of calls
        for player in resp.json()['data']['ranks']:
            if len(players) >= num_players:
                break
            players.add(int(player['id']))

    return players


def analyze_table_data(sess, table_id):
    """ Returns all information about this table_id's replay in the form of:
        (player_id_white, player_id_black, winner, every move history for this table_id game)
        Returns None if error or the current account is unable to access further replays.
    """

    if not sess:
        return

    # seemingly required to produce log
    sess.get(BASE + ARCHIVE, params={'table': table_id})
    resp = sess.get(BASE + REPLAY, params={'table': table_id, 'translated': 'true'})
    j = resp.json()
    if 'error' in j:
        if j['error'] == DEPELETED:
            print('Account replay access depleted.')
            return
        elif j['error'] == NO_ACCESS:
            print('Account cannot access any replays.')
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

        return (player_white, player_black, winner, all_actions)

    except Exception as e:
        print(f'Error analyzing replay for table {table_id}: ', e)
        print(e.__traceback__.tb_lineno)
        return


# if ran as script, automatically begin scraping
if __name__ == '__main__':
    sess = get_next_session()

    player_ids = get_players_by_rank(sess, 10)
    print(f'found the top {len(player_ids)} ranking player IDs')

    for player in player_ids:
        hive_db.searched_player(player)

    table_ids = list(get_top_arena_tables(sess, player_ids))
    print(f'proccessing {len(table_ids)} table IDs:')

    index = 0
    session_count = 0
    while sess and index < len(table_ids):
        table_id = table_ids[index]
        result = analyze_table_data(sess, table_id)

        if not result:
            # try to get new acct
            # if result fails again, its all ogre
            print(f'session expired or account depleted... added {index - session_count} table_ids with {sess.email}, attempting next account')
            session_count = index
            sess = get_next_session()
            if not sess:
                break
            continue

        if not result:
            print(f'failed to retrieve data for table_id {table_id}')
            break
        
        # send to db
        hive_db.insert_table_data(table_id, *result)
        index += 1

    print(f'SCRAPING COMPLETED')
    print(f'  added {index} tables to db')
    print(f'  {len(table_ids) - index} ids remaining:')
    print(f'    {table_ids[index:]}')


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

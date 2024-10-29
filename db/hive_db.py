import sqlite3
import time
from contextlib import closing

BGA_START = 100000000 # 100,000,000
BGA_END =   999999999
BOT_NAMES = ['Dumbot', 'WeakBot', 'SmartBot']
DB_NAME = 'db/hivemind.db'
DB_SCHEMA = '''
BEGIN;
CREATE TABLE IF NOT EXISTS actions(
    move_number INTEGER NOT NULL,
    notation TEXT,
    table_id INTEGER,
    type TEXT NOT NULL,
    type_copied TEXT,
    log TEXT,
    FOREIGN KEY(table_id) REFERENCES tables(table_id),
    UNIQUE(move_number, table_id, type)
);
CREATE TABLE IF NOT EXISTS players(
    player_id INTEGER PRIMARY KEY,
    last_search_timestamp TEXT
);
CREATE TABLE IF NOT EXISTS tables(
    table_id INTEGER PRIMARY KEY,
    player_white INTEGER,
    player_black INTEGER,
    winner INTEGER,
    uses_mosquito INTEGER,
    uses_ladybug INTEGER,
    uses_pillbug INTEGER,
    FOREIGN KEY(player_white) REFERENCES players(player_id),
    FOREIGN KEY(player_black) REFERENCES players(player_id)
);
CREATE TABLE IF NOT EXISTS game_strings(
    table_id INTEGER,
    string TEXT,
    FOREIGN KEY(table_id) REFERENCES tables(table_id)
);
COMMIT;
'''


def init():
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                cur.executescript(DB_SCHEMA)
    except Exception as e:
        print('ERROR: init() failed: ', e)
        exit(-1)


def searched_player(player_id):
    ''' Updates players table with new timestamp to increase scraping efficieny
    '''
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                now = int(time.time())
                cur.execute('INSERT OR IGNORE INTO players(player_id, last_search_timestamp) VALUES(?,?)', [player_id, now])
                cur.execute('UPDATE players SET last_search_timestamp = ? WHERE player_id = ?', [now, player_id])
                con.commit()

    except Exception as e:
        print(f'ERROR inserting player_id {player_id}: ', e)


def insert_table_data(table_id, player_white, player_black, winner, m, l, p, actions):
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                # create or update tables table
                cur.execute(
                    '''
                    INSERT OR REPLACE INTO tables(table_id, player_white, player_black,
                    winner, uses_mosquito, uses_ladybug, uses_pillbug) VALUES(?,?,?,?,?,?,?)
                    ''', 
                    [table_id, player_white, player_black, winner, m, l, p]
                )

                # convert actions into tuples for insert
                convert = lambda action, table_id=table_id: (
                    action.get('move_number', -1),
                    action.get('notation', ''),
                    table_id,
                    action.get('type', ''),
                    action.get('type_copied', ''),
                    action.get('log', '')
                )
                actions_params = list(map(convert, actions))

                # bulk add/update actions
                cur.executemany(
                    '''
                    INSERT OR REPLACE INTO actions
                    (move_number, notation, table_id, type, type_copied, log)
                    VALUES(?,?,?,?,?,?)
                    ''',
                    actions_params
                )

                con.commit()

    except Exception as e:
        print(f'ERROR inserting table_id {table_id}: ', e)


def update_table_expansions(table_id, m, l, p):
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                cur.execute(
                    '''
                    UPDATE tables SET uses_mosquito = ?, uses_ladybug = ?, uses_pillbug = ?
                    WHERE table_id = ?
                    ''',
                    [m, l, p, table_id]
                )
                con.commit()

    except Exception as e:
        print(f'ERROR updating expansions: ', e)


def get_all_table_data(include_bots = False, uses_m = True, uses_l = True, uses_p = True, include_bga = True, include_bs = True):
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                params = [uses_m, uses_l, uses_p]
                query = '''
                        SELECT * FROM tables WHERE
                        (uses_mosquito = ? AND uses_ladybug = ? AND uses_pillbug = ?)
                        '''
                if not include_bs:
                    params += [BGA_START, BGA_END]
                    query += '''
                             AND
                             (table_id >= ? AND table_id <= ?)
                             '''
                elif not include_bga:
                    params += [BGA_START, BGA_END]
                    query += '''
                             AND
                             (table_id < ? OR table_id > ?)
                             '''

                if not include_bots:
                    params += BOT_NAMES + BOT_NAMES
                    query += '''
                            AND
                            (player_white != ? AND player_white != ? AND player_white != ?)
                            AND
                            (player_black != ? AND player_black != ? AND player_black != ?)
                            '''
                cur.execute(query, params)

                return cur.fetchall()

    except Exception as e:
        print(f'ERROR retrieving from tables: ', e)


def get_unique_table_ids():
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                cur.execute('SELECT DISTINCT table_id FROM tables')

                return set(map(lambda val: val[0], cur.fetchall()))

    except Exception as e:
        print(f'ERROR retrieving unique table_ids: ', e)


def get_moves_list(table_id) -> list[tuple[int,str,int,str,str,str]]:
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                cur.execute('''
                            SELECT * FROM actions WHERE table_id = ?
                            ORDER BY move_number ASC, notation DESC
                            ''',
                            [table_id])

                return cur.fetchall()

    except Exception as e:
        print(f'ERROR retrieving moves list for table_id {table_id}: ', e)


init()

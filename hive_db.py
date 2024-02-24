import sqlite3
import time
from contextlib import closing

DB_NAME = 'hivemind.db'
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
    FOREIGN KEY(player_white) REFERENCES players(player_id),
    FOREIGN KEY(player_black) REFERENCES players(player_id)
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
                cur.execute('INSERT OR IGNORE INTO players(player_id, last_search_timestamp) VALUES(?,?)', (player_id, now))
                cur.execute('UPDATE players SET last_search_timestamp = ? WHERE player_id = ?', (now, player_id))
                con.commit()

    except Exception as e:
        print(f'ERROR inserting player_id {player_id}: ', e)


def insert_table_data(table_id, player_white, player_black, winner, actions, commit=True):
    try:
        with closing(sqlite3.connect(DB_NAME)) as con:
            with closing(con.cursor()) as cur:
                # first create or update players
                now = int(time.time())
                cur.execute('INSERT OR REPLACE INTO players(player_id, last_search_timestamp) VALUES(?,?)', (player_white, now))
                cur.execute('INSERT OR REPLACE INTO players(player_id, last_search_timestamp) VALUES(?,?)', (player_black, now))

                # create or update tables table
                cur.execute(
                    'INSERT OR REPLACE INTO tables(table_id, player_white, player_black, winner) VALUES(?,?,?,?)', 
                    (table_id, player_white, player_black, winner)
                )
                '''
                cur.execute(
                    'UPDATE tables SET player_white = ?, player_black = ?, winner = ? WHERE table_id = ?', 
                    (player_white, player_black, winner, table_id)
                )
                '''

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
                    'INSERT OR REPLACE INTO actions(move_number, notation, table_id, type, type_copied, log) VALUES(?,?,?,?,?,?)',
                    actions_params
                )

                con.commit()

    except Exception as e:
        print(f'ERROR inserting table_id {table_id}: ', e)


init()

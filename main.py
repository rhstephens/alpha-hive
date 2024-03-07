import scripts.bga_scraping as bga_scraping
import db.hive_db as hive_db


# if ran as script, automatically begin scraping
if __name__ == '__main__':
    sess = bga_scraping.get_next_session()

    player_ids = bga_scraping.get_players_by_rank(sess, 10)
    print(f'found the top {len(player_ids)} ranking player IDs')

    for player in player_ids:
        bga_scraping.hive_db.searched_player(player)

    table_ids = list(bga_scraping.get_top_arena_tables(sess, player_ids))
    print(f'proccessing {len(table_ids)} table IDs:')

    index = 0
    session_count = 0
    while sess and index < len(table_ids):
        table_id = table_ids[index]
        result = bga_scraping.analyze_table_data(sess, table_id)

        if not result:
            # try to get new acct
            # if result fails again, its all ogre
            print(f'session expired or account depleted... added {index - session_count} table_ids with {sess.email}, attempting next account')
            session_count = index
            sess = bga_scraping.get_next_session()
            if not sess:
                break
            continue

        if result == table_id: # this table should be ignored for whichever reason (missing replay, corrupted, etc.)
            index += 1
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
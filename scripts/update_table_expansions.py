import db.hive_db as hive_db
import scripts.bga_scraping as bga_scraping
import scripts.entomology_scraping as ent_scraping
import json
import time
import zlib
from ctypes import c_uint32
from requests import Session

from requests import JSONDecodeError
from requests.exceptions import RequestException, HTTPError
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def insert_new_table(driver, sess, uuid, i):
    try:
        results = ent_scraping.analyze_table_data(driver, sess, uuid, 'lmp', ranked=True, tournament=False)
        if results:
            hive_db.insert_table_data(i, *results)
            print(f'Inserted table_id: {i}, num_moves: {len(results[-1])}')

    except JSONDecodeError as e:
        print(f'Exception raised for uuid {uuid}: ' + str(e))

    except HTTPError as e:
        print('HTTPError: ' + str(e))
    
    except WebDriverException as e:
        print(e)
        print('Attempting to establish new connection in 1 minute...')
        time.sleep(60)

        if driver:
            driver.quit()

        driver = ent_scraping.new_webdriver()

    except RequestException as e:
        print(e)
        print('Attempting to establish new connection in 1 minute...')
        time.sleep(60)
        sess = Session()


def update_entomology_table(sess, table_id):
    pass


# update tables with their correct expansion booleans
if __name__ == "__main__":
    table_ids = hive_db.get_unique_table_ids()
    bga_sess = bga_scraping.get_next_session()
    ent_sess = Session()
    ent_driver = ent_scraping.new_webdriver()

    uuid_list = []
    index = 235037
    with open('entomology_uuids.json', 'r') as f:
        uuid_list = json.load(f)
    list_size = len(uuid_list)

    print(f'{list_size} entomology games to go through')
    while index < list_size:
        if index % 100 == 0:
            print(f'AT INDEX {index}')
       # uuid_hash = c_uint32(zlib.adler32(bytes(uuid_list[index], 'utf-8'))).value
        #if uuid_hash in table_ids:
            #table_id = uuid_hash
        if index not in table_ids:
            #insert_new_table(ent_driver, ent_sess, uuid_list[index], index)
            index += 1
            continue
        else:
            table_id = index

        resp = ent_sess.get(ent_scraping.BASE + ent_scraping.construct_xhr(uuid_list[index]))
        j = resp.json()
        if j:
            m = 'm' in j['variant']
            l = 'l' in j['variant']
            p = 'p' in j['variant']
        else:
            print(f'skipping uuid {uuid_list[index]}')
            index += 1
            continue

        print(f'table: {table_id}  m,l,p: {m},{l},{p}')
        hive_db.update_table_expansions(table_id,
                                  1 if m else 0,
                                  1 if l else 0,
                                  1 if p else 0)
        
        index += 1

    print(f'Updating {len(table_ids)} table_ids')
    for id in table_ids:
        if id >= hive_db.BGA_START and id <= hive_db.BGA_END:
            while bga_sess:
                try:
                    m, l, p = bga_scraping.get_expansion_info(bga_sess, id)
                    print(f'table: {id}  m,l,p: {m},{l},{p}')
                    hive_db.update_table_expansions(id,
                                              1 if m else 0,
                                              1 if l else 0,
                                              1 if p else 0)
                    break

                except:
                    bga_sess = bga_scraping.get_next_session()








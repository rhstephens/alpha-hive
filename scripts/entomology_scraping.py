import json
import signal
import sys
import time

from ctypes import c_uint32
from bs4 import BeautifulSoup
from requests import Session, JSONDecodeError
from requests.exceptions import RequestException, HTTPError
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import db.hive_db as hive_db


BASE = 'https://entomology.gitlab.io/'
BOARD = 'hive.html'

index = 0


def finish(sig, frame):
    with open('entomology_uuids.txt', 'w') as f:
        if index != 0:
            f.write(str(index + 1))
    print(f'FINISHED! Last index reached: {index}', flush=True)
    if sig or frame:
        sys.exit(0)


def new_webdriver():
    chrome_options = Options().add_argument("--headless")
    service = Service('/home/rhstephens/code/hivemind/chromedriver_linux64/chromedriver')
    
    return webdriver.Chrome(service=service, options=chrome_options)


def construct_xhr(uuid):
    # split the uuid into three parts
    parts = [uuid[0], uuid[1], uuid[2:]]

    # encode the first character using its Unicode code point in hexadecimal IFF
    # the first char is not a digit or lowercase letter
    if not (parts[0].isdigit() or parts[0].islower()):
        parts[0] = "x" + hex(ord(uuid[0]))[2:]

    # join the parts to construct the URL
    return "/".join(parts)


def analyze_table_data(driver: webdriver.Chrome, sess: Session,
                      uuid, variant='lmp', ranked=True, tournament=False):
    # first, check if the game's json data matches the given requirements
    resp = sess.get(BASE + construct_xhr(uuid))
    resp.raise_for_status()
    j = resp.json()

    if j:
        if variant and ('variant' not in j or j['variant'] != variant):
            print(f'Skipping table {uuid}, incorrect variant: {j["variant"] if "variant" in j else ""}')
            return

        if ranked and ('ranked' not in j or j['ranked'] != 1):
            print(f'Skipping table {uuid}, not a ranked game')
            return

        if tournament and ('tournament' not in j or j['tournament'] != 1):
            print(f'Skipping table {uuid}, not a tournament game')
            return
    else:
        print(f'Invalid response for table: {uuid}, {resp.status_code}, {j}')
        return
    
    # game metadata
    winner = j['result'] if 'result' in j else ''
    white = j['white']['name'] if 'white' in j and 'name' in j['white'] else ''
    black = j['black']['name'] if 'black' in j and 'name' in j['black'] else ''
    uses_mosquito = variant and 'm' in j['variant']
    uses_ladybug = variant and 'l' in j['variant']
    uses_pillbug = variant and 'p' in j['variant']

    # now load the game's processed movelist from the raw html response
    url = BASE + BOARD + "?game=" + uuid
    driver.get(url)
    
    # wait for the page to load
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "moves")))
    WebDriverWait(driver, 10).until(lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "#moves li")) > 0)
    
    # parse the HTML content using BeautifulSoup
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # extract moves and put into action list for DB insertion
    action_list = []
    div = soup.find('div', id='moves')
    if div:
        for num, li in enumerate(div.find_all('li')):
            action_list.append({'notation': li.text.replace(' .', '').replace('..., ', '').strip(),
                                'move_number': num + 1})
    else:
        print(f'Error finding moves list for: {uuid}')
        return None
    
    return (white, black, winner, uses_mosquito, uses_ladybug, uses_pillbug, action_list)


if __name__ == '__main__':
    # CTRL-C catcher
    signal.signal(signal.SIGINT, finish)

    # setup selenium chrome driver and a requests Session
    driver = new_webdriver()
    sess = Session()

    uuid_list = []
    with open('entomology_uuids.json', 'r') as f:
        uuid_list = json.load(f)

    list_size = len(uuid_list)
    try:
        with open('entomology_uuids.txt', 'r') as f:
            index = int(f.read())
    except:
        index = 0

    # TODO PUT BACK
    # exclusion_set = hive_db.get_unique_table_ids()
    exclusion_set = set()  
    print(f'Excluding {len(exclusion_set)} IDs already in the database')

    while index < list_size:
        try:
            print(f'Processing {list_size} uuids starting at index {index}')
            for i in range(index, list_size):
                index = i

                # simply using the index as the unique primary key in the database
                # as this provides a perfect hash/mapping for all ~750,000 uuid's
                uuid_key = c_uint32(i).value
                if uuid_key in exclusion_set:
                    print(f'Skipping table_id {uuid_key}, already in Database')
                    continue

                results = analyze_table_data(driver, sess, uuid_list[i], 'lmp', ranked=True, tournament=False)
                if results:
                    hive_db.insert_table_data(uuid_key, *results)
                    exclusion_set.add(uuid_key)
                    print(f'Inserted table_id: {uuid_key}, num_moves: {len(results[-1])}')

        except JSONDecodeError as e:
            print(f'Exception raised for uuid {uuid_list[i]}: ' + str(e))
            time.sleep(1)

            # skip over this uuid
            index += 1
            continue

        except HTTPError as e:
            print('HTTPError: ' + str(e))
            time.sleep(1)

            # skip over this uuid
            index += 1
            continue
        
        except WebDriverException as e:
            # write current progress to disk and attempt to create a new connection
            print(e)
            print('Attempting to establish new connection in 1 minute...')
            finish(None, None)
            time.sleep(60)

            if driver:
                driver.quit()

            driver = new_webdriver()
            continue

        except RequestException as e:
            print(e)
            print('Attempting to establish new connection in 1 minute...')
            finish(None, None)
            time.sleep(60)

            sess = Session()
            continue


    finish(None, None)

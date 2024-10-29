from datetime import datetime
from db import hive_db

import argparse
import sys

# parser = argparse.ArgumentParser()

# parser.add_argument('args', nargs='*', help='Arguments to process')
# parser.add_argument('-v', '--verbose', action=argparse.BooleanOptionalAction, default=False, type=bool)
# args = parser.parse_args()
# print('Arguments:', args.args)


# UHP strings for final output
UHP_BASE_GAME = 'Base'
UHP_WHITE_WINS = 'WhiteWins'
UHP_BLACK_WINS = 'BlackWins'
UHP_DRAW = 'Draw'
UHP_PASS_MOVE = 'pass'

# expected string formats from BoardSpace games
BS_WHITE_WINS = 'white wins'
BS_BLACK_WINS = 'black wins'
BS_DRAW = 'draw'
BS_OFFER_DRAW = 'offer-draw'
BS_ACCEPT_DRAW = 'accept-draw'
BS_DECLINE_DRAW = 'decline-draw'
BS_RESIGN = 'resign'

# expected string formats from BoardGameArena games
BGA_DEFAULT_MOVE = 'tokenPlayed'
BGA_PASS = 'message'
BGA_OFFER_DRAW = 'offerDraw'
BGA_ACCEPT_DRAW = 'acceptDraw'
BGA_VICTORY = 'queenSurr'

FOLDER_PATH = './game_strings/'

# create UHP-compliant game strings out of tables db
# https://github.com/jonthysell/Mzinga/wiki/UniversalHiveProtocol#gamestring
if __name__ == "__main__":
    # TODO use argparse
    file_path = f'GameStrings_{"Base+MLP"}{"+NoBots" if 1 else "+Bots"}_{datetime.strftime(datetime.now(), "%Y%m%d_%H%M%S")}.txt'
    with open(FOLDER_PATH + file_path, 'x') as f:

        tables = hive_db.get_all_table_data(include_bots=False, uses_m=True, uses_l=True, uses_p=True, include_bga=True, include_bs=False)
        print(f'Creating {len(tables)} game strings:')

        count = 0
        for id, white, black, winner, m, l, p in tables:
            # generate GameTypeString from expansions
            game_type_string = UHP_BASE_GAME
            if m or l or p:
                game_type_string += '+'
            if m:
                game_type_string += 'M'
            if l:
                game_type_string += 'L'
            if p:
                game_type_string += 'P'

            # generate GameStateString from the winner
            state_string = ''
            if isinstance(winner, str): # BoardSpace uses a string for the winner
                if winner == BS_WHITE_WINS:
                    state_string = UHP_WHITE_WINS
                elif winner == BS_BLACK_WINS:
                    state_string = UHP_BLACK_WINS
                elif winner == BS_DRAW:
                    state_string = UHP_DRAW
            elif isinstance(winner, int): # BoardGameArena uses an ID for a winner
                if winner == 0:
                    # this means the game ended in a mutually agreed draw
                    state_string = UHP_DRAW
                elif winner == 1:
                    # an actual draw via double queen surrender
                    state_string = UHP_DRAW
                elif winner == white:
                    state_string = UHP_WHITE_WINS
                elif winner == black:
                    state_string = UHP_BLACK_WINS
                else:
                    print(f"Can't find a winner from ({winner}) for table: {id}", file=sys.stderr)
                    continue

            # generate MoveStrings
            moves_to_join = []
            moves = hive_db.get_moves_list(id)
            if not moves:
                print(f"No actions found for table: {id}", file=sys.stderr)
                continue

            for i, move in enumerate(moves):
                move_num, notation, table_id, move_type, type_copied, _ = move                

                if not notation:
                    if move_type == BGA_ACCEPT_DRAW:
                        state_string = UHP_DRAW
                    elif move_type == BGA_PASS:
                        moves_to_join.append(UHP_PASS_MOVE)
                    elif move_type == BGA_OFFER_DRAW or move_type == BGA_VICTORY:
                        pass
                    elif move_type == BGA_DEFAULT_MOVE:
                        print(f'Expected move notation for move {move_num} at table {table_id}', file=sys.stderr)
                    else:
                        print(f'Unknown move {move_num} for table {table_id}', file=sys.stderr)
                elif notation == BS_ACCEPT_DRAW:
                    state_string = UHP_DRAW
                elif notation in [BS_OFFER_DRAW, BS_DECLINE_DRAW, BS_RESIGN]:
                    pass
                else:
                    moves_to_join.append(notation.strip('[]').strip())

            moves_string = ';'.join(moves_to_join)

            # ensure we have a finished game state after going through moves list
            if not state_string:
                print(f"Can't find a winner from ({winner}) for table: {id}", file=sys.stderr)
                continue

            # generate TurnString from moves
            num_moves = len(moves_to_join)
            turn_num = (num_moves // 2) + 1
            turn_string = 'White' if num_moves % 2 == 0 else 'Black'
            turn_string = f'{turn_string}[{turn_num}]'

            # join all parts and save to disk
            f.write(';'.join([game_type_string, state_string, turn_string, moves_string]) + '\n')
            print(f'[{count}] Successfully added game string for table {id}')
            count += 1

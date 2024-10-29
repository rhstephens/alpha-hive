#!/bin/bash

script_dir=$(dirname "$(readlink -f "$0")")
cd $script_dir


python3 -u "scripts/generate_game_strings.py" "$@" | tee -a "generate_game_strings.log"


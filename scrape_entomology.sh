#!/bin/bash

script_dir=$(dirname "$(readlink -f "$0")")
cd $script_dir

python3 -u "scripts/entomology_scraping.py" | tee -a "scrape_entomology.log"

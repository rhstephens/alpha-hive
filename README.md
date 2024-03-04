# hivemind 
A collection of tools to gather and preprocess data for Deep Learning AI purposes in the boardgame ['Hive'](https://boardgamegeek.com/boardgame/2655/hive).

## Running locally

To start gathering replay data from BoardGameArena, you will need a list of valid account(s) in a file named `accounts.py` in the root directory. It should contain a list of `(email, password)` tuples:

```
ACCOUNTS=[(email1@gmail.com, password1), (email2@gmail.com, password2)]
```

There will be a limit to how much replay data you can retrieve per account. This typically resets 24 hours after reaching the limit.

### Manual
Simply run `python main.py`. This will retrieve tables from the top 10 ranked players by default. See `main.py` for more args (**TBD**).


### Crontab
Due to the daily limit on replay data, you may want to setup a cron job to periodically scrape data. The provided `scrape.sh` can be run hourly on cron, and will begin scraping once 24.5 hours has elapsed since the last successful attempt (an extra 30min buffer is needed due to variance in run time and BGA's replay limit). Add this to your /etc/crontab file:

```
0 * * * *  root    /PATH/TO/REPO/scrape.sh >> /PATH/TO/REPO/scrape.log
```


#### Credits
Thanks to [iamdj/tokaido-analysis](https://github.com/liamdj/tokaido-analysis) for providing a starting point used to scrape BoardGameArena replay data!


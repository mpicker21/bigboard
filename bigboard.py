import re, threading, subprocess, json, nflgame
from urllib2 import urlopen
from datetime import date, timedelta
from operator import itemgetter

# This section declares strings, locks, etc.
date = date.today()
dwell_time = 5
refresh_rate = 60
sport = "nhl"
dedicated_mode = False
currentgame = 0
scoredata = []
last_score = ""
nfl_season = ""
nfl_time = ""
nfl_weeks = ""
scoreslock = threading.Lock()
source_trigger = threading.Event()
display_trigger = threading.Event()
source_ready = threading.Event()
disp_ready = threading.Event()

# This section defines functions
#   Hardware functions
#   Source functions
def build_nfl_times():                                                    # Build table of PRE/REG/POST and weeks in each to make it easier to reference with nfl_time
  a = []
  for x in range(0, 4 + 1):
    a.append([x, 'PRE'])
  for x in range(1, 17 + 1):
    a.append([x, 'REG'])
  for x in range(1, 4 + 1):
    a.append([x, 'POST'])
  return a

def set_nfl_current():                                                    # Sets the current nfl_season and returns the current nfl_time
  global nfl_season
  cyad = nflgame.live.current_year_and_week()
  nfl_season = cyad[0]
  return nfl_weeks.index([cyad[1], nflgame.live._cur_season_phase])

def get_nhl_scores(date):                                                 # Pulls json files from NHL, parses them, and fills scoredata with data
  global scoredata
  scores = []
  url = "http://live.nhle.com/GameData/GCScoreboard/" + date.strftime('%Y-%m-%d') + ".jsonp"
  raw = urlopen(url).read()
  raw = re.sub("loadScoreboard\(", "", raw)
  raw = re.sub("\)\\n", "", raw)
  games = json.loads(raw)['games']
  for game in games:
    awayteam = game['ata']
    hometeam = game['hta']
    awayscore = str(game['ats'])
    homescore = str(game['hts'])
    if game['gs'] == 1:
      time = re.search(r'(\d*:\d\d)', game['bs']).group(1)
      period = ""
    elif game['gs'] == 2:
      time = ""
      period = "P"
    elif game['gs'] == 3:
      try:
        time = re.search(r'(\d*:\d\d)', game['bs']).group(1)
      except:
        time = "00:00"
      period = re.search(r'\s(\d)', game['bs']).group(1)
    elif game['gs'] == 5:
      time = ""
      period = "F"
    gameid = game['id']
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nba_scores(date):                                                 # Pulls json files fron NBA, parses them, and fills scoredata with data
  global scoredata
  scores = []
  url = "http://data.nba.com/5s/json/cms/noseason/scoreboard/" + date.strftime('%Y%m%d') + "/games.json"
  raw = urlopen(url).read()
  games = json.loads(raw)['sports_content']['games']['game']
  for game in games:
    awayteam = game['visitor']['team_key']
    hometeam = game['home']['team_key']
    awayscore = game['visitor']['score']
    homescore = game['home']['score']
    if game['period_time']['game_status'] == "1":
      time = re.search(r'(\d*:\d\d)', game['period_time']['period_status']).group(1)
      period = ""
    elif game['period_time']['game_status'] == "2":
      time = game['period_time']['game_clock']
      period = game['period_time']['period_value']
    elif game['period_time']['game_status'] == "3":
      time = ""
      period = "F"
    gameid = game['id']
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nfl_scores(nfl_time):                                             # Uses nflgame to fill scoredata with data
  global scoredata
  scores = []
  this_week = []
  sched = nflgame.sched.games
##  populate this_week with a template for this week
  for key in sched:
    if sched[key]['year'] == nfl_season:
      if sched[key]['season_type'] == nfl_weeks[nfl_time][1]:
        if sched[key]['week'] == nfl_weeks[nfl_time][0]:
          awayteam = sched[key]['away']
          hometeam = sched[key]['home']
          awayscore = ""
          homescore = ""
          time = sched[key]['time']
          period = ""
          gameid = sched[key]['gamekey']
          this_week.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  games = nflgame.games(nfl_season, week=nfl_weeks[nfl_time][0], kind=nfl_weeks[nfl_time][1])
##  run through this_week and fill in scores for finished/ongoing games
  for game in this_week:
    for g in games:
      if g.gamekey == game['gameid']:
        if g.time.is_pregame():
          pass
        elif g.time.is_final():
          game['awayscore'] = g.score_away
          game['homescore'] = g.score_home
          game['time'] = ""
          game['period'] = "F"
        else:
          game['awayscore'] = g.score_away
          game['homescore'] = g.score_home
          game['time'] = g.time.clock
          game['period'] = g.time.qtr
  this_week = sorted(this_week, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = this_week
  return

def update_scores():                                                      # Runs the appropriate score source to update scores
  global sport
  if sport == "nhl":
    get_nhl_scores(date)
  elif sport == "nba":
    get_nba_scores(date)
  elif sport == "nfl":
    get_nfl_scores(nfl_time)

#   Other functions
def dedicated_compare(last):
  with scoreslock:
    if last['gameid'] != scoredata[currentgame]['gameid']:
      pass
    if last == scoredata[currentgame]:
      pass
    elif last['homescore'] != scoredata[currentgame]['homescore']:
      print "Home team scored!"
    elif last['awayscore'] != scoredata[currentgame]['awayscore']:
      print "Away team scored!"
    elif last['period'] == "":
      pass
    elif last['time'] != scoredata[currentgame]['time']:
      if scoredata[currentgame]['time'] == "00:00" or "":
        print "End of period!"
      elif last['period'] != scoredata[currentgame]['period']:
        if last['time'] != "00:00" or "":
          print "End of period!"
      else:
        pass

def test_display():                                                       # Simple terminal output for debugging
  global scoredata, currentgame, last_score
  from time import sleep
  source_ready.wait()
  while True:
    while not display_trigger.is_set():
      if not dedicated_mode:
        currentgame += 1
        if currentgame > (len(scoredata) - 1):
          currentgame = 0
      with scoreslock:
        print "Game: %s" % (scoredata[currentgame]['gameid'])
        print "Time: %s  Period: %s" % (scoredata[currentgame]['time'], scoredata[currentgame]['period'])
        print "Away: %s    %s" % (scoredata[currentgame]['awayteam'], scoredata[currentgame]['awayscore'])
        print "Home: %s    %s" % (scoredata[currentgame]['hometeam'], scoredata[currentgame]['homescore'])
        print ""
      if dedicated_mode:
        dedicated_compare(last_score)
        last_score = scoredata[currentgame]
        display_trigger.wait(10)
      else:
        display_trigger.wait(dwell_time)
    display_trigger.clear()

#   Daemon functions
def source_daemon():                                                      # A looping function that updates scores at refresh_rate interval unless source_trigger is set
  print "source_daemon is running"
  while True:
    while not source_trigger.is_set():
      print "updating scores"
      update_scores()
      source_ready.set()
      if dedicated_mode:
        source_trigger.wait(10)
      else:
        source_trigger.wait(refresh_rate)
    source_trigger.clear()

def main():                                                               # The main function that gets everything running
  global nfl_time, nfl_weeks
  nfl_weeks = build_nfl_times()
  nfl_time = set_nfl_current()
  source = threading.Thread(target=source_daemon)
  source.daemon = True
  source.start()
  test_display()

main()

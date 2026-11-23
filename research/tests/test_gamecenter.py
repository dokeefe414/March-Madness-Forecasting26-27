"""Hermetic scheduled Game Center, prior-opponent evidence and unknown-team safety."""
import unittest
from datetime import datetime,timezone
from forecast.gamecenter import build_game_center

NOW=datetime(2026,11,20,12,tzinfo=timezone.utc)
RATINGS={"season":2027,"mode":"current","retrievedAtUtc":"2026-11-20T11:50:00Z",
 "lastGameDate":"2026-11-19","regularSeasonGames":3,
 "teams":[
  {"name":"Duke","teamId":"ncaa-duke","espnSourceTeamId":"150",
   "rating":1555.,"projectedRating":1560.,"trend":5.,"wins":2,"losses":0,
   "history":[1500.,1530.,1555.],"opponentAverageElo":1512.},
  {"name":"UNC","teamId":"ncaa-unc","espnSourceTeamId":"153",
   "rating":1500.,"projectedRating":1504.,"trend":4.,"wins":0,"losses":1,
   "history":[1500.,1500.],"opponentAverageElo":1510.}
 ]}
GAMES=[
 {"id":"1","date":"2026-11-17","home":"Duke","away":"Wake","homeScore":81,"awayScore":70},
 {"id":"2","date":"2026-11-18","home":"Wake","away":"UNC","homeScore":70,"awayScore":62},
 {"id":"3","date":"2026-11-19","home":"Duke","away":"State","homeScore":92,"awayScore":75}]
def event(id,home,away,home_id,away_id,date="2026-11-21T00:00:00Z"):
 return {"id":id,"date":date,"status":{"type":{"name":"STATUS_SCHEDULED","completed":False}},
  "competitions":[{"neutralSite":False,"competitors":[
    {"homeAway":"home","team":{"id":home_id,"location":home}},
    {"homeAway":"away","team":{"id":away_id,"location":away}}]}]}
class GameCenterTests(unittest.TestCase):
 def test_real_fixture_has_probability_and_sources_for_explanation(self):
  # ESPN names deliberately disagree; season-linked IDs prove identity.
  board={"events":[event("fixture","Blue Devils","Tar Heels","150","153")]}
  output=build_game_center([board],RATINGS,GAMES,NOW)
  self.assertEqual(output["coverage"]["eligibleForecasts"],1)
  one=output["games"][0]
  self.assertEqual(one["home"],"Duke")
  self.assertEqual(one["away"],"UNC")
  self.assertGreater(one["homeWinProbability"],.5)
  self.assertEqual(one["homeProfile"]["recentGames"][0]["opponent"],"State")
  self.assertEqual(one["awayProfile"]["recentGames"][0]["opponent"],"Wake")
  self.assertEqual(one["commonOpponents"][0]["opponent"],"Wake")
  self.assertEqual(len(one["factors"]),4)
 def test_same_day_source_has_stable_safe_forecast_and_profile(self):
  from forecast.live import build_current
  source=[{"id":"1","date":"2026-11-19","home":"Duke","away":"UNC",
           "homeScore":74,"awayScore":63},
          {"id":"2","date":"2026-11-20","home":"UNC","away":"Duke",
           "homeScore":88,"awayScore":61}]
  data=build_current(source,NOW)
  data["retrievedAtUtc"]="2026-11-20T11:50:00Z"
  for t in data["teams"]:
   t["espnSourceTeamId"]="150" if t["name"]=="Duke" else "153"
  board={"events":[event("afternoon","Duke","UNC","150","153",
                         date="2026-11-20T22:00:00Z")]}
  report=build_game_center([board],data,source,NOW)
  self.assertEqual(report["coverage"]["eligibleForecasts"],1)
  item=report["games"][0]
  self.assertEqual(item["status"],"ready")
  self.assertEqual(item["ratingReplayMode"],"prior-date-safe")
  self.assertEqual(item["homeProfile"]["wins"],1)
  self.assertEqual(item["homeProfile"]["losses"],0)
  self.assertEqual(item["awayProfile"]["wins"],0)
  self.assertEqual(item["awayProfile"]["losses"],1)
 def test_unknown_program_has_no_invented_probability(self):
  board={"events":[event("fixture","Unknown","Duke","999","150")]}
  output=build_game_center([board],RATINGS,GAMES,NOW)
  self.assertEqual(output["games"][0]["status"],"unmatched")
  self.assertIsNone(output["games"][0]["homeWinProbability"])
 def test_old_or_not_scheduled_not_a_pick(self):
  past=event("old","Duke","UNC","150","153",date="2026-11-20T11:00:00Z")
  output=build_game_center([{"events":[past]}],RATINGS,GAMES,NOW)
  self.assertFalse(output["games"])

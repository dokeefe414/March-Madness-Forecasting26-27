"""Prospective Elo 3.0: real pretipoff as-of embargo and immutable paired first picks."""
import copy
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from forecast.elo_v3_shadow import Elo3Pregame, MODEL_VERSION
from forecast.snapshot import forecast_scheduled, write_ledger
from forecast.accuracy_research import derive
from forecast.audit import audit_ledger

NOW=datetime(2026,11,16,14,tzinfo=timezone.utc)
STAMP="2026-11-16T13:00:00Z"


def current():
    rows=[]
    boxes=[]
    for day,h,a in ((12,80,70),(13,68,75),(14,90,75),(15,70,80)):
        date=f"2026-11-{day:02d}"
        gid=f"contest-{day}"
        rows.append({"id":gid,"date":date,"home":"Duke","away":"North Carolina",
                     "homeScore":h,"awayScore":a})
        homebox={"poss":70.,"off":h/70*100,"def":a/70*100,"factors":None}
        awaybox={"poss":70.,"off":a/70*100,"def":h/70*100,"factors":None}
        boxes.append({"id":gid,"date":date,"home":"Duke","away":"North Carolina",
                      "homeBox":homebox,"awayBox":awaybox})
    ratings={"season":2027,"mode":"current","retrievedAtUtc":STAMP,
             "lastGameDate":"2026-11-15","regularSeasonGames":len(rows),
             "teams":[{"name":"Duke","teamId":"ncaa-duke","rating":1560.},
                      {"name":"North Carolina","teamId":"ncaa-unc","rating":1530.}]}
    games={"season":2027,"retrievedAtUtc":STAMP,"games":rows}
    boxdoc={"season":2027,"retrievedAtUtc":STAMP,"status":"matched","games":boxes}
    return ratings,games,boxdoc


def schedule(starts="2026-11-17T01:00:00Z"):
    return [{"events":[{"id":"espn-1","date":starts,
       "status":{"type":{"name":"STATUS_SCHEDULED","completed":False}},
       "competitions":[{"neutralSite":False,"competitors":[
         {"homeAway":"home","team":{"id":"9","location":"Duke","displayName":"Duke Blue Devils"}},
         {"homeAway":"away","team":{"id":"8","location":"North Carolina","displayName":"North Carolina Tar Heels"}}
       ]}]}]}]


class Elo3ProspectiveTests(unittest.TestCase):
    def test_freezes_original_probability_with_previous_date_only(self):
        ratings,games,boxes=current()
        shadow=Elo3Pregame(ratings,games,boxes)
        frozen=forecast_scheduled(schedule(),ratings,NOW,elo3_shadow=shadow)
        self.assertEqual(len(frozen["predictions"]),1)
        p=frozen["predictions"][0]
        self.assertEqual(p["elo3Research"]["modelVersion"],MODEL_VERSION)
        self.assertEqual(p["elo3Research"]["ratingCutoffExclusive"],"2026-11-16")
        self.assertEqual(p["elo3Research"]["trainedThroughDate"],"2026-11-15")
        self.assertEqual(p["elo3Research"]["pairedBoxGames"],4)
        self.assertEqual(p["elo3Research"]["fourFactorTeamGames"],0)
        self.assertTrue(0<p["elo3HomeWinProbability"]<1)
        self.assertNotEqual(p["homeWinProbability"],p["elo3HomeWinProbability"])
        self.assertFalse(p["model"].startswith("Elo3"))

    def test_same_date_new_final_and_boxes_cannot_change_early_forecast(self):
        ratings,games,boxes=current()
        first=Elo3Pregame(ratings,games,boxes).predict("Duke","North Carolina",
                                            "2026-11-16",False)
        # Another Nov 16 result may exist in a later source capture; the
        # forecast is date-frozen even when source IDs and box scores change.
        day={"id":"contest-16","date":"2026-11-16","home":"Duke",
             "away":"North Carolina","homeScore":50,"awayScore":90}
        more_games={**games,"games":[*games["games"],day]}
        more_ratings={**ratings,"regularSeasonGames":5,"lastGameDate":"2026-11-16"}
        side={"poss":70.,"off":50/70*100,"def":90/70*100,"factors":None}
        other={"poss":70.,"off":90/70*100,"def":50/70*100,"factors":None}
        more_boxes={**boxes,"games":[*boxes["games"],{
           "id":"contest-16","date":"2026-11-16","home":"Duke","away":"North Carolina",
           "homeBox":side,"awayBox":other}]}
        second=Elo3Pregame(more_ratings,more_games,more_boxes).predict(
            "Duke","North Carolina","2026-11-16",False)
        self.assertEqual(first,second)

    def test_unplayed_teams_have_neutral_priors_and_home_edge(self):
        ratings,games,boxes=current()
        ratings["teams"] += [{"name":"Arizona","teamId":"ncaa-arizona","rating":1500.}]
        # A genuinely unmatched opponent identity must not be guessed from
        # similar school names in ESPN.
        with self.assertRaisesRegex(ValueError,"coverage"):
            Elo3Pregame(ratings,games,boxes)
        cold_ratings={"season":2027,"mode":"current","retrievedAtUtc":STAMP,
            "lastGameDate":None,"regularSeasonGames":0,
            "teams":[]}
        cold_games={"season":2027,"retrievedAtUtc":STAMP,"games":[]}
        cold_boxes={"season":2027,"retrievedAtUtc":STAMP,"status":"unavailable","games":[]}
        cold=Elo3Pregame(cold_ratings,cold_games,cold_boxes)
        with self.assertRaisesRegex(ValueError,"identity"):
            cold.predict("Arizona","Duke","2026-11-16",False)

    def test_rejects_wrong_source_stamp_and_unverified_box_pair(self):
        ratings,games,boxes=current()
        bad=copy.deepcopy(boxes);bad["retrievedAtUtc"]="2026-11-15T13:00:00Z"
        with self.assertRaisesRegex(ValueError,"retrieval"):
            Elo3Pregame(ratings,games,bad)
        bad=copy.deepcopy(boxes);bad["games"][0]["away"]="Wrong School"
        with self.assertRaisesRegex(ValueError,"matchup"):
            Elo3Pregame(ratings,games,bad)
        bad=copy.deepcopy(boxes);bad["games"].append(copy.deepcopy(bad["games"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            Elo3Pregame(ratings,games,bad)

    def test_first_frozen_candidate_is_auditable_and_settles_once(self):
        ratings,games,boxes=current()
        shadow=Elo3Pregame(ratings,games,boxes)
        first=forecast_scheduled(schedule(),ratings,NOW,elo3_shadow=shadow)
        second=forecast_scheduled(schedule(),ratings,NOW+timedelta(hours=1))
        finals=[{"id":"ncaa-final","date":"2026-11-16",
                 "home":"Duke","away":"North Carolina",
                 "homeScore":75,"awayScore":68}]
        independent={"espn-1":{"date":"2026-11-16","homeScore":75,"awayScore":68}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write_ledger(root,first,[],NOW,verified_finals={})
            write_ledger(root,second,[],NOW+timedelta(hours=1),verified_finals={})
            write_ledger(root,{"predictions":[]},finals,NOW+timedelta(days=2),
                         verified_finals=independent)
            verified=audit_ledger(root)
            report=derive(root,NOW+timedelta(days=3))
            self.assertEqual(verified["predictions"],2)
            self.assertEqual(report["immutableFirstPicks"],1)
            research=report["prospectiveElo3"]
            self.assertEqual(research["firstFrozenPicks"],1)
            self.assertEqual(research["verifiedPairedFinals"],1)
            self.assertEqual(research["pendingOriginalFirstPicks"],0)
            self.assertEqual(research["pairedComparison"]["pairedGames"],1)
            self.assertIsNone(research["pairedComparison"]["dateBlockGain95"])
            self.assertFalse(research["pairedComparison"]["reviewEligible"])
            self.assertFalse(research["activePredictorReplaced"])

    def test_later_snapshot_cannot_backfill_missing_first_elo3(self):
        ratings,games,boxes=current()
        old=forecast_scheduled(schedule(),ratings,NOW)
        late=forecast_scheduled(schedule(),ratings,NOW+timedelta(hours=1),
                                elo3_shadow=Elo3Pregame(ratings,games,boxes))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write_ledger(root,old,[],NOW,verified_finals={})
            write_ledger(root,late,[],NOW+timedelta(hours=1),verified_finals={})
            report=derive(root,NOW+timedelta(hours=2))
            self.assertEqual(report["prospectiveElo3"]["firstFrozenPicks"],0)
            self.assertEqual(report["prospectiveElo3"]["verifiedPairedFinals"],0)

    def test_audit_rejects_tampered_candidate_timestamp_and_score(self):
        ratings,games,boxes=current()
        report=forecast_scheduled(schedule(),ratings,NOW,
             elo3_shadow=Elo3Pregame(ratings,games,boxes))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write_ledger(root,report,[],NOW,verified_finals={})
            path=next((root/"snapshots").glob("*.json"))
            original=path.read_text()
            obj=__import__("json").loads(original)
            obj["predictions"][0]["elo3Research"]["trainedThroughDate"]="2026-11-16"
            path.write_text(__import__("json").dumps(obj))
            with self.assertRaisesRegex(ValueError,"leaks"):
                audit_ledger(root)
            obj=__import__("json").loads(original)
            obj["predictions"][0]["elo3HomeWinProbability"]=1.2
            path.write_text(__import__("json").dumps(obj))
            with self.assertRaisesRegex(ValueError,"Elo3 probability"):
                audit_ledger(root)


if __name__=="__main__":
    unittest.main()

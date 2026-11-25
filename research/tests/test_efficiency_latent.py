"""Causal paired-box offense/defense and ensemble regressions."""
import copy
import unittest
from datetime import datetime,timezone,timedelta
from research.forecast.efficiency_latent import evaluate
from research.forecast.efficiency import BOX_URL

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
def data():
    start=datetime(2026,11,1)
    games=[]
    boxes=[]
    for i in range(12):
        day=(start+timedelta(days=i)).date().isoformat()
        games.append({"id":str(i),"date":day,"home":"A","away":"B",
                      "homeScore":75+i%4,"awayScore":68})
        boxes.append({"id":str(i),"date":day,"home":"A","away":"B",
                      "homeBox":{"off":111.+i,"def":98.,"poss":70.,"factors":None},
                      "awayBox":{"off":98.,"def":111.+i,"poss":70.,"factors":None}})
    ratings={"mode":"current","season":2027,"regularSeasonGames":len(games),
             "retrievedAtUtc":"2026-11-25T11:00:00Z","lastGameDate":games[-1]["date"]}
    manifest={"schemaVersion":1,"season":2027,"sourceUrl":BOX_URL,
              "retrievedAtUtc":ratings["retrievedAtUtc"],
              "acceptedScoreGames":len(games),"games":boxes}
    return games,ratings,manifest

class EfficiencyLatentTests(unittest.TestCase):
    def test_previous_date_only_and_paired_comparison(self):
        games,ratings,boxes=data()
        report=evaluate(games,ratings,boxes,NOW)
        self.assertEqual(report["eligibleComparedGames"],9)
        self.assertEqual(report["withheldGames"],3)
        self.assertIsNotNone(report["latent"]["brier"])
        self.assertIsNotNone(report["prequentialEnsemble"]["brier"])
        self.assertFalse(report["promotionEligible"])
        self.assertEqual(report["weightsByDate"][0]["weight"],0.)

    def test_current_date_scores_and_boxes_are_embargoed(self):
        games,ratings,boxes=data()
        baseline=evaluate(games,ratings,boxes,NOW)
        changed=copy.deepcopy(games)
        changed_boxes=copy.deepcopy(boxes)
        changed.append({"id":"future","date":"2026-11-25","home":"A","away":"B",
                        "homeScore":120,"awayScore":40})
        changed_boxes["games"].append({"id":"future","date":"2026-11-25",
            "home":"A","away":"B","homeBox":{"off":200.,"def":40.,"poss":70.},
            "awayBox":{"off":40.,"def":200.,"poss":70.}})
        changed_boxes["acceptedScoreGames"]+=1
        changed_ratings={**ratings,"regularSeasonGames":len(changed),
                         "lastGameDate":"2026-11-25"}
        after=evaluate(changed,changed_ratings,changed_boxes,NOW)
        for key in ("baseline","latent","prequentialEnsemble","eligibleComparedGames"):
            self.assertEqual(baseline[key],after[key])

    def test_rejects_mismatched_source_and_duplicate_identity(self):
        games,ratings,boxes=data()
        with self.assertRaisesRegex(ValueError,"timestamps"):
            evaluate(games,ratings,{**boxes,"retrievedAtUtc":"wrong"},NOW)
        bad=copy.deepcopy(boxes)
        bad["games"].append(bad["games"][0])
        with self.assertRaisesRegex(ValueError,"identity"):
            evaluate(games,ratings,bad,NOW)

    def test_missing_pair_abstains_without_imputation(self):
        games,ratings,boxes=data()
        boxes["games"]=boxes["games"][:6]
        r=evaluate(games,ratings,boxes,NOW)
        self.assertEqual(r["eligibleComparedGames"],3)
        self.assertGreater(r["withheldGames"],3)

if __name__=="__main__":
    unittest.main()

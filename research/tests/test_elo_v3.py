import unittest
from forecast.core import Game
from forecast.elo_v3 import replay,evaluate

class Elo3Tests(unittest.TestCase):
    def games(self):
        return [Game(2025,d,1,2,75,68,"H",f"g{d}") for d in range(1,20)]
    def test_date_embargo(self):
        games=self.games()
        a=replay(games)["rows"]
        changed=list(games)
        changed[-1]=Game(2025,19,2,1,90,60,"A","g19")
        b=replay(changed)["rows"]
        self.assertEqual([r["elo3"] for r in a[:-1]],[r["elo3"] for r in b[:-1]])
    def test_same_date_predictions_are_frozen(self):
        a=[Game(2025,1,1,2,80,70,"H","a"),
           Game(2025,1,1,3,72,70,"H","b"),
           Game(2025,2,1,3,75,65,"N","c")]
        b=[Game(2025,1,2,1,90,70,"A","a"),a[1],a[2]]
        left=replay(a)["rows"]
        right=replay(b)["rows"]
        self.assertEqual(left[1]["elo3"],right[1]["elo3"])
        self.assertNotEqual(left[2]["elo3"],right[2]["elo3"])

    def test_verified_four_factors_do_not_leak_to_first_day(self):
        games=self.games()
        f={"fga":60,"fgm":30,"fg3m":8,"fta":14,"tov":10,"orb":10,"drb":20}
        pairs={g.contest_id:{"winnerId":1,"loserId":2,"dayNum":g.day_num,
             "winner":{"off":110,"def":95,"poss":70,"factors":f},
             "loser":{"off":95,"def":110,"poss":70,"factors":f}} for g in games}
        without=replay(games)
        with_boxes=replay(games,paired_boxes=pairs)
        self.assertEqual(without["rows"][0]["elo3"],with_boxes["rows"][0]["elo3"])
        self.assertEqual(with_boxes["pairedBoxes"],len(games))
        self.assertEqual(with_boxes["fourFactorGames"][1],len(games))
        self.assertNotEqual(without["rows"][-1]["elo3"],with_boxes["rows"][-1]["elo3"])

    def test_box_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"identity"):
            replay(self.games(),paired_boxes={"g1":{"winnerId":9,"loserId":2,"dayNum":1}})
    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            replay(self.games()+[self.games()[0]])
    def test_prior_changes_predictions(self):
        g=self.games()
        self.assertNotEqual(replay(g)["rows"][0]["elo3"],
                            replay(g,{1:1600.,2:1400.})["rows"][0]["elo3"])
    def test_small_sample_is_shrunk_toward_verified_prior(self):
        result=replay([Game(2025,1,1,2,85,60,"H","small")])
        component=result["ratingComponents"][1]
        self.assertGreater(component["rawElo"],component["reliableElo"])
        self.assertGreater(component["reliableElo"],1500)
        self.assertAlmostEqual(component["prior"],1500)
        self.assertLess(component["reliability"],1)

    def test_schedule_strength_uses_prior_opponent_ratings(self):
        games=[Game(2025,d,11,21,80,60,"N",f"build-{d}") for d in range(1,9)]
        games += [Game(2025,d,1,31,79,65,"N",f"weak-{d}") for d in range(9,17)]
        games += [Game(2025,d,2,11,75,70,"N",f"strong-{d}") for d in range(9,17)]
        result=replay(games)
        self.assertGreater(result["ratingComponents"][2]["sos"],
                           result["ratingComponents"][1]["sos"])

    def test_historical_prior_uses_only_older_stable_ids(self):
        from forecast.elo_v3 import historical_priors
        old={2020:[Game(2020,d,1,2,85,60,"N",f"20-{d}") for d in range(1,134)],
             2021:[Game(2021,d,1,2,80,70,"N",f"21-{d}") for d in range(1,134)],
             2022:[Game(2022,d,2,1,80,70,"N",f"22-{d}") for d in range(1,134)]}
        one=historical_priors(old,2023,{1,2,3},1)
        multi=historical_priors(old,2023,{1,2,3},3)
        self.assertNotIn(3,one)
        self.assertNotIn(3,multi)
        self.assertGreater(multi[1],one[1])

    def test_paired_elo2_benchmark_never_mixes_fixtures(self):
        from forecast.elo_v3 import _paired_cohort
        with self.assertRaisesRegex(ValueError,"date/contest"):
            _paired_cohort([{"contestId":"a","dayNum":5,"winnerId":1,
                             "loserId":2,"winnerProbability":.6}],
                           [{"contestId":"x","day":5,"y":1.,"elo3":.6}])

    def test_exact_season_cohort_includes_elo2_and_multiyear(self):
        from forecast.elo_v3 import evaluate
        grouped={year:[Game(year,d,1,2,80,70,"N",f"{year}-{d}")
                       for d in range(1,134)] for year in range(2020,2024)}
        report=evaluate(grouped,years=(2023,))
        self.assertEqual(report["games"],133)
        self.assertEqual(report["elo2"]["games"],report["elo3"]["games"])
        self.assertEqual(report["elo3"]["games"],report["elo3Multi"]["games"])
        self.assertEqual(report["holdoutSeasons"],[2023])
        self.assertIsNotNone(report["brierGain"])

    def test_no_historical_data_does_not_invent_accuracy(self):
        self.assertIsNone(evaluate({})["brierGain"])
if __name__=="__main__":unittest.main()

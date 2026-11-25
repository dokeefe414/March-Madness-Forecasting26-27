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
    def test_no_historical_data_does_not_invent_accuracy(self):
        self.assertIsNone(evaluate({})["brierGain"])
if __name__=="__main__":unittest.main()

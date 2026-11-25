import unittest
from research.forecast.core import Game
from research.forecast.elo_v3 import replay,evaluate

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

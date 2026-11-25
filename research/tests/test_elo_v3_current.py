import unittest
from forecast.elo_v3_current import build


class CurrentElo3Tests(unittest.TestCase):
    def sources(self):
        stamp="2026-11-25T16:00:00Z"
        game={"id":"g1","date":"2026-11-05","home":"Duke",
              "away":"Oregon State","homeScore":77,"awayScore":71}
        return ({"season":2027,"retrievedAtUtc":stamp,"games":[game]},
                {"season":2027,"mode":"current","retrievedAtUtc":stamp,
                 "regularSeasonGames":1,"lastGameDate":"2026-11-05",
                 "teams":[{"name":"Duke","teamId":"ncaa-duke","wins":1,
                           "losses":0,"rating":1510.},
                          {"name":"Oregon State","teamId":"ncaa-oregon","wins":0,
                           "losses":1,"rating":1490.}]},
                {"retrievedAtUtc":stamp,"games":[]})

    def test_power_components_are_published_and_ranked(self):
        result=build(*self.sources())
        self.assertEqual(result["model"],"elo3")
        self.assertEqual(result["teams"][0]["name"],"Duke")
        self.assertEqual(result["teams"][0]["rating"],
                         round(result["teams"][0]["components"]["power"],2))
        self.assertIn("underlyingElo",result["teams"][0])
        self.assertEqual(len(result["top25OutlierAudit"]),2)
        self.assertEqual(result["currentRetrospective"]["sourceGames"],1)
        self.assertEqual(result["currentRetrospective"]["elo2"]["games"],1)
        self.assertEqual(result["currentRetrospective"]["elo3"]["games"],1)
        self.assertEqual(result["currentRetrospective"]["pairedBoxEligibleGames"],0)
        self.assertIn("small-sample",result["top25OutlierAudit"][0]["flags"])

    def test_reject_timestamp_mismatch(self):
        games,ratings,boxes=self.sources()
        boxes["retrievedAtUtc"]="2026-11-24T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"timestamps"):
            build(games,ratings,boxes)

    def test_reject_missing_source_team(self):
        games,ratings,boxes=self.sources()
        ratings["teams"].pop()
        with self.assertRaisesRegex(ValueError,"Missing team"):
            build(games,ratings,boxes)


if __name__=="__main__":
    unittest.main()

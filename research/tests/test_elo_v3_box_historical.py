"""Hermetic historical Kaggle detailed-source and Elo3 four-way ablation tests."""
import csv
import hashlib
import io
import unittest

from forecast.core import Game
from forecast.elo_v3 import replay
from forecast.elo_v3_box_historical import (
    FIELD_BASE, STATS, _git_blob_sha, parse_detail, evaluate,
)


def record(day,season=2023):
    # 75 = 2*28+8+11; 68 = 2*25+7+11.
    w={"FGM":28,"FGA":60,"FGM3":8,"FGA3":20,"FTM":11,"FTA":15,
       "OR":10,"DR":27,"Ast":17,"TO":12,"Stl":8,"Blk":4,"PF":18}
    l={"FGM":25,"FGA":59,"FGM3":7,"FGA3":20,"FTM":11,"FTA":14,
       "OR":9,"DR":26,"Ast":15,"TO":10,"Stl":6,"Blk":3,"PF":19}
    return {"Season":season,"DayNum":day,"WTeamID":1,"LTeamID":2,
            "WScore":75,"LScore":68,"WLoc":"H",
            **{"W"+key:v for key,v in w.items()},
            **{"L"+key:v for key,v in l.items()}}


def csv_bytes(rows):
    buf=io.StringIO()
    writer=csv.DictWriter(buf,fieldnames=list(FIELD_BASE)+
                          ["W"+key for key in STATS]+["L"+key for key in STATS])
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def season():
    previous=[Game(2022,132,1,2,75,68,"H","p-2022")]
    games=[Game(2023,i,1,2,75,68,"H",f"2023-{i}-1-2") for i in range(1,16)]
    games.append(Game(2023,132,1,2,75,68,"H","2023-132-1-2"))
    return {2022:previous,2023:games}


class HistoricalBoxTests(unittest.TestCase):
    def test_source_blob_sha_is_standard_git_object(self):
        raw=b"Season,DayNum\n2023,1\n"
        reference=hashlib.sha1(b"blob "+str(len(raw)).encode()+
                               bytes([0])+raw).hexdigest()
        self.assertEqual(_git_blob_sha(raw),reference)

    def test_observed_stats_are_matched_without_inventing_possessions(self):
        grouped=season()
        raw=csv_bytes([record(g.day_num) for g in grouped[2023]])
        pairs,coverage=parse_detail(raw,grouped,years=(2023,))
        self.assertEqual(coverage["matched"],16)
        self.assertEqual(coverage["coverageBySeason"]["2023"]["coverage"],1.)
        self.assertIn("ESTIMATED",coverage["possessionSource"])
        first=pairs[2023]["2023-1-1-2"]
        self.assertAlmostEqual(first["winner"]["factors"]["fga"],60)
        self.assertEqual(first["winner"]["extras"]["ast"],17)
        self.assertTrue(40<first["winner"]["poss"]<120)

    def test_real_box_ablations_use_identical_prior_day_fixtures(self):
        grouped=season()
        raw=csv_bytes([record(g.day_num) for g in grouped[2023]])
        pairs,coverage=parse_detail(raw,grouped,years=(2023,))
        report=evaluate(grouped,pairs,coverage,years=(2023,))
        self.assertEqual(report["holdoutSeasons"],[2023])
        self.assertEqual(report["eligiblePairedGames"],13)
        self.assertEqual(report["variants"]["scoreOnly"]["games"],13)
        for variant in ("efficiency","fourFactors","extended"):
            self.assertEqual(report["variants"][variant]["games"],13)
            self.assertIsNotNone(report["brierGainVsScoreOnly"][variant])
        self.assertNotEqual(report["variants"]["scoreOnly"]["brier"],
                            report["variants"]["efficiency"]["brier"])

    def test_five_year_bootstrap_uses_identical_eligible_game_counts(self):
        grouped={2018:[Game(2018,132,1,2,75,68,"H","2018-132-1-2")]}
        source=[]
        for year in range(2019,2024):
            games=[Game(year,d,1,2,75,68,"H",f"{year}-{d}-1-2")
                   for d in list(range(1,16))+[132]]
            grouped[year]=games
            source.extend(record(g.day_num,year) for g in games)
        pairs,coverage=parse_detail(csv_bytes(source),grouped,
                                    years=tuple(range(2019,2024)))
        report=evaluate(grouped,pairs,coverage,years=tuple(range(2019,2024)))
        self.assertEqual(report["status"],"ready")
        self.assertEqual(report["eligiblePairedGames"],65)
        self.assertEqual(len(report["holdoutSeasons"]),5)
        self.assertEqual(len(report["seasonBlockGain95"]["efficiency"]),2)
        self.assertTrue(all(y["games"]==13 for y in report["bySeason"]))

    def test_conflicting_scores_and_duplicate_identity_are_withheld(self):
        grouped=season()
        records=[record(g.day_num) for g in grouped[2023]]
        wrong=[dict(x) for x in records];wrong[0]["LScore"]=60
        pairs,coverage=parse_detail(csv_bytes(wrong),grouped,years=(2023,))
        self.assertEqual(coverage["matched"],15)
        self.assertEqual(coverage["mismatches"]["scoreOrVenueMismatch"],1)
        duplicated=records+[dict(records[0])]
        pairs,coverage=parse_detail(csv_bytes(duplicated),grouped,years=(2023,))
        self.assertEqual(coverage["matched"],15)
        self.assertNotIn("2023-1-1-2",pairs[2023])

    def test_invalid_shooting_and_score_arithmetic_are_withheld(self):
        grouped=season()
        records=[record(g.day_num) for g in grouped[2023]]
        records[0]["WFGM3"]=60
        pairs,coverage=parse_detail(csv_bytes(records),grouped,years=(2023,))
        self.assertEqual(coverage["mismatches"]["invalidBox"],1)
        records[0]=record(1)
        records[0]["WFTM"]=12
        pairs,coverage=parse_detail(csv_bytes(records),grouped,years=(2023,))
        self.assertEqual(coverage["mismatches"]["invalidBox"],1)

    def test_missing_columns_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"missing Kaggle box"):
            parse_detail(b"Season,DayNum\n2023,1\n",season(),years=(2023,))

    def test_future_game_box_does_not_change_prior_prediction(self):
        games=season()[2023]
        rows=[record(g.day_num) for g in games]
        pairs,_=parse_detail(csv_bytes(rows),{2023:games},years=(2023,))
        normal=replay(games,paired_boxes=pairs[2023])["rows"]
        changed={key:dict(value) for key,value in pairs[2023].items()}
        last=changed["2023-132-1-2"]
        altered={**last,"winner":{**last["winner"],
                  "off":last["winner"]["off"]+50.}}
        changed["2023-132-1-2"]=altered
        other=replay(games,paired_boxes=changed)["rows"]
        self.assertEqual([r["elo3"] for r in normal[:-1]],
                         [r["elo3"] for r in other[:-1]])


if __name__=="__main__":
    unittest.main()

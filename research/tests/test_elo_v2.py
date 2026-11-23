"""Elo 2.0: paired game-date evidence and independent prior-season source tests."""
from __future__ import annotations

import csv
import copy
import io
import unittest
from datetime import datetime,timezone

from forecast.core import Game
from forecast.game_aware_elo import GameAwareEloEngine
from forecast.elo_v2 import Elo2Engine,preseason_priors,paired_metrics
from forecast.elo_v2_historical import read_games,evaluate
from forecast.elo_v2_current import build,source_priors,_to_games
from forecast.history import SOURCE_COMMIT
from forecast.live import build_current


def g(d,w,l,m=8,where="N",event=None,year=2027):
    return Game(year,d,w,l,70+m,70,where,event or f"{d}-{w}-{l}")


class EloV2Tests(unittest.TestCase):
    def test_preseason_regression_never_reads_current_year(self):
        priors=preseason_priors({1:1750,2:1200,3:1500}, {1,2,3,4})
        self.assertEqual(priors[1],1588)
        self.assertEqual(priors[2],1412)
        self.assertEqual(priors[3],1500)
        self.assertNotIn(4,priors)
        with self.assertRaises(ValueError):
            preseason_priors({1:1740},{1},weight=1.2)

    def test_same_date_freeze_and_zero_sum_deltas_with_nonzero_priors(self):
        games=[g(1,1,2,7,event="one"),g(1,1,3,13,event="two"),
               g(2,1,2,8,event="three")]
        prior={1:1580,2:1430,3:1515}
        a=Elo2Engine(prior).fit(games,{})
        b=Elo2Engine(prior).fit(list(reversed(games)),{})
        self.assertEqual(a.game_receipts,b.game_receipts)
        self.assertEqual(a.standings(),b.standings())
        self.assertEqual(a.game_receipts[0]["preWinnerElo"],1580)
        self.assertEqual(a.game_receipts[1]["preWinnerElo"],1580)
        self.assertEqual(a.game_receipts[0]["winnerPriorOpponentGames"],0)
        self.assertEqual(a.game_receipts[1]["winnerPriorOpponentGames"],0)
        self.assertAlmostEqual(a.conservation_error,0,places=7)
        self.assertAlmostEqual(sum(s.rating for s in a.states.values()),4525,places=6)
        self.assertNotEqual(a.game_receipts[-1]["winnerSosAdjustment"],0)
        self.assertEqual(len(a.team_receipts[1]),3)

    def test_causal_schedule_adjustment_is_shrunk_bounded_and_no_future_use(self):
        first=[g(d,1,2,7,event=str(d)) for d in range(1,10)]
        after=first+[g(10,1,2,10,event="later")]
        control=Elo2Engine({},.16).fit(first,{})
        candidate=Elo2Engine({},.16).fit(after,{})
        self.assertEqual(candidate.game_receipts[:-1],control.game_receipts)
        self.assertEqual(candidate.game_receipts[0]["winnerSosAdjustment"],0)
        self.assertEqual(candidate.game_receipts[-1]["winnerPriorOpponentGames"],9)
        self.assertLessEqual(abs(candidate.schedule_adjustment(1)),35)
        self.assertLessEqual(abs(candidate.schedule_adjustment(2)),35)
        disabled=Elo2Engine({},0).fit(after,{})
        self.assertTrue(all(r["winnerSosAdjustment"]==0 for r in disabled.game_receipts))

    def test_paired_identical_fixture_proof_and_no_fake_brier_gain(self):
        games=[g(1,1,2,6,event="one"),g(2,2,3,3,event="two")]
        baseline=GameAwareEloEngine().fit(games,{})
        equal=Elo2Engine({},0).fit(games,{})
        stats=paired_metrics(baseline.game_receipts,equal.game_receipts)
        self.assertEqual(stats["games"],2)
        self.assertAlmostEqual(stats["brierGain"],0,places=6)
        self.assertEqual(stats["baselineAccuracy"],stats["challengerAccuracy"])
        with self.assertRaisesRegex(ValueError,"Different or duplicate"):
            paired_metrics(baseline.game_receipts,equal.game_receipts[:1])
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            Elo2Engine().fit([g(1,1,2,6,event="z"),g(2,2,1,5,event="z")],{})

    def test_provisional_prior_exact_name_only_not_alias_guess(self):
        prev={"mode":"historical","season":2026,"sourceCommit":SOURCE_COMMIT,
              "throughDay":118,"isComplete":False,
              "teams":[{"name":"Florida","rating":1740.0},
                       {"name":"Connecticut","rating":1680.0}]}
        names={"Florida","florida","UConn","Connecticut"}
        matched,report=source_priors(prev,names)
        self.assertEqual(matched["Florida"],1740)
        self.assertEqual(matched["florida"],1740)
        self.assertEqual(matched["Connecticut"],1680)
        self.assertNotIn("UConn",matched)
        self.assertFalse(report["snapshotIsComplete"])
        self.assertIn("not approved",report["identityWarning"])
        wrong=copy.deepcopy(prev);wrong["sourceCommit"]="unverified"
        with self.assertRaisesRegex(ValueError,"provenance"):
            source_priors(wrong,names)
        wrong=copy.deepcopy(prev);wrong["isComplete"]=True
        with self.assertRaisesRegex(ValueError,"coverage"):
            source_priors(wrong,names)

    def test_history_csv_is_pinned_source_cohort_and_held_out_years(self):
        out=io.StringIO()
        writer=csv.DictWriter(out,fieldnames=["Season","DayNum","WTeamID","WScore","LTeamID","LScore","WLoc"])
        writer.writeheader()
        for season in range(2015,2022):
            for day in [20,35,45,80,100,132]:
                writer.writerow({"Season":season,"DayNum":day,
                    "WTeamID":101 if day%2 else 102,"LTeamID":102 if day%2 else 101,
                    "WScore":75+season%5,"LScore":67,"WLoc":"H"})
        seasons,sha=read_games(out.getvalue().encode("utf8"))
        result=evaluate(seasons,sha,tuple(range(2016,2022)))
        self.assertEqual(result["status"],"ready")
        self.assertEqual(result["holdoutSeasons"],6)
        self.assertEqual(result["firstHeldOutYear"],2016)
        for label,v in result["variants"].items():
            self.assertEqual(v["games"],36)
            self.assertEqual(v["earlySeason"]["games"],18)
            self.assertEqual(len(v["seasonBlockBrierGain95"]),2)
        self.assertEqual(result["bySeason"][0]["priorMatchedTeams"],2)
        seasons[2017].append(g(5,101,102,event="late",year=2017))
        other=evaluate(seasons,sha,tuple(range(2016,2022)))
        self.assertNotEqual(result["bySeason"][1]["games"],other["bySeason"][1]["games"])
        with self.assertRaisesRegex(ValueError,"Duplicate historical"):
            read_games((out.getvalue()+out.getvalue().splitlines()[-1]+"\n").encode())

    def test_full_current_report_replays_only_real_games_and_is_research(self):
        raw=[{"id":"one","date":"2026-11-13","home":"Florida","away":"Kentucky",
              "homeScore":78,"awayScore":71},
             {"id":"two","date":"2026-11-14","home":"Kentucky","away":"Duke",
              "homeScore":77,"awayScore":66}]
        at=datetime(2026,11,23,16,tzinfo=timezone.utc)
        ratings=build_current(raw,at)
        for i,t in enumerate(ratings["teams"]):
            t["divisionIConfirmed"]=True
            t["espnSourceTeamId"]=str(100+i)
        prev={"mode":"historical","season":2026,"sourceCommit":SOURCE_COMMIT,
              "throughDay":118,"isComplete":False,
              "teams":[{"name":"Florida","rating":1740},
                       {"name":"Kentucky","rating":1620},
                       {"name":"Duke","rating":1700}]}
        ap={"season":2027,"weeks":[]}
        hist={"status":"unavailable","holdoutSeasons":0}
        report=build(raw,ratings,prev,ap,hist,at)
        self.assertFalse(report["modelPromotionAllowed"])
        self.assertEqual(report["sourceGames"],2)
        self.assertEqual(report["priorCoverage"]["matchedTeamNames"],3)
        self.assertIn("carryoverAndSchedule",report["currentRetrospective"])
        self.assertEqual(report["currentRetrospective"]["carryoverAndSchedule"]["games"],2)
        self.assertEqual(len(report["teams"]),3)
        self.assertEqual(set(x["baselineRank"] for x in report["teams"]),{1,2,3})
        self.assertEqual(report["apComparisons"],[])
        bad=copy.deepcopy(ratings);bad["regularSeasonGames"]=8
        with self.assertRaisesRegex(ValueError,"count"):
            build(raw,bad,prev,ap,hist,at)
        future=[{**raw[0],"date":"2026-11-25"}]
        with self.assertRaisesRegex(ValueError,"Future score"):
            build(future,{**ratings,"regularSeasonGames":1},prev,ap,hist,at)


if __name__=="__main__":
    unittest.main()

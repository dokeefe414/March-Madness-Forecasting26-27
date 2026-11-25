"""Hermetic prospective Elo 3.0 cohort/segment diagnostics regression tests."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone, timedelta

from forecast.elo_v3_forward_diagnostics import derive

NOW=datetime(2026,11,25,21,39,tzinfo=timezone.utc)


def event(eid, *, baseline=.65, elo3=.75, start="2026-11-26T01:00:00Z",
          neutral=False, game_date="2026-11-25"):
    return {"eventId":eid, "home":"Duke", "away":"UNC",
            "scheduledStartUtc":start,"scheduledEasternDate":game_date,
            "neutralSite":neutral,
            "baselineHomeWinProbability":baseline,
            "elo3HomeWinProbability":elo3}


def snap(stamp,predictions,identifier):
    return {"snapshotId":identifier,"generatedAtUtc":stamp,
            "predictions":predictions}


def frozen(source):
    entries={}
    for s in sorted(source,key=lambda x:x["generatedAtUtc"]):
        for p in s["predictions"]:
            entries.setdefault(p["eventId"],(s,p))
    return entries


def final(eid,baseline,elo3,day,home_win=1):
    return {"eventId":eid,"day":day,"observedHome":home_win,
            "elo":baseline,"Elo 3.0 prospective":elo3}


class Elo3ForwardDiagnosticsTests(unittest.TestCase):
    def test_empty_cohort_never_claims_skill(self):
        report=derive({},[],[],[],NOW)
        self.assertEqual(report["status"],"no-eligible-first-picks")
        self.assertEqual(report["eligibleOriginalFirstPicks"],0)
        self.assertIsNone(report["overallVerified"]["brierGain"])
        self.assertIsNone(report["afterLaunchCandidateCoverage"])
        self.assertEqual(report["topUpcomingDisagreements"],[])
        self.assertIsNone(report["calibration"]["ece"])

    def test_first_pick_wins_over_later_elo3_and_coverage_has_denominator(self):
        original=snap("2026-11-25T19:00:00Z",[
            {**event("older"),"elo3HomeWinProbability":None}], "old")
        new=snap("2026-11-25T21:30:00Z",[
            event("older",baseline=.55,elo3=.99),
            event("new",baseline=.53,elo3=.69),
            {**event("missed"),"elo3HomeWinProbability":None}], "new")
        first=frozen([new,original])
        result=derive(first,[original,new],[],[],NOW)
        self.assertEqual(result["allCapturedShadowPredictions"],2)
        self.assertEqual(result["eligibleOriginalFirstPicks"],1)
        self.assertEqual(result["laterOnlyShadowEventsExcluded"],1)
        self.assertEqual(result["afterLaunchOriginalFirstPicks"],2)
        self.assertEqual(result["afterLaunchMissingShadow"],1)
        self.assertEqual(result["afterLaunchCandidateCoverage"],.5)
        self.assertEqual(len(result["examplesMissingAfterLaunch"]),1)
        self.assertEqual(result["topUpcomingDisagreements"][0]["eventId"],"new")

    def test_first_picks_are_stratified_and_pending_stays_unscored(self):
        captured=snap("2026-11-25T20:00:00Z",[
            event("a",baseline=.55,elo3=.80,neutral=True),
            event("b",baseline=.61,elo3=.40,start="2026-11-26T13:00:00Z",
                  game_date="2026-11-26"),
            event("c",baseline=.95,elo3=.94,start="2026-11-27T20:00:00Z",
                  game_date="2026-11-27")], "batch")
        outcomes=[final("a",.55,.80,"2026-11-25",1),
                  final("b",.61,.40,"2026-11-26",0)]
        pending=[{"eventId":"c","status":"upcoming"}]
        result=derive(frozen([captured]),[captured],outcomes,pending,NOW)
        self.assertEqual(result["eligibleOriginalFirstPicks"],3)
        self.assertEqual(result["verifiedPairedFinals"],2)
        self.assertEqual(result["pendingOriginalFirstPicks"],1)
        self.assertEqual(result["pendingByStatus"],{"upcoming":1})
        self.assertEqual(result["difference"]["differentWinnerPicks"],1)
        self.assertEqual(result["difference"]["differenceAtLeast10pp"],2)
        self.assertEqual(result["overallVerified"]["games"],2)
        self.assertEqual(result["overallVerified"]["gameDates"],2)
        self.assertEqual(result["overallVerified"]["status"],"descriptive-only")
        self.assertGreater(result["overallVerified"]["brierGain"],0)
        venue={x["segment"]:x for x in result["segments"]["venue"]}
        self.assertEqual(venue["Neutral"]["verifiedResults"] if "verifiedResults" in venue["Neutral"] else venue["Neutral"]["games"],1)
        self.assertEqual(venue["Neutral"]["firstFrozenPicks"],1)
        self.assertEqual(venue["Listed home"]["firstFrozenPicks"],2)
        switched={x["segment"]:x for x in result["segments"]["winnerAgreement"]}
        self.assertEqual(switched["Different picks"]["games"],1)
        self.assertEqual(result["calibration"]["games"],2)
        self.assertEqual(len(result["topUpcomingDisagreements"]),3)

    def test_unverified_games_do_not_enter_results_or_overstate_significance(self):
        captured=snap("2026-11-25T20:00:00Z",[
            event(str(i),baseline=.6,elo3=.7,
                  start="2026-11-27T20:00:00Z",game_date="2026-11-27")
            for i in range(50)],"start")
        result=derive(frozen([captured]),[captured],[],[],NOW)
        self.assertEqual(result["eligibleOriginalFirstPicks"],50)
        self.assertEqual(result["verifiedPairedFinals"],0)
        self.assertIsNone(result["overallVerified"]["brierGain"])
        self.assertIsNone(result["calibration"]["ece"])
        self.assertEqual(result["segments"]["disagreementSize"][-1]["status"],"no-verified-pairs")
        self.assertEqual(result["afterLaunchCandidateCoverage"],1)

    def test_score_discrepancy_fails_closed_instead_of_approximating_original(self):
        captured=snap("2026-11-25T20:00:00Z",[
            event("x",baseline=.6,elo3=.7)],"start")
        with self.assertRaisesRegex(ValueError,"differs from original"):
            derive(frozen([captured]),[captured],
                   [final("x",.61,.7,"2026-11-25")],[],NOW)
        with self.assertRaisesRegex(ValueError,"differs from original"):
            derive(frozen([captured]),[captured],
                   [final("x",.6,.71,"2026-11-25")],[],NOW)

    def test_invalid_probability_and_near_tipoff_are_rejected(self):
        captured=snap("2026-11-25T20:00:00Z",[
            event("x",baseline=.4,elo3=1.3)],"start")
        with self.assertRaisesRegex(ValueError,"probability"):
            derive(frozen([captured]),[captured],[],[],NOW)
        captured=snap("2026-11-25T20:00:00Z",[
            event("x",baseline=.4,elo3=.7,start="2026-11-25T20:10:00Z")],"start")
        with self.assertRaisesRegex(ValueError,"15-minute"):
            derive(frozen([captured]),[captured],[],[],NOW)

    def test_duplicate_verified_outcomes_are_rejected(self):
        captured=snap("2026-11-25T20:00:00Z",[event("x")],"start")
        outcome=final("x",.65,.75,"2026-11-25")
        with self.assertRaisesRegex(ValueError,"Duplicate settled"):
            derive(frozen([captured]),[captured],[outcome,outcome],[],NOW)


if __name__=="__main__":
    unittest.main()

"""Hermetic proof: predictions precede sourced start; results settle later."""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from forecast.snapshot import forecast_scheduled, settle_snapshots, write_ledger, parse_time

NOW = datetime(2026, 11, 16, 14, tzinfo=timezone.utc)
RATINGS = {
    "mode": "current", "season": 2027,
    "retrievedAtUtc": "2026-11-16T13:00:00Z",
    "lastGameDate": "2026-11-15", "sourceUrl": "https://example.invalid/ncaa",
    "teams": [
        {"name": "Duke", "teamId": "duke", "rating": 1550},
        {"name": "North Carolina", "teamId": "unc", "rating": 1520},
    ],
}


def game(identifier: str, start: str, state="STATUS_SCHEDULED", away="North Carolina",
         home="Duke", neutral=False):
    return {
        "id": identifier, "date": start,
        "status": {"type": {"name": state, "completed": state == "STATUS_FINAL"}},
        "competitions": [{
            "neutralSite": neutral,
            "competitors": [
                {"homeAway": "home", "team": {"location": home, "displayName": home + " Blue Devils"}},
                {"homeAway": "away", "team": {"location": away, "displayName": away + " Tar Heels"}},
            ],
        }],
    }


class PregameAuditTests(unittest.TestCase):
    def test_future_time_and_exact_match_only(self):
        scoreboard = {"events": [
            game("ESPN-1", "2026-11-17T01:00:00Z"),
            game("ESPN-2", "2026-11-16T13:50:00Z"),
            game("ESPN-3", "2026-11-17T02:00:00Z", state="STATUS_FINAL"),
            game("ESPN-4", "2026-11-17T02:00:00Z", away="Other University"),
            game("ESPN-1", "2026-11-17T01:00:00Z"),
        ]}
        report = forecast_scheduled([scoreboard], RATINGS, NOW)
        self.assertEqual(len(report["predictions"]), 1)
        self.assertEqual(report["predictions"][0]["eventId"], "ESPN-1")
        self.assertEqual(report["predictions"][0]["scheduledEasternDate"], "2026-11-16")
        self.assertGreater(report["predictions"][0]["homeWinProbability"], .5)
        self.assertEqual(report["coverage"]["unmatchedOrAmbiguous"], 1)
        self.assertEqual(report["coverage"]["duplicateIds"], 1)
        self.assertEqual(report["coverage"]["startedOrTooClose"], 1)
        self.assertEqual(report["coverage"]["notScheduled"], 1)
        self.assertEqual(report["timeBufferMinutes"], 15)

    def test_game_aware_elo_version_is_frozen_without_relabeling_old_picks(self):
        fixture = [{"events": [game("ESPN-1", "2026-11-17T01:00:00Z")]}]
        original = forecast_scheduled(fixture, RATINGS, NOW)["predictions"][0]
        self.assertEqual(original["model"], "as-of regular-season Elo")
        self.assertIsNone(original["ratingMethodVersion"])
        updated = forecast_scheduled(
            fixture,
            {**RATINGS, "eloMethodology":{"version":"source-aware-game-elo-v1"}},
            NOW
        )["predictions"][0]
        self.assertEqual(updated["model"], "source-aware margin Elo v2.1")
        self.assertEqual(updated["ratingMethodVersion"], "source-aware-game-elo-v1")
        self.assertNotEqual(updated["model"], original["model"])
        # Only a new forecast receives the new version; existing JSON is immutable.
        self.assertEqual(original["model"], "as-of regular-season Elo")

    def test_future_ratings_rejected_and_invalid_time(self):
        wrong = {**RATINGS, "retrievedAtUtc": "2026-11-17T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "future"):
            forecast_scheduled([{"events": []}], wrong, NOW)
        with self.assertRaisesRegex(ValueError, "timezone"):
            parse_time("2026-11-16T23:00:00")

    def test_separate_settlements_are_append_only(self):
        forecast = forecast_scheduled([{"events": [game("ESPN-1", "2026-11-17T01:00:00Z")]}], RATINGS, NOW)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            first = write_ledger(directory, forecast, [], NOW)
            self.assertEqual(first["scores"]["settledPredictions"], 0)
            snap = list((directory / "snapshots").glob("*.json"))[0]
            before = snap.read_bytes()
            final = [{
                "id": "NCAA-100", "date": "2026-11-16",
                "home": "Duke", "away": "North Carolina",
                "homeScore": 84, "awayScore": 80,
            }]
            later = NOW + timedelta(days=2)
            result = write_ledger(directory, {"predictions": []}, final, later)
            self.assertEqual(result["scores"]["settledPredictions"], 1)
            self.assertEqual(snap.read_bytes(), before)
            self.assertEqual(result["settlements"][0]["observedHome"], 1)
            self.assertGreaterEqual(result["scores"]["brier"], 0)
            # Re-running must not settle the same pregame record twice.
            again = write_ledger(directory, {"predictions": []}, final, later + timedelta(days=1))
            self.assertEqual(again["scores"]["settledPredictions"], 1)

    def test_wrong_sides_never_settle(self):
        report = forecast_scheduled([{"events": [game("ESPN-1", "2026-11-17T01:00:00Z")]}], RATINGS, NOW)
        report["snapshotId"] = "immutable"
        source = [{"id":"NCAA-1","date":"2026-11-16","home":"North Carolina",
                   "away":"Duke","homeScore":100,"awayScore":70}]
        self.assertEqual(settle_snapshots([report], source, set(), NOW + timedelta(days=2)), [])

    def test_tampering_and_time_travel_are_rejected(self):
        from forecast.audit import audit_ledger
        forecast = forecast_scheduled([{"events": [
            game("ESPN-1", "2026-11-17T01:00:00Z")]}], RATINGS, NOW)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            write_ledger(path, forecast, [], NOW)
            self.assertEqual(audit_ledger(path)["predictions"], 1)
            snap_file = next((path / "snapshots").glob("*.json"))
            saved = json.loads(snap_file.read_text())
            altered = {**saved, "generatedAtUtc": "2026-11-17T00:55:00Z"}
            snap_file.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "tip-off buffer"):
                audit_ledger(path)
            snap_file.write_text(json.dumps(saved))
            self.assertEqual(
                settle_snapshots([{**saved, "generatedAtUtc": "2026-11-17T00:55:00Z"}],
                    [{"id":"100","date":"2026-11-16","home":"Duke","away":"North Carolina",
                      "homeScore":80,"awayScore":70}], set(), NOW + timedelta(days=2)),
                [], "a near-tipoff artifact must not settle",
            )
            final = [{"id":"100","date":"2026-11-16","home":"Duke","away":"North Carolina",
                      "homeScore":80,"awayScore":70}]
            write_ledger(path, {"predictions": []}, final, NOW + timedelta(days=2))
            self.assertEqual(audit_ledger(path)["settledPredictions"], 1)
            settlement_file = next((path / "settlements").glob("*.json"))
            settled = json.loads(settlement_file.read_text())
            settled["results"][0]["brier"] = 0.999999
            settlement_file.write_text(json.dumps(settled))
            with self.assertRaisesRegex(ValueError, "scoring mismatch"):
                audit_ledger(path)

    def test_empty_public_ledger_is_explicit(self):
        from forecast.audit import audit_ledger
        with tempfile.TemporaryDirectory() as folder:
            result = audit_ledger(Path(folder))
            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["predictions"], 0)
            self.assertEqual(result["settledPredictions"], 0)

    def test_model_adoption_only_after_chronological_gate(self):
        ratings = {**RATINGS, "teams": [
            {**RATINGS["teams"][0], "wins":6,"losses":2,"trend":8},
            {**RATINGS["teams"][1], "wins":1,"losses":6,"trend":-7},
        ]}
        model = {"mode":"active","type":"current-season-chronological-logistic",
                 "season":2027,"modelId":"model001",
                 "ratingRetrievedAtUtc":"2026-11-16T13:00:00Z",
                 "trainedThroughDate":"2026-11-15","modelWeights":[0,0,.4,0]}
        fixture = {"events":[game("ESPN-1","2026-11-17T01:00:00Z")]}
        pred=forecast_scheduled([fixture],ratings,NOW,online_model=model)["predictions"][0]
        self.assertEqual(pred["model"],"chronologically validated in-season logistic")
        self.assertEqual(pred["modelId"],"model001")
        self.assertEqual(pred["modelTrainingThroughDate"],"2026-11-15")
        other=forecast_scheduled([fixture],ratings,NOW,online_model={**model,"mode":"shadow"})
        self.assertEqual(other["predictions"][0]["model"],"as-of regular-season Elo")
        with self.assertRaisesRegex(ValueError,"same-date"):
            forecast_scheduled([fixture],ratings,NOW,online_model={**model,"trainedThroughDate":"2026-11-16"})
        neutral=forecast_scheduled([{"events":[game("ESPN-2","2026-11-17T01:00:00Z",neutral=True)]}],ratings,NOW,online_model=model)
        self.assertEqual(neutral["predictions"][0]["model"],"as-of regular-season Elo")


    def test_same_day_future_fixture_uses_yesterday_elo_not_this_mornings_result(self):
        from forecast.live import build_current
        from forecast.core import matchup_probability
        past = [{"id":"prev","date":"2026-11-15","home":"Duke",
                 "away":"North Carolina","homeScore":76,"awayScore":70}]
        today = {"id":"earlier-today","date":"2026-11-16","home":"North Carolina",
                 "away":"Duke","homeScore":97,"awayScore":65}
        source = past + [today]
        rating = build_current(source, NOW)
        rating["retrievedAtUtc"] = "2026-11-16T13:00:00Z"
        board = [{"events":[game("later-today","2026-11-17T01:00:00Z")]}]
        first = forecast_scheduled(board,rating,NOW,scored_games=source)
        self.assertEqual(first["coverage"]["unsafeSameDateRatings"],0)
        pick = first["predictions"][0]
        earlier = build_current(past,NOW)
        states = {t["name"]:t for t in earlier["teams"]}
        expected = matchup_probability(states["Duke"]["rating"],
                                      states["North Carolina"]["rating"],65)
        self.assertAlmostEqual(pick["homeWinProbability"],expected,places=6)
        self.assertEqual(pick["ratingReplayMode"],"prior-date-safe")
        self.assertEqual(pick["ratingSourceIncludedThroughDate"],"2026-11-15")
        self.assertEqual(pick["ratingInputs"]["home"]["wins"],1)
        self.assertEqual(pick["ratingInputs"]["away"]["wins"],0)
        self.assertIsNone(pick["researchScoreProjection"])
        # Rewriting today's score cannot alter a strictly prior-date pick.
        altered = past + [{**today,"homeScore":110,"awayScore":55}]
        changed = build_current(altered,NOW)
        changed["retrievedAtUtc"] = rating["retrievedAtUtc"]
        again = forecast_scheduled(board,changed,NOW,scored_games=altered)
        self.assertEqual(pick["homeWinProbability"],again["predictions"][0]["homeWinProbability"])
        # Without the exact scored-game ledger, the old safety guard remains.
        blocked = forecast_scheduled(board,rating,NOW)
        self.assertEqual(blocked["coverage"]["unsafeSameDateRatings"],1)
        self.assertEqual(blocked["rejectionReasons"]["later-today"],"missing-verified-prior-date-replay")

    def test_safe_date_replay_rejects_mismatched_rating_ledger(self):
        from forecast.live import build_current
        rows=[{"id":"same-day","date":"2026-11-16","home":"Duke",
               "away":"North Carolina","homeScore":80,"awayScore":79}]
        rating=build_current(rows,NOW)
        rating["retrievedAtUtc"]="2026-11-16T13:00:00Z"
        with self.assertRaisesRegex(ValueError,"counts differ"):
            forecast_scheduled([{"events":[game("future","2026-11-17T01:00:00Z")]}],
                               rating,NOW,scored_games=[])


if __name__ == "__main__":
    unittest.main()

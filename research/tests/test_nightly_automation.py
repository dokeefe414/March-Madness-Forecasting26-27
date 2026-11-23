"""Guard the overnight result -> archive -> site -> monitoring schedule.

The archived first-pick result ledger must refresh before a nightly Pages build.
These tests intentionally use only stdlib so they run in the existing CI suite.
They validate configuration, not actual GitHub scheduler delivery.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def schedules(filename: str) -> list[str]:
    content = (WORKFLOWS / filename).read_text(encoding="utf-8")
    values = re.findall(r'^\s*- cron: "([^"]+)"', content, re.MULTILINE)
    if not values:
        raise AssertionError(f"{filename} has no scheduled triggers")
    if content.count('timezone: "America/New_York"') < len(values):
        raise AssertionError(f"{filename} must use daylight-saving-aware Eastern crons")
    return values


def times(crons: list[str]) -> set[tuple[int, int]]:
    return {
        (int(hour), int(minute))
        for cron in crons
        for minute_field, hour_field, *_ in [cron.split()]
        for minute in minute_field.split(",")
        for hour in hour_field.split(",")
    }


class NightlyAutomationContract(unittest.TestCase):
    def test_nightly_archive_runs_before_nightly_site_rebuild(self):
        archive = schedules("archive-pregame.yml")
        deploy = schedules("deploy-pages.yml")
        self.assertEqual(archive, ["7 2 * 1,2,3,4,11,12 *", "7 6 * 1,2,3,4,11,12 *",
                                  "7 9 * 1,2,3,4,11,12 *", "7 16 * 1,2,3,4,11,12 *",
                                  "7 22 * 1,2,3,4,11,12 *",
                                  "7 18 * 1,2,3,4,11,12 1"])
        self.assertIn("47 2 * * *", deploy)
        self.assertIn("47 6 * 1,2,3,4,11,12 *", deploy)
        self.assertIn("17 10,17 * 1,2,3,4,11,12 *", deploy)
        self.assertIn("47 22 * 1,2,3,4,11,12 *", deploy)
        self.assertIn("47 18 * 1,2,3,4,11,12 1", deploy)
        archive_times, page_times = times(archive), times(deploy)
        for hour, minute in ((2, 47), (6, 47), (10, 17), (17, 17), (22, 47)):
            self.assertIn((hour, minute), page_times)
            preceding = {(2, 7), (6, 7), (9, 7), (16, 7), (22, 7)}
            self.assertTrue(
                any(0 < 60 * hour + minute - (60 * ah + am) <= 75
                    for ah, am in archive_times & preceding),
                msg=f"Site build {hour:02}:{minute:02} lacks preceding forecast archive",
            )

    def test_archive_triggers_site_and_commits_only_verified_ledger(self):
        archive = (WORKFLOWS / "archive-pregame.yml").read_text(encoding="utf-8")
        deploy = (WORKFLOWS / "deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("python -m forecast.recent_finals", deploy)
        self.assertIn("python -m forecast.snapshot", archive)
        self.assertIn("python -m forecast.ap_poll", archive)
        self.assertIn("git add web/public/forecasts web/public/research/ap-poll-history.json", archive)
        self.assertIn("python -m forecast.audit", archive)
        self.assertIn("git add web/public/forecasts", archive)
        self.assertIn('workflows: ["Archive real pre-tipoff forecasts"]', deploy)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", deploy)

    def test_elo2_is_research_only_and_does_not_modify_operational_elo(self):
        deploy=(WORKFLOWS/"deploy-pages.yml").read_text(encoding="utf-8")
        archive=(WORKFLOWS/"archive-pregame.yml").read_text(encoding="utf-8")
        self.assertIn("python -m forecast.elo_v2_historical",deploy)
        self.assertIn("python -m forecast.elo_v2_current",deploy)
        self.assertIn("web/public/research/elo-v2-historical.json",deploy)
        self.assertIn("web/public/current/elo-v2-research.json",deploy)
        self.assertLess(deploy.index("python -m forecast.elo_v2_historical"),
                        deploy.index("python -m forecast.live"))
        self.assertLess(deploy.index("python -m forecast.live"),
                        deploy.index("python -m forecast.elo_v2_current"))
        self.assertLess(deploy.index("python -m forecast.elo_v2_current"),
                        deploy.index("python -m forecast.retrain"))
        self.assertIn("python -m forecast.live",archive)
        self.assertNotIn("forecast.elo_v2_current",archive)
        self.assertNotIn("forecast.elo_v2_historical",archive)
        self.assertIn("python -m forecast.snapshot",archive)

    def test_morning_monitor_catches_missing_overnight_settlement(self):
        monitor = (WORKFLOWS / "monitor-archive.yml").read_text(encoding="utf-8")
        self.assertEqual(schedules("monitor-archive.yml"),
                         ["41 3,7,11,18,23 * 1,2,3,4,11,12 *"])
        self.assertIn("--require-recent --max-age-hours 4", monitor)
        self.assertIn("if: failure()", monitor)
        self.assertIn("steps.freshness.outcome == 'failure'", monitor)
        self.assertIn("gh workflow run archive-pregame.yml --ref main", monitor)
        self.assertIn("actions: write", monitor)
        self.assertIn("gh run list --workflow archive-pregame.yml", monitor)
        self.assertIn('workflows: ["Deploy website to GitHub Pages"]', monitor)
        self.assertIn("gh issue close", monitor)


    def test_github_pages_artifact_metadata_and_bounded_fresh_retry(self):
        deploy = (WORKFLOWS / "deploy-pages.yml").read_text(encoding="utf-8")
        recovery = (WORKFLOWS / "recover-pages.yml").read_text(encoding="utf-8")
        self.assertIn("actions/upload-pages-artifact@v3", deploy)
        self.assertIn("actions/deploy-pages@v4", deploy)
        self.assertIn("Wait for Pages artifact metadata to become queryable", deploy)
        self.assertIn('.name == "github-pages"', deploy)
        self.assertIn("exit 1", deploy)  # fail closed without a unique artifact
        self.assertIn("actions: read", deploy)
        self.assertIn("error_count: 20", deploy)
        self.assertIn("timeout: 900000", deploy)
        self.assertIn("actions: write", recovery)
        self.assertIn("workflow_run.run_attempt == 1", recovery)
        self.assertIn("workflow_run.event != 'workflow_dispatch'", recovery)
        self.assertIn('failed_steps" != "Run actions/deploy-pages@v4"', recovery)
        self.assertIn('artifacts" != "1"', recovery)
        # Rerunning the SAME job reuploads a SECOND github-pages artifact,
        # which defeats deployment. Always use a fresh workflow_run.
        self.assertIn("gh workflow run deploy-pages.yml --ref main", recovery)
        self.assertNotIn("rerun-failed-jobs", recovery)
        self.assertNotIn("gh run rerun", recovery)

    def test_archiver_is_safe_for_watchdog_dispatch(self):
        archive = (WORKFLOWS / "archive-pregame.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", archive)
        self.assertIn("cancel-in-progress: false", archive)
        self.assertIn("python -m forecast.snapshot", archive)
        self.assertIn("python -m forecast.audit", archive)
        self.assertIn("git rebase origin/main", archive)
        self.assertNotIn("--force", archive)


if __name__ == "__main__":
    unittest.main()

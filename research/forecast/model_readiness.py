"""Conservative, auditable model-readiness review of immutable forward forecasts.

Never trains or promotes a model. Works from the independently settled,
first-published paired comparisons in accuracy_research. Historical studies
are supporting evidence, not substitutes for prospective performance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from .accuracy_research import derive

MIN_GAMES = 150
MIN_DATES = 20
MIN_GAIN = .002
MAX_ECE = .06
MIN_CALIBRATION_GAMES = 100


def assess(report: dict) -> dict:
    if report.get("mode") != "first-pick-forward-research" or report.get("autoPromoted") is not False:
        raise ValueError("Expected immutable first-pick forward research, not a trained or promoted model")
    comparisons = report.get("pairedComparisons")
    if not isinstance(comparisons, list):
        raise ValueError("Missing paired comparison evidence")
    results = []
    for row in comparisons:
        name = row["model"]
        n = row["pairedGames"]
        days = row["pairedDays"]
        gain = row.get("brierGain")
        interval = row.get("dateBlockGain95")
        reasons = []
        if n < MIN_GAMES:
            reasons.append("insufficient paired settled games")
        if days < MIN_DATES:
            reasons.append("insufficient independent game dates")
        if gain is None or gain < MIN_GAIN:
            reasons.append("insufficient paired Brier improvement")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] <= 0:
            reasons.append("no strictly positive date-block 95% interval")
        # Overall calibration does not establish candidate calibration. Require
        # separately archived, candidate-specific reliability before promotion.
        reasons.append("candidate-specific forward calibration not independently certified")
        results.append({
            "model": name, "pairedGames": n, "pairedDates": days,
            "brierGain": gain, "gainDateBlock95": interval,
            "readyForPromotion": False, "blockers": reasons,
        })
    calibration = report.get("calibrationDiagnostics") or {}
    overall = {
        "settledGames": report.get("verifiedUniqueFinals", 0),
        "ece": calibration.get("expectedCalibrationError"),
        "calibrationSampleSufficient": calibration.get("games", 0) >= MIN_CALIBRATION_GAMES,
        "baselineCalibrationWithinTolerance": (
            calibration.get("games", 0) >= MIN_CALIBRATION_GAMES
            and calibration.get("expectedCalibrationError") is not None
            and calibration["expectedCalibrationError"] <= MAX_ECE
        ),
    }
    return {
        "schemaVersion": 1, "mode": "read-only-promotion-audit",
        "generatedAtUtc": report.get("generatedAtUtc"),
        "baseline": overall, "challengers": results,
        "automaticPromotion": False,
        "requiredEvidence": {
            "minimumPairedGames": MIN_GAMES, "minimumPairedDates": MIN_DATES,
            "minimumBrierGain": MIN_GAIN, "positiveDateBlock95LowerBound": True,
            "minimumCalibrationGames": MIN_CALIBRATION_GAMES,
            "maximumBaselineECE": MAX_ECE,
            "candidateSpecificCalibration": "required but not yet independently provided",
            "historicalOutOfSeasonValidation": "required for any production change",
            "verifiedIdentityAndPredictionCoverage": "required for any production change",
        },
        "limitations": [
            "Candidate calibration, historical season robustness and verified coverage are separate gates; none is silently inferred from a positive Brier gain.",
            "This audit cannot authorize promotion. It never modifies the production forecaster or immutable snapshots.",
            "Insufficient samples are unknown evidence, not evidence of model failure.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", type=Path, default=Path("web/public/forecasts"))
    p.add_argument("--out", type=Path, default=Path("web/public/current/model-readiness.json"))
    a = p.parse_args()
    result = assess(derive(a.ledger))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"challengers": len(result["challengers"]),
                      "eligible": sum(x["readyForPromotion"] for x in result["challengers"])}))


if __name__ == "__main__":
    main()

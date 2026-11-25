"""Model promotion must fail closed when evidence is absent or incomplete."""
import unittest
from research.forecast.model_readiness import assess


def report(**overrides):
    row = {"model": "Fixed state-space", "pairedGames": 200, "pairedDays": 30,
           "brierGain": .006, "dateBlockGain95": [.001, .011]}
    row.update(overrides)
    return {"mode": "first-pick-forward-research", "autoPromoted": False,
            "verifiedUniqueFinals": 220,
            "calibrationDiagnostics": {"games": 220, "expectedCalibrationError": .03},
            "pairedComparisons": [row]}


class ReadinessTests(unittest.TestCase):
    def test_strong_brier_alone_never_promotes_without_candidate_calibration(self):
        r = assess(report())
        self.assertFalse(r["challengers"][0]["readyForPromotion"])
        self.assertIn("candidate-specific forward calibration not independently certified",
                      r["challengers"][0]["blockers"])
        self.assertFalse(r["automaticPromotion"])

    def test_low_sample_and_interval_are_explicit_blockers(self):
        r = assess(report(pairedGames=20, pairedDays=3, brierGain=-.01,
                          dateBlockGain95=[-.02, .01]))["challengers"][0]
        self.assertGreaterEqual(len(r["blockers"]), 5)

    def test_rejects_nonforward_or_promoted_input(self):
        with self.assertRaises(ValueError):
            assess({**report(), "mode": "historical-backtest"})
        with self.assertRaises(ValueError):
            assess({**report(), "autoPromoted": True})

    def test_empty_comparisons_valid_and_never_promotes(self):
        r = assess({**report(), "pairedComparisons": []})
        self.assertEqual(r["challengers"], [])
        self.assertFalse(r["automaticPromotion"])


if __name__ == "__main__":
    unittest.main()

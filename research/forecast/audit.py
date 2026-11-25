"""Offline integrity audit of committed immutable prediction/settlement evidence.

The archival workflow can only add a match to the public scoreboard when:
- a snapshot file proves a forecast was generated ahead of the scheduled start
- its current-season rating snapshot was retrieved by the claimed forecast time
- the settlement is unique and refers to a real original snapshot prediction
- the stored Brier/log loss/accuracy equals the deterministic result

This validation checks *internal evidence* only. It cannot independently certify
external API content or guarantee the event actually began at the listed time.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import timedelta
from pathlib import Path

from .snapshot import BUFFER_MINUTES, parse_time


def _read_all(folder: Path) -> list[tuple[Path, dict]]:
    output = []
    for path in sorted(folder.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unreadable ledger JSON: {path.name}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"Ledger entry must be a JSON object: {path.name}")
        output.append((path, obj))
    return output


def audit_ledger(folder: Path) -> dict:
    """Recompute derived metrics and verify append-only archive integrity."""
    folder = Path(folder)
    sources = _read_all(folder / "snapshots")
    settlements = _read_all(folder / "settlements")
    raw_index = folder / "index.json"
    if raw_index.exists():
        index = json.loads(raw_index.read_text(encoding="utf-8"))
    else:
        index = None
    original: dict[str, tuple[dict, dict]] = {}
    for path, snap in sources:
        if not isinstance(snap.get("predictions"), list):
            raise ValueError(f"Snapshot missing predictions: {path.name}")
        created = parse_time(snap["generatedAtUtc"])
        retrieved = parse_time(snap["ratingRetrievedAtUtc"])
        if retrieved > created:
            raise ValueError(f"Rating newer than forecast: {path.name}")
        buffer_minutes = int(snap.get("timeBufferMinutes", -1))
        if buffer_minutes < BUFFER_MINUTES or buffer_minutes > 360:
            raise ValueError(f"Invalid forecast time buffer: {path.name}")
        if snap.get("snapshotId") != path.stem:
            raise ValueError(f"Snapshot filename/id mismatch: {path.name}")
        for pred in snap["predictions"]:
            key = snap["snapshotId"] + ":" + str(pred["eventId"])
            if key in original:
                raise ValueError(f"Duplicate pregame snapshot prediction {key}")
            model_day = pred.get("modelTrainingThroughDate")
            if model_day is not None and model_day >= pred["scheduledEasternDate"]:
                raise ValueError(f"Online model training reaches forecast day: {key}")
            if pred.get("model") == "chronologically validated in-season logistic":
                if not model_day or not pred.get("modelId"):
                    raise ValueError(f"Trained forecast lacks as-of model provenance: {key}")
            start = parse_time(pred["scheduledStartUtc"])
            if created + timedelta(minutes=buffer_minutes) >= start:
                raise ValueError(f"Forecast not before tip-off buffer: {key}")
            p = float(pred["homeWinProbability"])
            q = float(pred["awayWinProbability"])
            if not (math.isfinite(p) and math.isfinite(q) and 0 < p < 1
                    and 0 < q < 1 and abs(p + q - 1) < 0.00001):
                raise ValueError(f"Invalid probability complement: {key}")
            for field in ("baselineHomeWinProbability","challengerHomeWinProbability",
                          "stateSpaceHomeWinProbability"):
                if pred.get(field) is not None:
                    candidate=float(pred[field])
                    if not math.isfinite(candidate) or not 0<candidate<1:
                        raise ValueError(f"Unscorable frozen challenger probability: {key}")
            # Elo3 candidate can only be scored with matching first-pick
            # metadata, prior-date cutoff, and finite original probability.
            e3=pred.get("elo3HomeWinProbability")
            evidence=pred.get("elo3Research")
            if (e3 is None)!=(evidence is None):
                raise ValueError(f"Elo3 probability/provenance missing pair: {key}")
            if e3 is not None:
                if type(e3) not in (int,float) or not math.isfinite(e3) or not 0<e3<1:
                    raise ValueError(f"Invalid frozen Elo3 probability: {key}")
                if not isinstance(evidence,dict) or evidence.get("modelVersion")!="elo3-prospective-shadow-v1":
                    raise ValueError(f"Invalid Elo3 research model identity: {key}")
                if (evidence.get("ratingRetrievedAtUtc")!=snap["ratingRetrievedAtUtc"] or
                    evidence.get("boxRetrievedAtUtc")!=snap["ratingRetrievedAtUtc"] or
                    evidence.get("ratingCutoffExclusive")!=pred["scheduledEasternDate"] or
                    evidence.get("preseasonPriorPolicy")!="neutral-2027-until-verified-crossyear-ID"):
                    raise ValueError(f"Unmatched Elo3 source metadata or date: {key}")
                trained=evidence.get("trainedThroughDate")
                if trained is not None and (not isinstance(trained,str) or
                                            trained>=pred["scheduledEasternDate"]):
                    raise ValueError(f"Elo3 training leaks forecast date: {key}")
                for field in ("sourceGames","pairedBoxGames","fourFactorTeamGames"):
                    value=evidence.get(field)
                    if type(value) is not int or value<0:
                        raise ValueError(f"Invalid Elo3 source coverage metadata: {key}")
                if (evidence["pairedBoxGames"]>evidence["sourceGames"] or
                    (trained is None and evidence["sourceGames"]>0)):
                    raise ValueError(f"Inconsistent Elo3 pregame evidence: {key}")
                for field,lo,hi in (("temperature",.5,2.0),("homeAdvantage",0.,150.)):
                    value=evidence.get(field)
                    if type(value) not in (float,int) or not math.isfinite(value) or not lo<=value<=hi:
                        raise ValueError(f"Invalid Elo3 learned setting: {key}")
            # New v1.9 score shadows are optional, but when a forecast is
            # published the frozen source-backed points must be internally
            # consistent. Earlier snapshots contain no score forecast.
            projection = pred.get("researchScoreProjection")
            if projection is not None:
                if (not isinstance(projection,dict) or
                    projection.get("schemaVersion")!=1 or
                    projection.get("modelVersion")!="source-scoring-shadow-v1" or
                    projection.get("method") not in ("opponent-adjusted-possessions","raw-scoring-means")):
                    raise ValueError(f"Invalid frozen score model metadata: {key}")
                try:
                    home_points=float(projection["projectedHomeScore"])
                    away_points=float(projection["projectedAwayScore"])
                    margin=float(projection["projectedMargin"])
                    total=float(projection["projectedTotal"])
                except (KeyError,TypeError,ValueError) as exc:
                    raise ValueError(f"Incomplete frozen score prediction: {key}") from exc
                if (not all(math.isfinite(x) for x in (home_points,away_points,margin,total)) or
                    not (0<home_points<200 and 0<away_points<200) or
                    abs((home_points-away_points)-margin)>.11 or
                    abs((home_points+away_points)-total)>.11):
                    raise ValueError(f"Frozen score arithmetic mismatch: {key}")
            original[key] = (snap, pred)
    scored: list[dict] = []
    seen: set[str] = set()
    for path, group in settlements:
        settled_at = parse_time(group["generatedAtUtc"])
        if not isinstance(group.get("results"), list):
            raise ValueError(f"Settlement missing results: {path.name}")
        for row in group["results"]:
            key = row["predictionKey"]
            if key in seen:
                raise ValueError(f"Duplicate settled forecast {key}")
            seen.add(key)
            if key not in original:
                raise ValueError(f"Settlement without original forecast {key}")
            snap, pred = original[key]
            start = parse_time(pred["scheduledStartUtc"])
            if settled_at <= start:
                raise ValueError(f"Settlement predates scheduled tip-off: {key}")
            if row["snapshotId"] != snap["snapshotId"] or row["eventId"] != pred["eventId"]:
                raise ValueError(f"Settlement identity mismatch: {key}")
            if parse_time(row["forecastAtUtc"]) != parse_time(snap["generatedAtUtc"]):
                raise ValueError(f"Settlement forecast timestamp mismatch: {key}")
            if parse_time(row["scheduledStartUtc"]) != start:
                raise ValueError(f"Settlement scheduled time mismatch: {key}")
            if str(row["home"]) != str(pred["home"]) or str(row["away"]) != str(pred["away"]):
                raise ValueError(f"Settlement team mismatch: {key}")
            p = float(pred["homeWinProbability"])
            if abs(float(row["predictedHome"]) - p) > 0.0000001:
                raise ValueError(f"Settlement probability changed: {key}")
            y = int(row["observedHome"])
            if y not in (0, 1):
                raise ValueError(f"Invalid observed outcome: {key}")
            if (int(row["homeScore"]) > int(row["awayScore"])) != bool(y) or int(row["homeScore"]) == int(row["awayScore"]):
                raise ValueError(f"Settlement contradicts final score: {key}")
            brier = (p-y)**2
            loss = -math.log(p if y else 1-p)
            accuracy = float(int((p > .5 and y == 1) or (p < .5 and y == 0))) if p != .5 else .5
            if (abs(float(row["brier"]) - brier) > .000001 or
                abs(float(row["logLoss"]) - loss) > .000001 or
                abs(float(row["winnerCorrect"]) - accuracy) > .000001):
                raise ValueError(f"Settlement probability scoring mismatch: {key}")
            scored.append(row)
    metrics = {
        "settledPredictions": len(scored),
        "brier": round(sum(float(r["brier"]) for r in scored)/len(scored),6) if scored else None,
        "logLoss": round(sum(float(r["logLoss"]) for r in scored)/len(scored),6) if scored else None,
        "winnerAccuracy": round(sum(float(r["winnerCorrect"]) for r in scored)/len(scored),6) if scored else None,
    }
    if index is not None:
        health = index.get("archiveHealth")
        if health is not None:
            if health.get("everArchivedPredictions") != len(original):
                raise ValueError("Public archive health prediction count mismatches immutable files")
            if not isinstance(health.get("sourceWarnings"), list):
                raise ValueError("Archive health source warnings must be a list")
            if health.get("verifiedNewSettlements", 0) > len(scored):
                raise ValueError("Archive health settlement count exceeds source evidence")
        if index.get("uniqueGames") is not None:
            from .performance import summarize_forward
            expected=summarize_forward([s for _,s in sources],scored)
            archived=index["uniqueGames"]
            # Schema evolution: older immutable-index revisions were built
            # before the additive, source-derived verifiedOutcomes table.
            # Every previously archived field must STILL match recomputation
            # exactly; when new outcomes are published, they too are verified.
            allowed_missing={"verifiedOutcomes"}
            if (set(archived)-set(expected) or
                (set(expected)-set(archived))-allowed_missing or
                any(expected[k]!=v for k,v in archived.items())):
                raise ValueError("Unique-game forward scoring differs from immutable evidence")
        if index.get("scores") != metrics:
            raise ValueError("Public index metrics disagree with immutable settlement entries")
        snapshot_summary = index.get("snapshots", [])
        if any(item["id"] not in {s["snapshotId"] for _, s in sources} for item in snapshot_summary):
            raise ValueError("Public index references missing snapshot")
        for r in index.get("settlements", []):
            if r["predictionKey"] not in seen:
                raise ValueError("Public index contains non-archived settlement")
    return {"status": "verified", "snapshots": len(sources),
            "predictions": len(original), "settlements": len(settlements),
            "settledPredictions": len(scored), "scores": metrics,
            "warning": "Internal evidence validated; source and actual start time are not independently certified."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path("web/public/forecasts"))
    args = parser.parse_args()
    print(json.dumps(audit_ledger(args.dir), indent=2))


if __name__ == "__main__":
    main()

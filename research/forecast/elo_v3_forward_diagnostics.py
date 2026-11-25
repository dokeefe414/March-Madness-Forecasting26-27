"""Auditable *prospective* Elo 3.0 cohort diagnostics.

Uses original immutable first picks and their independently verified settlements
only. Never chooses the most favorable later forecast for an event. Intended
for monitoring disagreement, sample coverage, and fixed predeclared segments;
not evidence for model promotion by itself.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from .snapshot import parse_time

MODEL_VERSION = "elo3-prospective-shadow-v1"
# Bound enough evidence for descriptive segmentation; review promotion still
# uses the separate, more stringent original paired-date gate.
SEGMENT_MIN_GAMES = 30
SEGMENT_MIN_DATES = 6


def _probability(value):
    if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value < 1:
        raise ValueError("Invalid first-published Elo3/control probability")
    return float(value)


def _segment_strength(control):
    confidence = max(control, 1 - control)
    if confidence < .60:
        return "Close (50-59%)"
    if confidence < .75:
        return "Moderate favorite (60-74%)"
    return "Strong favorite (75%+)"


def _segment_gap(gap):
    if gap < .05:
        return "Under 5 pp"
    if gap < .10:
        return "5 to under 10 pp"
    return "10+ pp"


def _segment_lead(hours):
    if hours < 6:
        return "15 minutes to under 6 hours"
    if hours < 24:
        return "6 to under 24 hours"
    return "24+ hours"


def _metrics(rows):
    if not rows:
        return {"games": 0, "gameDates": 0, "baselineBrier": None,
                "elo3Brier": None, "brierGain": None, "baselineAccuracy": None,
                "elo3Accuracy": None, "status": "no-verified-pairs"}
    n = len(rows)
    def brier(key):
        return sum((r[key] - r["observedHome"])**2 for r in rows) / n
    def acc(key):
        return sum(.5 if r[key] == .5 else
                   float((r[key] > .5) == bool(r["observedHome"]))
                   for r in rows) / n
    baseline, challenger = brier("baseline"), brier("elo3")
    dates = len({r["day"] for r in rows})
    return {
        "games": n, "gameDates": dates,
        "baselineBrier": round(baseline, 6),
        "elo3Brier": round(challenger, 6),
        "brierGain": round(baseline - challenger, 6),
        "baselineAccuracy": round(acc("baseline"), 6),
        "elo3Accuracy": round(acc("elo3"), 6),
        "status": ("descriptive-only" if
                   n < SEGMENT_MIN_GAMES or dates < SEGMENT_MIN_DATES
                   else "sample-sufficient-for-descriptive-review"),
    }


def _segments(frozen, observed, category, labels):
    events = defaultdict(list)
    result = defaultdict(list)
    for row in frozen:
        events[row[category]].append(row)
    for row in observed:
        result[row[category]].append(row)
    return [{
        "segment": label,
        "firstFrozenPicks": len(events[label]),
        "unverifiedOrPending": len(events[label]) - len(result[label]),
        **_metrics(result[label]),
    } for label in labels]


def _calibration(observed):
    bands = []
    for low in (.5, .6, .7, .8, .9):
        high = round(low + .1, 5)
        selected = [r for r in observed if
                    low <= max(r["elo3"], 1 - r["elo3"]) <
                    (high if high < 1 else 1.000001)]
        correct = sum(.5 if x["elo3"] == .5 else
                      float((x["elo3"] > .5) == bool(x["observedHome"]))
                      for x in selected)
        expected = (sum(max(x["elo3"], 1-x["elo3"]) for x in selected)
                    / len(selected)) if selected else None
        actual = correct / len(selected) if selected else None
        bands.append({
            "confidenceRange": f"{int(low*100)}-{int(high*100)}%",
            "games": len(selected),
            "meanConfidence": round(expected, 6) if expected is not None else None,
            "realizedCorrect": round(actual, 6) if actual is not None else None,
        })
    if not observed:
        return {"games":0,"status":"no-verified-pairs","ece":None,"bins":bands}
    ece = sum(x["games"] * abs(x["meanConfidence"] - x["realizedCorrect"])
              for x in bands if x["games"]) / len(observed)
    return {"games": len(observed),
            "status":"descriptive-only" if len(observed)<100 else "monitoring",
            "ece": round(ece, 6), "bins": bands}


def derive(first:dict, snapshots:list[dict], outcomes:list[dict],
           pending:list[dict], now:datetime)->dict:
    """Distinct event-ID cohort: earliest original first pick, not latest shadow.

    'first' is assembled by the existing archive accuracy evaluator from all
    snapshots sorted by original capture time. 'outcomes' includes only ESPN
    STATUS_FINAL + matching NCAA source settlements of those first picks.
    """
    if now.tzinfo is None:
        raise ValueError("Prospective diagnostics require timezone-aware now")
    now = now.astimezone(timezone.utc)
    seen_shadow_events=set()
    raw_shadow_count=0
    shadow_created=[]
    for snap in snapshots:
        captured=parse_time(snap["generatedAtUtc"])
        for prediction in snap.get("predictions",[]):
            if prediction.get("elo3HomeWinProbability") is not None:
                _probability(prediction["elo3HomeWinProbability"])
                raw_shadow_count+=1
                seen_shadow_events.add(str(prediction["eventId"]))
                shadow_created.append(captured)
    launch=min(shadow_created,default=None)
    observed_by_id={str(row["eventId"]):row for row in outcomes}
    pending_by_id={str(row["eventId"]):row for row in pending}
    if len(observed_by_id)!=len(outcomes):
        raise ValueError("Duplicate settled first-pick event in Elo3 diagnostics")
    if len(pending_by_id)!=len(pending):
        raise ValueError("Duplicate pending first-pick event in Elo3 diagnostics")
    frozen=[]
    verified=[]
    post_launch_total=0
    post_launch_unpaired=0
    missing_eligible=[]
    for event_id,(snap,pred) in first.items():
        captured=parse_time(snap["generatedAtUtc"])
        if launch is not None and captured>=launch:
            post_launch_total+=1
            if pred.get("elo3HomeWinProbability") is None:
                post_launch_unpaired+=1
                if len(missing_eligible)<10:
                    missing_eligible.append({"eventId":event_id,
                        "home":pred["home"],"away":pred["away"],
                        "firstCapturedAtUtc":snap["generatedAtUtc"],
                        "reason":"Missing Elo3 in original first-published snapshot"})
        candidate=pred.get("elo3HomeWinProbability")
        if candidate is None:
            continue
        control=_probability(pred.get("baselineHomeWinProbability"))
        elo3=_probability(candidate)
        start=parse_time(pred["scheduledStartUtc"])
        lead=(start-captured).total_seconds()/3600
        if lead <= .25:
            raise ValueError("Elo3 first pick violates 15-minute pretipoff buffer")
        gap=abs(control-elo3)
        # A probability exactly 0.5 does not choose a winner.
        disagreement=(control!=.5 and elo3!=.5 and
                      (control>.5)!=(elo3>.5))
        row={"eventId":event_id,
             "day":pred["scheduledEasternDate"],
             "home":pred["home"],"away":pred["away"],
             "scheduledStartUtc":pred["scheduledStartUtc"],
             "firstCapturedAtUtc":snap["generatedAtUtc"],
             "baseline":control,"elo3":elo3,"absoluteGap":gap,
             "differentWinner":disagreement,
             "venue":"Neutral" if pred.get("neutralSite") else "Listed home",
             "baselineStrength":_segment_strength(control),
             "disagreementSize":_segment_gap(gap),
             "tipoffLead":_segment_lead(lead),
             "winnerAgreement":"Different picks" if disagreement else "Same pick / 50% tie",
             "status":pending_by_id.get(event_id,{}).get("status","verified"
                         if event_id in observed_by_id else "unverified")}
        frozen.append(row)
        if event_id in observed_by_id:
            actual=observed_by_id[event_id]
            y=actual["observedHome"]
            if y not in (0,1) or actual.get("Elo 3.0 prospective") is None:
                raise ValueError("Elo3 verified result missing candidate or outcome")
            if (abs(float(actual["Elo 3.0 prospective"])-elo3)>1e-7 or
                abs(float(actual["elo"])-control)>1e-7):
                raise ValueError("Verified Elo3/production Elo differs from original snapshot")
            verified.append({**row,"observedHome":y,
                             "day":actual["day"]})
    top=[r for r in frozen if parse_time(r["scheduledStartUtc"])>now]
    top.sort(key=lambda r:(-r["absoluteGap"],r["scheduledStartUtc"],r["eventId"]))
    top_rows=[{"eventId":r["eventId"],"home":r["home"],"away":r["away"],
               "scheduledStartUtc":r["scheduledStartUtc"],
               "baselineHomeWinProbability":round(r["baseline"],6),
               "elo3HomeWinProbability":round(r["elo3"],6),
               "differencePercentagePoints":round(100*r["absoluteGap"],2),
               "differentWinner":r["differentWinner"],
               "neutralSite":r["venue"]=="Neutral"} for r in top[:12]]
    gaps=sorted(row["absoluteGap"] for row in frozen)
    n=len(frozen)
    first_shadow_ids={row["eventId"] for row in frozen}
    pending_status=defaultdict(int)
    for row in frozen:
        if row["eventId"] not in observed_by_id:
            pending_status[row["status"]]+=1
    return {
        "schemaVersion":1,"type":"elo3-original-first-pick-diagnostics",
        "modelVersion":MODEL_VERSION,
        "status":"collecting" if n else "no-eligible-first-picks",
        "launchCapturedAtUtc":launch.isoformat().replace("+00:00","Z") if launch else None,
        "allCapturedShadowPredictions":raw_shadow_count,
        "distinctShadowCapturedEvents":len(seen_shadow_events),
        "eligibleOriginalFirstPicks":n,
        "eligibleOriginalFirstDates":len({r["day"] for r in frozen}),
        "afterLaunchOriginalFirstPicks":post_launch_total,
        "afterLaunchMissingShadow":post_launch_unpaired,
        "afterLaunchCandidateCoverage":round(
            (post_launch_total-post_launch_unpaired)/post_launch_total,6
        ) if post_launch_total else None,
        "laterOnlyShadowEventsExcluded":len(seen_shadow_events-first_shadow_ids),
        "examplesMissingAfterLaunch":missing_eligible,
        "verifiedPairedFinals":len(verified),
        "pendingOriginalFirstPicks":n-len(verified),
        "pendingByStatus":dict(sorted(pending_status.items())),
        "difference":{
            "meanPercentagePoints":round(
                100*sum(row["absoluteGap"] for row in frozen)/n,3) if n else None,
            "medianPercentagePoints":round(50*(gaps[(n-1)//2]+gaps[n//2]),3) if n else None,
            "differentWinnerPicks":sum(row["differentWinner"] for row in frozen),
            "differenceAtLeast10pp":sum(row["absoluteGap"]>=.1 for row in frozen),
        },
        "topUpcomingDisagreements":top_rows,
        "overallVerified":_metrics(verified),
        "calibration":_calibration(verified),
        "segments":{
            "baselineStrength":_segments(frozen,verified,"baselineStrength",
                ["Close (50-59%)","Moderate favorite (60-74%)","Strong favorite (75%+)"]),
            "disagreementSize":_segments(frozen,verified,"disagreementSize",
                ["Under 5 pp","5 to under 10 pp","10+ pp"]),
            "venue":_segments(frozen,verified,"venue",["Listed home","Neutral"]),
            "tipoffLead":_segments(frozen,verified,"tipoffLead",
                ["15 minutes to under 6 hours","6 to under 24 hours","24+ hours"]),
            "winnerAgreement":_segments(frozen,verified,"winnerAgreement",
                ["Same pick / 50% tie","Different picks"]),
        },
        "reviewOnly":True,"autoPromoted":False,
        "limitations":[
            "An Elo3 probability recorded in a later snapshot for an event with an older original first pick is excluded from the prospective accuracy cohort.",
            "Top disagreements are FIRST-PUBLISHED, UPCOMING predictions only and are NOT successes, losses, or wagering recommendations.",
            "Segment definitions were frozen in code, but any exploratory subgroup may be biased by selection and small sample size.",
            "No segment is inferential when fewer than 30 independently verified events or six independent game dates are present.",
            "Original first picks are only scored after independent ESPN STATUS_FINAL and matching NCAA scoreboard results.",
            "Future schedules can change; a stored scheduled tipoff is the originally observed ESPN start, not proof of actual start.",
        ],
    }

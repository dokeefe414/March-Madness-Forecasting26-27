"""Prospective accuracy center: original first picks, independently verified finals.

Read-only derivation from immutable snapshots and settlement files. Never
recompute an old pick, select a later improved model, or label an unmatched
scheduled fixture as a result. Reports daily/weekly reliability, strictly
paired frozen challenger-vs-Elo metrics, and *genuinely frozen* experimental
score errors where the score forecast actually existed before tipoff.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .snapshot import parse_time
from .performance import _rate

LOCAL=ZoneInfo("America/New_York")
FIELDS={
 "Online logistic challenger":"challengerHomeWinProbability",
 "Fixed state-space":"stateSpaceHomeWinProbability",
 "Adaptive state-space":"adaptiveStateSpaceHomeWinProbability",
 "Opponent adjusted":"opponentAdjustedHomeWinProbability",
 "Frozen ensemble":"ensembleHomeWinProbability",
 "Elo 3.0 prospective":"elo3HomeWinProbability",
}
MIN_INTERVAL_GAMES=40
MIN_INTERVAL_DATES=6

def _valid_probability(x:object)->float|None:
    if type(x) not in (float,int) or not math.isfinite(x) or not 0<x<1:
        return None
    return float(x)

def _metrics(rows:list[dict],field:str)->dict:
    subset=[r for r in rows if r.get(field) is not None]
    if not subset:return {"games":0,"brier":None,"logLoss":None,"accuracy":None}
    scores=[_rate(r[field],r["observedHome"]) for r in subset]
    n=len(scores)
    return {"games":n,"brier":round(sum(s["brier"] for s in scores)/n,6),
      "logLoss":round(sum(s["logLoss"] for s in scores)/n,6),
      "accuracy":round(sum(s["correct"] for s in scores)/n,6)}

def _interval(pairs:list[dict],seed:int=19027)->list[float]|None:
    by=defaultdict(list)
    for p in pairs:
        by[p["day"]].append((p["elo"]-p["observedHome"])**2-
                            (p["candidate"]-p["observedHome"])**2)
    if len(by)<MIN_INTERVAL_DATES or len(pairs)<MIN_INTERVAL_GAMES:return None
    days=sorted(by)
    rng=random.Random(seed)
    vals=[]
    for _ in range(700):
        sampled=[by[days[rng.randrange(len(days))]] for _ in days]
        all_errors=[x for group in sampled for x in group]
        vals.append(sum(all_errors)/len(all_errors))
    vals.sort()
    return [round(vals[17],6),round(vals[681],6)]

def _calibration(rows:list[dict],field:str)->dict:
    """Independent first-pick confidence reliability; empty means unknown."""
    valid=[r for r in rows if r.get(field) is not None]
    bins=[]
    for i in range(5):
        lo=.5+.1*i;hi=.5+.1*(i+1)
        group=[r for r in valid
               if lo<=max(r[field],1-r[field])<
                  (hi if i<4 else 1.000001)]
        if group:
            expected=sum(max(r[field],1-r[field]) for r in group)/len(group)
            observed=sum(float((r[field]>.5)==bool(r["observedHome"]))
                         if r[field]!=.5 else .5 for r in group)/len(group)
        else:expected=observed=None
        bins.append({"confidenceRange":f"{int(lo*100)}-{int(hi*100)}%",
          "games":len(group),"meanPredicted":round(expected,6) if expected is not None else None,
          "realizedCorrect":round(observed,6) if observed is not None else None,
          "gap":round(observed-expected,6) if observed is not None else None})
    ece=sum((b["games"]/len(valid))*abs(b["gap"]) for b in bins if b["games"]) if valid else None
    # A single low-volume reliability plot is not a calibrated distribution.
    status=("insufficient-evidence" if len(valid)<50
            else "observing")
    return {"status":status,"games":len(valid),
      "expectedCalibrationError":round(ece,6) if ece is not None else None,
      "bins":bins,
      "policy":"Descriptive confidence-band frequency for unique source-verified original first picks only; at least 50 needed for monitoring, not for an accuracy guarantee."}

def derive(folder:Path,now:datetime|None=None)->dict:
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshots=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((folder/"snapshots").glob("*.json"))]
    settlement_groups=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((folder/"settlements").glob("*.json"))]
    first={}
    for snap in sorted(snapshots,key=lambda s:(s["generatedAtUtc"],s["snapshotId"])):
        for pred in snap.get("predictions",[]):
            first.setdefault(str(pred["eventId"]),(snap,pred))
    verified={}
    for group in settlement_groups:
        for r in group.get("results",[]):
            key=str(r["predictionKey"])
            if key in verified and verified[key]!=r:raise ValueError("Conflicting original settlement receipt")
            if r.get("espnFinalVerified") is True:
                verified[key]=r
    outcomes=[]
    pending=[]
    for eid,(snap,pred) in first.items():
        key=snap["snapshotId"]+":"+eid
        start=parse_time(pred["scheduledStartUtc"])
        created=parse_time(snap["generatedAtUtc"])
        try:
            rated=parse_time(snap["ratingRetrievedAtUtc"])
        except (KeyError,TypeError,ValueError):
            raise ValueError("Earliest prediction has missing rating source provenance")
        if rated>created or created+timedelta(minutes=15)>=start:
            raise ValueError("Earliest snapshot violates pretipoff source and time guards")
        row=verified.get(key)
        if row is None:
            hrs=(now-start).total_seconds()/3600
            status=("upcoming" if hrs<0 else "recent-start" if hrs<5 else
                    "awaiting-final" if hrs<=48 else "delayed-review")
            pending.append({"eventId":eid,"date":pred.get("scheduledEasternDate"),
                "home":pred["home"],"away":pred["away"],"listedStartUtc":pred["scheduledStartUtc"],
                "status":status,"hoursSinceListedStart":round(max(0,hrs),1)})
            continue
        if row.get("eventId")!=eid or row.get("home")!=pred["home"] or row.get("away")!=pred["away"]:
            raise ValueError("Verified result's original matchup identity changed")
        h,a=int(row["homeScore"]),int(row["awayScore"])
        if h<=0 or a<=0 or h==a:raise ValueError("Invalid independently verified final score")
        y=int(h>a)
        if y!=row["observedHome"]:raise ValueError("Outcome and independently verified score disagree")
        day=row["actualResultDate"]
        baseline=_valid_probability(pred.get("baselineHomeWinProbability"))
        official=_valid_probability(pred.get("homeWinProbability"))
        if official is None:raise ValueError("Original active probability missing")
        alternatives={label:_valid_probability(pred.get(field)) for label,field in FIELDS.items()}
        score=pred.get("researchScoreProjection")
        shadow=None
        if score is not None:
            if score.get("schemaVersion")!=1 or score.get("modelVersion")!="source-scoring-shadow-v1":
                raise ValueError("Unsupported original frozen scoring model")
            sh=score.get("projectedHomeScore")
            sa=score.get("projectedAwayScore")
            if not all(type(z) in (int,float) and math.isfinite(z) and z>0 for z in (sh,sa)):
                raise ValueError("Invalid archived scoring projection")
            shadow={"method":score["method"],"homeProjected":sh,"awayProjected":sa,
                "marginError":round(abs((sh-sa)-(h-a)),5),
                "totalError":round(abs((sh+sa)-(h+a)),5),
                "homeScoreError":round(abs(sh-h),5),"awayScoreError":round(abs(sa-a),5)}
        outcomes.append({"eventId":eid,"day":day,"weekStart":datetime.fromisoformat(day).date().strftime("%G-W%V"),
          "home":pred["home"],"away":pred["away"],"observedHome":y,
          "homeScore":h,"awayScore":a,
          "forecastAtUtc":snap["generatedAtUtc"],
          "official":official,"elo":baseline,**alternatives,
          "ratingMethodVersion":pred.get("ratingMethodVersion") or "pre-v2.1-unversioned",
          "scoreShadow":shadow})
    outcomes.sort(key=lambda o:(o["day"],o["eventId"]))
    def group(rows:list[dict],field:str):
        by=defaultdict(list)
        for r in rows:by[r[field]].append(r)
        return [{"period":period,**_metrics(items,"official"),"upsets":sum(
           int((r["official"]>.5)!=(r["observedHome"]==1))
           for r in items if r["official"]!=.5)}
           for period,items in sorted(by.items())]
    comparisons=[]
    for label in ["Online logistic challenger","Fixed state-space","Adaptive state-space",
                  "Opponent adjusted","Frozen ensemble","Elo 3.0 prospective"]:
        paired=[dict(r,candidate=r[label]) for r in outcomes
                if r["elo"] is not None and r[label] is not None]
        e=_metrics(paired,"elo")
        c=_metrics(paired,"candidate")
        gain=(round(e["brier"]-c["brier"],6) if paired else None)
        ci=_interval(paired)
        comparisons.append({"model":label,"pairedGames":len(paired),"pairedDays":len({r["day"] for r in paired}),
          "eloBrier":e["brier"],"candidateBrier":c["brier"],
          "eloAccuracy":e["accuracy"],"candidateAccuracy":c["accuracy"],
          "brierGain":gain,"dateBlockGain95":ci,
          "reviewEligible":bool(len(paired)>=100 and len({r["day"] for r in paired})>=12 and
                  gain is not None and gain>=.002 and ci is not None and ci[0]>0),
          "autoPromoted":False})
    # Only the EARLIEST original snapshot for each game is eligible.
    shadow_picks=[(s,p) for s,p in first.values()
                  if p.get("elo3HomeWinProbability") is not None]
    for s,p in shadow_picks:
        meta=p.get("elo3Research")
        if (not isinstance(meta,dict) or
            meta.get("modelVersion")!="elo3-prospective-shadow-v1" or
            meta.get("ratingRetrievedAtUtc")!=s["ratingRetrievedAtUtc"] or
            meta.get("boxRetrievedAtUtc")!=s["ratingRetrievedAtUtc"] or
            meta.get("ratingCutoffExclusive")!=p["scheduledEasternDate"] or
            (meta.get("trainedThroughDate") is not None and
             meta["trainedThroughDate"]>=p["scheduledEasternDate"])):
            raise ValueError("Prospective Elo3 original first-pick provenance mismatch")
        if _valid_probability(p["elo3HomeWinProbability"]) is None:
            raise ValueError("Prospective Elo3 original first-pick probability invalid")
    elo3_comparison=next(c for c in comparisons if c["model"]=="Elo 3.0 prospective")
    prospective_elo3={
        "status":"review-eligible" if elo3_comparison["reviewEligible"] else
                 "collecting-first-published-evidence",
        "modelVersion":"elo3-prospective-shadow-v1",
        "firstFrozenPicks":len(shadow_picks),
        "firstFrozenDates":len({p["scheduledEasternDate"] for _,p in shadow_picks}),
        "firstCaptureUtc":min((s["generatedAtUtc"] for s,p in shadow_picks),default=None),
        "lastCaptureUtc":max((s["generatedAtUtc"] for s,p in shadow_picks),default=None),
        "verifiedPairedFinals":elo3_comparison["pairedGames"],
        "pendingOriginalFirstPicks":len(shadow_picks)-elo3_comparison["pairedGames"],
        "pairedComparison":elo3_comparison,
        "onlyEarliestFirstPick":True,"retrospectiveBackfill":False,
        "activePredictorReplaced":False,
        "note":"Elo3 is frozen before listed tipoff alongside contemporaneous baseline Elo. Independent ESPN STATUS_FINAL plus matching NCAA score required. Earlier first picks cannot acquire Elo3 later.",
    }
    shadow=[r for r in outcomes if r["scoreShadow"] is not None]
    score_metrics={"games":len(shadow),
      "marginMAE":round(sum(r["scoreShadow"]["marginError"] for r in shadow)/len(shadow),5) if shadow else None,
      "totalMAE":round(sum(r["scoreShadow"]["totalError"] for r in shadow)/len(shadow),5) if shadow else None,
      "homeScoreMAE":round(sum(r["scoreShadow"]["homeScoreError"] for r in shadow)/len(shadow),5) if shadow else None,
      "awayScoreMAE":round(sum(r["scoreShadow"]["awayScoreError"] for r in shadow)/len(shadow),5) if shadow else None,
      "byMethod":[{"method":method,"games":len(items),
          "marginMAE":round(sum(r["scoreShadow"]["marginError"] for r in items)/len(items),5),
          "totalMAE":round(sum(r["scoreShadow"]["totalError"] for r in items)/len(items),5)}
          for method,items in sorted(((k,[r for r in shadow if r["scoreShadow"]["method"]==k])
          for k in {r["scoreShadow"]["method"] for r in shadow}))]}
    status={k:sum(p["status"]==k for p in pending) for k in
            ("upcoming","recent-start","awaiting-final","delayed-review")}
    archive_file=folder/"index.json"
    archive=json.loads(archive_file.read_text(encoding="utf-8")) if archive_file.exists() else {}
    health=archive.get("archiveHealth") or {}
    return {"schemaVersion":1,"mode":"first-pick-forward-research",
      "generatedAtUtc":now.isoformat().replace("+00:00","Z"),
      "archiveGeneratedAtUtc":archive.get("generatedAtUtc"),
      "immutableFirstPicks":len(first),"verifiedUniqueFinals":len(outcomes),
      "pendingUniqueGames":len(pending),"pendingByStatus":status,
      "pendingReview":sorted((p for p in pending if p["status"]=="delayed-review"),
                              key=lambda p:p["listedStartUtc"])[:35],
      "verification":{"independentESPNFinalRequired":True,"matchingNCAAScoreRequired":True,
        "esponFinalsInspectedInLastArchive":health.get("completedEspnEventsChecked"),
        "sourceWarnings":health.get("sourceWarnings",[]),
        "observedScheduleChanges":health.get("observedScheduleChanges",[])},
      "overall":_metrics(outcomes,"official"),
      "calibrationDiagnostics":_calibration(outcomes,"official"),
      "eloCalibrationDiagnostics":_calibration(outcomes,"elo"),
      "byRatingVersion":[{
         "version":version,"firstPicks":len(items),
         **_metrics(items,"official"),
         "latestGameDate":max(r["day"] for r in items),
         "calibrationStatus":_calibration(items,"official")["status"]
       } for version,items in sorted((
         (k,[r for r in outcomes if r["ratingMethodVersion"]==k])
         for k in {r["ratingMethodVersion"] for r in outcomes}))],
      "daily":group(outcomes,"day"),
      "weekly":group(outcomes,"weekStart"),
      "pairedComparisons":comparisons,
      "prospectiveElo3":prospective_elo3,
      "frozenScoreResults":score_metrics,
      "reviewOnly":True,"autoPromoted":False,
      "policy":"Only unique earliest source-timestamped predictions with independent ESPN final and matching NCAA score; frozen research shadow scores only when present at original tipoff. Never backfill or change an official pick.",
      "limitations":["An upcoming scheduled event is not known to have started or finished.",
        "A pending result is NOT a model loss, and a scheduled start does not independently verify a final.",
        "Rating model versions are tracked separately; version-specific cohorts are nonrandom and cannot imply causal superiority without a paired forward evaluation.",
        "Paired model intervals require enough settled independent game dates; no claim follows from a small sample.",
        "Missing original frozen score predictions cannot be reconstructed after the result."]}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger",type=Path,default=Path("web/public/forecasts"))
    parser.add_argument("--out",type=Path,default=Path("web/public/current/accuracy-research.json"))
    args=parser.parse_args()
    report=derive(args.ledger)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"originalPicks":report["immutableFirstPicks"],"verifiedFinals":report["verifiedUniqueFinals"],
                      "pairedModels":len(report["pairedComparisons"]),"frozenScoring":report["frozenScoreResults"]["games"]}))
if __name__=="__main__":main()

"""Strictly out-of-season Elo 2.0 evaluation from pinned Kaggle regular-season scores.

Historical evaluation uses the same *games* for all four models. The first
model is the existing production GameAwareEloEngine (K=24, home=65,
bounded margin). Three research challengers isolate carryover, strength
of schedule and their combination. The previous-season rating prior is
calculated entirely from seasons < target season (same Kaggle team IDs).

Source is a fixed published Git commit, not a rolling provider. Current
source can be passed as a local CSV for offline reproducibility.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from urllib.request import Request,urlopen

from .core import Game
from .elo_v2 import (Elo2Engine,preseason_priors,paired_metrics,
                     PRIOR_WEIGHT,SOS_WEIGHT,PRIOR_CAP,SOS_CAP)
from .game_aware_elo import GameAwareEloEngine
from .history import SOURCE_COMMIT

URL=(f"https://raw.githubusercontent.com/Andreachurchwell/"
     f"march-madness-bracket-simulator/{SOURCE_COMMIT}/"
     "data/raw/MRegularSeasonCompactResults.csv")
MAX_BYTES=25_000_000
HOLDOUT_YEARS=tuple(range(2016,2026))
SEED=62027
BOOTSTRAPS=800


def read_games(content:bytes) -> tuple[dict[int,list[Game]],str]:
    if len(content)>MAX_BYTES:
        raise ValueError("Pinned Kaggle compact-results file exceeds max size")
    digest=hashlib.sha256(content).hexdigest()
    reader=csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required={"Season","DayNum","WTeamID","WScore","LTeamID","LScore","WLoc"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Historical source missing mandatory columns")
    years:dict[int,list[Game]]=defaultdict(list)
    for row in reader:
        season=int(row["Season"])
        if not 1985<=season<=2026:
            continue
        game=Game(season,int(row["DayNum"]),int(row["WTeamID"]),
                  int(row["LTeamID"]),int(row["WScore"]),
                  int(row["LScore"]),row["WLoc"],
                  # Name stable across reruns; no duplicate day/pair allowed
                  contest_id=f"{season}-{row['DayNum']}-{min(row['WTeamID'],row['LTeamID'])}-{max(row['WTeamID'],row['LTeamID'])}")
        years[season].append(game)
    for season,group in years.items():
        if len({g.contest_id for g in group})!=len(group):
            raise ValueError(f"Duplicate historical contest {season}")
    return dict(years),digest


def download()->bytes:
    req=Request(URL,headers={"User-Agent":"MarchForecastResearch/2.0",
                            "Accept":"text/csv"})
    with urlopen(req,timeout=50) as response:
        result=response.read(MAX_BYTES+1)
    if len(result)>MAX_BYTES:
        raise ValueError("Historical compact results exceed maximum source limit")
    return result


def _confidence(years:list[dict],key:str)->list[float]|None:
    """Season-block bootstrap for mean paired Brier gain, descriptive only."""
    season_rows=[(r["variants"][key]["brierGain"],
                 r["variants"][key]["games"]) for r in years
                 if r["variants"][key]["games"]]
    if len(season_rows)<5:
        return None
    rng=random.Random(SEED)
    draws=[]
    for _ in range(BOOTSTRAPS):
        sample=[season_rows[rng.randrange(len(season_rows))]
                for _ in season_rows]
        draws.append(sum(gain*n for gain,n in sample)/
                     sum(n for _,n in sample))
    draws.sort()
    return [round(draws[int(.025*(len(draws)-1))],6),
            round(draws[int(.975*(len(draws)-1))],6)]


def _aggregate(rows:list[dict],variant:str,subkey:str="variants")->dict:
    records=[r[subkey][variant] for r in rows if r[subkey][variant]["games"]]
    n=sum(r["games"] for r in records)
    if not n:
        return {"games":0,"baselineBrier":None,"challengerBrier":None,
                "brierGain":None,"baselineAccuracy":None,
                "challengerAccuracy":None}
    fields=["baselineBrier","challengerBrier",
            "baselineAccuracy","challengerAccuracy",
            "baselineLogLoss","challengerLogLoss"]
    out={"games":n}
    for field in fields:
        out[field]=round(sum(r[field]*r["games"] for r in records)/n,6)
    out["brierGain"]=round(out["baselineBrier"]-out["challengerBrier"],6)
    # Aggregate actual sufficient statistics from SAME fixtures across
    # historical years, rather than averaging five-bin ECE percentages
    # computed on different year-specific bin populations.
    for source,dest in (("baselineCalibrationBins","baselineECE"),
                        ("challengerCalibrationBins","challengerECE")):
        total=[[0,0.0,0.0] for _ in range(5)]
        for row in records:
            for idx,(count,forecast_sum,actual_sum) in enumerate(row[source]):
                total[idx][0]+=count
                total[idx][1]+=forecast_sum
                total[idx][2]+=actual_sum
        out[dest]=round(sum(abs(pred/c-actual/c)*c
                            for c,pred,actual in total if c)/n,6)
        out[source]=[[int(c),round(pred,5),round(actual,5)]
                     for c,pred,actual in total]
    return out


def evaluate(grouped:dict[int,list[Game]],digest:str,
             holdouts:tuple[int,...]=HOLDOUT_YEARS)->dict:
    if not holdouts or tuple(sorted(set(holdouts)))!=holdouts:
        raise ValueError("Historical holdouts must be ordered unique years")
    # Need complete prior regular seasons to construct honest carryover.
    years=[]
    for year in holdouts:
        if year-1 not in grouped or year not in grouped:
            continue
        previous=grouped[year-1]
        test=grouped[year]
        if max(g.day_num for g in previous)<132 or max(g.day_num for g in test)<132:
            continue  # incomplete 2026 snapshot cannot enter a full-year test
        names={}
        ids={g.winner for g in test}|{g.loser for g in test}
        prior_engine=GameAwareEloEngine().fit(previous,{})
        prior=preseason_priors({tid:x.rating for tid,x in prior_engine.states.items()},ids)
        base=GameAwareEloEngine().fit(test,names)
        bare={r["contestId"]:r for r in base.game_receipts}
        variants={}
        early={}
        for name,model in [
            ("carryover",Elo2Engine(prior,0)),
            ("scheduleOnly",Elo2Engine({},SOS_WEIGHT)),
            ("carryoverAndSchedule",Elo2Engine(prior,SOS_WEIGHT)),
        ]:
            model.fit(test,names)
            variants[name]=paired_metrics(base.game_receipts,model.game_receipts)
            early_ids={r["contestId"] for r in base.game_receipts if r["dayNum"]<=45}
            early[name]=paired_metrics(base.game_receipts,model.game_receipts,early_ids)
        years.append({
            "season":year,"games":len(test),"priorSeason":year-1,
            "priorSourceGames":len(previous),"priorMatchedTeams":len(prior),
            "earlyGames":len(early_ids),
            "variants":variants,"earlyVariants":early,
            "sourcePolicy":"Same pinned Kaggle school IDs; previous-season final strength only",
        })
    variants={}
    for label in ["carryover","scheduleOnly","carryoverAndSchedule"]:
        variants[label]={
            **_aggregate(years,label),
            "earlySeason":_aggregate(years,label,"earlyVariants"),
            "seasonBlockBrierGain95":_confidence(years,label),
            "positiveGainSeasons":sum(1 for row in years
               if row["variants"][label]["brierGain"]>0),
        }
    return {
        "schemaVersion":1,"type":"elo-v2-historical-year-holdout",
        "source":URL,"sourceCommit":SOURCE_COMMIT,"sourceSha256":digest,
        "status":"ready" if len(years)>=5 else "insufficient-complete-seasons",
        "holdoutSeasons":len(years),
        "firstHeldOutYear":years[0]["season"] if years else None,
        "lastHeldOutYear":years[-1]["season"] if years else None,
        "fixedHyperparameters":{
            "offseasonCarryover":PRIOR_WEIGHT,"maxPriorDeviation":PRIOR_CAP,
            "scheduleWeight":SOS_WEIGHT,"maxScheduleOffset":SOS_CAP,
            "marginK":24,"homeAdvantage":65,"sameDayEmbargo":True},
        "baseline":"Production current-season GameAwareEloEngine: season-reset 1500, bounded score margin, same-day-frozen opponent expectation",
        "variants":variants,"bySeason":years,
        "recommendation":"Research only: no automatic production promotion; use genuine first-published pretipoff evidence and source ID checks.",
        "warnings":[
            "Fixed challenger parameters are hypotheses, not tuned or selected on held-out years.",
            "Every season uses exactly the same scored fixtures; prior-year ratings only from earlier-season games.",
            "Historical replay is an offline game-date benchmark, not actual forward published forecasts.",
            "2026 historically pinned scores end at day 118 and are excluded as a complete historical holdout.",
            "The current 2027 candidate matches to this incomplete 2026 snapshot by exact school name only; identity verification must precede any production promotion.",
        ],
    }


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-csv",type=Path,help="Offline pinned source file for reproducible tests")
    p.add_argument("--out",type=Path,
                   default=Path("web/public/research/elo-v2-historical.json"))
    args=p.parse_args()
    try:
        raw=args.raw_csv.read_bytes() if args.raw_csv else download()
        games,digest=read_games(raw)
        report=evaluate(games,digest)
    except (OSError,TimeoutError,ValueError,KeyError) as exc:
        if args.raw_csv:
            raise
        report={"schemaVersion":1,"type":"elo-v2-historical-year-holdout",
                "status":"unavailable","holdoutSeasons":0,
                "source":URL,"sourceCommit":SOURCE_COMMIT,
                "reason":f"Pinned historical research source unavailable: {type(exc).__name__}: {str(exc)[:180]}",
                "variants":{},"bySeason":[],
                "recommendation":"Do not invent missing historical holdout data or automatically promote Elo 2.0."}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"Elo 2.0 prior-year benchmark: {report['status']}; "
          f"{report['holdoutSeasons']} seasons; historical source pinned")
    if report["status"]=="ready":
        for label,v in report["variants"].items():
            print(f"  {label}: {v['games']} games, paired Brier gain {v['brierGain']}, "
                  f"early season gain {v['earlySeason']['brierGain']}, "
                  f"year CI {v['seasonBlockBrierGain95']}")
if __name__=="__main__":
    main()

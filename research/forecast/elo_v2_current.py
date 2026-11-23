"""Current 2027 Elo 2.0 *shadow* ratings, historical proof and AP three-way lab.

The current 2026 Kaggle snapshot is incomplete through day 118.
Strict case-folded EXACT 2026 Kaggle school names are a provisional
cross-year identity, not a source-verified ID crosswalk to NCAA 2027.
Neither this challenger nor AP votes are ever used to choose live picks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import Game
from .elo_v2 import (Elo2Engine,preseason_priors,paired_metrics,
                     PRIOR_WEIGHT,SOS_WEIGHT)
from .game_aware_elo import GameAwareEloEngine
from .history import SOURCE_COMMIT
from .live import FIRST_DATE

EASTERN=ZoneInfo("America/New_York")


def source_priors(snapshot:dict,names:set[str])->tuple[dict[str,float],dict]:
    if (snapshot.get("mode")!="historical" or snapshot.get("season")!=2026
        or snapshot.get("sourceCommit")!=SOURCE_COMMIT
        or not isinstance(snapshot.get("teams"),list)):
        raise ValueError("Pinned previous-year Kaggle source provenance mismatch")
    if snapshot.get("throughDay") != 118 or snapshot.get("isComplete") is not False:
        # Intentionally acknowledge true source incompleteness, rather than
        # changing prior policy when a newly edited snapshot appears.
        raise ValueError("Unexpected 2026 incomplete snapshot coverage")
    prior_names={}
    duplicates=set()
    for team in snapshot["teams"]:
        name=str(team.get("name") or "").strip()
        rating=float(team.get("rating") or 0)
        if not name or not math.isfinite(rating) or rating<1000 or rating>2000:
            raise ValueError("Invalid historical prior source team")
        key=name.casefold()
        if key in prior_names:
            duplicates.add(key)
        prior_names[key]=rating
    for key in duplicates:
        prior_names.pop(key,None)
    current_by_key={}
    for name in names:
        current_by_key.setdefault(name.casefold(),[]).append(name)
    # An apparent duplicate school-name identity must not assign one
    # historical prior to two distinct 2027 IDs.
    ambiguous_current={key for key,values in current_by_key.items() if len(values)!=1}
    matches={n:prior_names[n.casefold()] for n in names
             if n.casefold() in prior_names and n.casefold() not in ambiguous_current}
    return matches,{
        "snapshotSeason":2026,"snapshotThroughKaggleDay":118,
        "snapshotIsComplete":False,"snapshotSourceCommit":SOURCE_COMMIT,
        "joinPolicy":"Exact case-insensitive school NAME ONLY, not authoritative season-spanning NCAA/Kaggle ID linkage",
        "matchedTeamNames":len(matches),"sourceHistoricalTeams":len(snapshot["teams"]),
        "unmatchedTeamNames":len(names)-len(matches),
        "ambiguousCurrentNameGroupsWithheld":len(ambiguous_current),
        "identityWarning":"The 2026 historical source is incomplete, and school names alone cannot prove a program identity. Research-only candidate, not approved for live promotion.",
    }


def _to_games(records:list[dict],season:int=2027)->tuple[list[Game],dict[int,str]]:
    names=sorted({g["home"] for g in records}|{g["away"] for g in records},key=str.casefold)
    index={name:i+1 for i,name in enumerate(names)}
    out=[]
    for g in records:
        home,away=g["home"],g["away"]
        h,a=int(g["homeScore"]),int(g["awayScore"])
        if not(min(h,a)>0 and h!=a):
            raise ValueError("Invalid live game score")
        won=h>a
        out.append(Game(season,(date.fromisoformat(g["date"])-FIRST_DATE).days,
                        index[home] if won else index[away],
                        index[away] if won else index[home],
                        max(h,a),min(h,a),"H" if won else "A",str(g["id"])))
    return out,{v:k for k,v in index.items()}


def _cohort_rank(engine:Elo2Engine,ratings:dict)->list[dict]:
    source_rows=[t for t in ratings["teams"] if t.get("divisionIConfirmed") is True
                 and str(t.get("espnSourceTeamId") or "").strip()
                 and int(t.get("wins",0))+int(t.get("losses",0))>0]
    # The site-wide rank can contain non-D-I opponents and projected-form
    # positions. Compare like with like: raw-rating ranks among the SAME
    # source-linked D-I cohort only, not incompatible public rank numbers.
    source_rows.sort(key=lambda t:(-float(t["rating"]),t["name"]))
    sourced={t["name"]:{**t,"baselineD1Rank":i+1}
             for i,t in enumerate(source_rows)}
    # Current model's D-I + ESPN linkage is reused only as a source *ID
    # comparator*. New historical prior matched by name is NOT approved.
    rows=[]
    for state in engine.states.values():
        source=sourced.get(state.name)
        if not source or state.games==0:
            continue
        rows.append({
            "name":state.name,"teamId":source["teamId"],
            "espnTeamId":str(source["espnSourceTeamId"]),
            "elo2":round(state.rating,1),
            "opponentScheduleBonus":round(engine.schedule_adjustment(state.team_id),2),
            "games":state.games,
            "baselineElo":float(source["rating"]),
            "baselineRank":int(source["baselineD1Rank"]),
            "wins":state.wins,"losses":state.losses,
            "offseasonPrior":round(engine.initial_ratings.get(state.team_id,1500),1),
            "hasHistoricalMatch":state.team_id in engine.initial_ratings,
        })
    seen=set()
    for row in rows:
        if row["espnTeamId"] in seen:
            raise ValueError("Duplicate verified ESPN identity in Elo2 cohort")
        seen.add(row["espnTeamId"])
    rows.sort(key=lambda x:(-x["elo2"],x["name"]))
    for idx,row in enumerate(rows):
        row["elo2Rank"]=idx+1
        row["rankChangeFromBaseline"]=row["baselineRank"]-(idx+1)
    return rows


def compare_ap(archive:dict,records:list[dict],ratings:dict,
               matches:dict[str,float])->list[dict]:
    if archive.get("season")!=2027 or not isinstance(archive.get("weeks"),list):
        raise ValueError("AP archive source invalid")
    output=[]
    for week in archive["weeks"]:
        date_key=week["sourceWeekStart"]
        cutoff=date.fromisoformat(date_key)-timedelta(days=1)
        eligible=[g for g in records if date.fromisoformat(g["date"])<=cutoff]
        if not eligible:
            continue
        gamedata,id_names=_to_games(eligible)
        ids={tid:matches[name] for tid,name in id_names.items() if name in matches}
        model=Elo2Engine(preseason_priors(ids,set(id_names)),SOS_WEIGHT).fit(gamedata,id_names)
        rows=_cohort_rank(model,ratings)
        teamids={x["espnTeamId"]:x for x in rows}
        apids={t["espnTeamId"] for t in week["teams"]}
        top25={x["espnTeamId"] for x in rows[:25]}
        top10={x["espnTeamId"] for x in rows[:10]}
        records_out=[]
        for team in week["teams"]:
            challenger=teamids.get(team["espnTeamId"])
            records_out.append({
                "apRank":team["apRank"],
                "apTeam":team["apName"],
                "baselineEloRankFrozen":team.get("eloRank"),
                "elo2Rank":challenger["elo2Rank"] if challenger else None,
                "elo2":challenger["elo2"] if challenger else None,
                "rankGap":(challenger["elo2Rank"]-team["apRank"]) if challenger else None,
            })
        n=sum(x["elo2Rank"] is not None for x in records_out)
        ready=n>=20 and len(rows)>=25
        output.append({
            "pollKey":week["pollKey"],"sourceWeekStart":date_key,
            "eloGameCutoffDate":cutoff.isoformat(),
            "status":"retrospective-comparable" if ready else "insufficient-identity-evidence",
            "apMatchedElo2":n,
            "baselineTop25OverlapFrozen":week.get("top25Overlap"),
            "elo2Top25Overlap":len(apids&top25) if ready else None,
            "baselineTop10OverlapFrozen":week.get("top10Overlap"),
            "elo2Top10Overlap":len({x["espnTeamId"] for x in week["teams"][:10]}&top10)
                if ready else None,
            "elo2Top25":[{"team":r["name"],"rank":r["elo2Rank"],
                          "elo":r["elo2"]} for r in rows[:25]],
            "teams":records_out,
            "warning":"Elo2 poll comparison reconstructed today using same-date cutoff and currently accepted historical scores. The archived original Elo/AP comparison remains frozen; score availability at the historical polling instant is not proved.",
        })
    return output


def build(records:list[dict],ratings:dict,previous:dict,ap:dict,
          historical:dict,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Elo2 research clock must be timezone-aware")
    if ratings.get("mode")!="current" or ratings.get("season")!=2027:
        raise ValueError("Requires latest source-aligned 2027 ratings")
    if len(records)!=ratings.get("regularSeasonGames"):
        raise ValueError("Elo2 game count does not match source ratings")
    if not records:
        raise ValueError("No accepted 2027 games for research")
    if max(g["date"] for g in records)>now.astimezone(EASTERN).date().isoformat():
        raise ValueError("Future score in source accepted game corpus")
    games,names=_to_games(records)
    prior_names,coverage=source_priors(previous,set(names.values()))
    prior_by_id={tid:prior_names[name] for tid,name in names.items() if name in prior_names}
    priors=preseason_priors(prior_by_id,set(names))
    control=GameAwareEloEngine().fit(games,names)
    compared={}
    models={}
    for label,weights,sos in [
        ("carryover",priors,0),
        ("scheduleOnly",{},SOS_WEIGHT),
        ("carryoverAndSchedule",priors,SOS_WEIGHT),
    ]:
        model=Elo2Engine(weights,sos).fit(games,names)
        models[label]=model
        compared[label]=paired_metrics(control.game_receipts,model.game_receipts)
        compared[label]["researchOnly"]=True
    winner=models["carryoverAndSchedule"]
    teamrows=_cohort_rank(winner,ratings)
    if len(teamrows)<25:
        status="insufficient-current-division-identity"
    else:
        status="research-only"
    return {
        "schemaVersion":1,"season":2027,"type":"current-elo2-research",
        "status":status,"generatedAtUtc":now.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
        "ratingRetrievedAtUtc":ratings["retrievedAtUtc"],
        "sourceGameDate":ratings["lastGameDate"],
        "sourceGames":len(records),
        "historicalBenchmarkStatus":historical.get("status"),
        "historicalHoldoutSeasons":historical.get("holdoutSeasons",0),
        "baselineMethodVersion":ratings.get("eloMethodology",{}).get("version"),
        "candidate":"Offseason 55%-regressed 2026 partial historical Elo plus 16% prior-opponent-SOS signal",
        "priorCoverage":coverage,
        "currentRetrospective":compared,
        "teams":teamrows,
        "apComparisons":compare_ap(ap,records,ratings,prior_names),
        "modelPromotionAllowed":False,
        "promotionReason":"2026 historical prior is incomplete and name-joined only. No independently verified cross-season identity proof or first-published prospective superiority; do not change active picks.",
        "caveats":[
            "Research-only challenger. Daily source-verified Elo and game probabilities are unchanged.",
            "2026 previous-year Kaggle snapshot ends at day 118, and its exact-name join to 2027 school names is NOT a verified cross-year identity.",
            "Schedule strength is computed from past opponent game-day Elo only, shrunken and capped.",
            "Current-year retrospective games and reconstructed AP comparisons are date-frozen but not timestamp-validated at each original pregame deadline.",
            "AP poll agreement is a ranking opinion comparison, not the accuracy target or a model training label.",
        ],
    }


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--previous",type=Path,default=Path("web/public/seasons/2026.json"))
    p.add_argument("--ap",type=Path,default=Path("web/public/research/ap-poll-history.json"))
    p.add_argument("--historical",type=Path,
                   default=Path("web/public/research/elo-v2-historical.json"))
    p.add_argument("--out",type=Path,
                   default=Path("web/public/current/elo-v2-research.json"))
    args=p.parse_args()
    games=json.loads(args.games.read_text(encoding="utf-8"))
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    if (games.get("season")!=2027 or
        games.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc")):
        raise ValueError("Candidate rating/game source timestamps must match")
    previous=json.loads(args.previous.read_text(encoding="utf-8"))
    ap=json.loads(args.ap.read_text(encoding="utf-8"))
    historical=json.loads(args.historical.read_text(encoding="utf-8"))
    report=build(games["games"],ratings,previous,ap,historical)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"Elo2 2027 shadow: {report['status']}; "
          f"{report['sourceGames']} same-date games; "
          f"{report['priorCoverage']['matchedTeamNames']} previous-year EXACT names; "
          f"paired historical Brier gains { {k:v['brierGain'] for k,v in report['currentRetrospective'].items()} }; "
          f"{len(report['apComparisons'])} AP weeks reconstructed. No active promotion.")
if __name__=="__main__":
    main()

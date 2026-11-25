"""Matched 2003+ Kaggle detailed-box Elo 3.0 statistical ablation.

Historical box counts are observed in the pinned Kaggle 2026 mirror. Game
possessions are *estimated* from box totals, not independently recorded.
Match on Kaggle season/day/winner/loser plus BOTH scores and venue against
the separately pinned compact game source, with no team-name inference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

from .elo_v2_historical import read_games, download as compact_download, HOLDOUT_YEARS
from .elo_v3 import replay, historical_priors, metrics, _gain_ci, _paired_cohort
from .elo_v2 import Elo2Engine, SOS_WEIGHT

# Public mirror of Kaggle 2026 men's detailed regular-season records, pinned
# to an immutable Git commit and blob SHA. No live changing main-branch data.
DETAIL_COMMIT = "e0c70940b0e807df89380740b3a6e0e18d76d01a"
DETAIL_BLOB_SHA1 = "c2e4a7a5355120373d92a84250fc0f1eda044842"
DETAIL_URL = (f"https://raw.githubusercontent.com/ryanbiancavilla/"
              f"march-ml-mania-2026/{DETAIL_COMMIT}/data/MRegularSeasonDetailedResults.csv")
MAX_BYTES = 22_000_000
MIN_COVERAGE = .90
MIN_HOLDOUT_DATES = 130
FEATURES = ("scoreOnly", "efficiency", "fourFactors", "extended")
FIELD_BASE = ("Season","DayNum","WTeamID","WScore","LTeamID","LScore","WLoc")
STATS = ("FGM","FGA","FGM3","FGA3","FTM","FTA","OR","DR","Ast","TO","Stl","Blk","PF")


def _git_blob_sha(raw:bytes)->str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw).hexdigest()


def download_detailed()->bytes:
    request = Request(DETAIL_URL, headers={
        "User-Agent":"MarchForecastHistoricalBoxResearch/1.0","Accept":"text/csv"})
    with urlopen(request,timeout=50) as resp:
        raw=resp.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("Pinned detailed data exceeds configured download limit")
    if _git_blob_sha(raw)!=DETAIL_BLOB_SHA1:
        raise ValueError("Detailed CSV Git blob SHA does not match immutable source")
    return raw


def _metrics(row:dict, prefix:str)->dict:
    stats={}
    for key in STATS:
        try:
            value=int(row[prefix+key])
        except (KeyError,ValueError,TypeError) as exc:
            raise ValueError("Incomplete historical box score") from exc
        if not 0<=value<=200:
            raise ValueError("Invalid historical box count")
        stats[key]=value
    if (not 30<=stats["FGA"]<=130 or stats["FGM"]>stats["FGA"] or
        stats["FGM3"]>stats["FGM"] or stats["FGM3"]>stats["FGA3"] or
        stats["FGA3"]>stats["FGA"] or stats["FTM"]>stats["FTA"] or
        stats["OR"]>stats["FGA"]-stats["FGM"]+3 or
        stats["TO"]>65 or stats["Ast"]>stats["FGM"]+3 or stats["PF"]>65):
        raise ValueError("Impossible historical source box relationships")
    return stats


def _box(own:dict, other:dict, scored:int, other_score:int, possessions:float)->dict:
    if 2*own["FGM"]+own["FGM3"]+own["FTM"] != scored:
        raise ValueError("Historical box points do not match final score")
    if not 40<=scored<=200 or not 40<=other_score<=200:
        raise ValueError("Historical game score outside source bounds")
    offensive=scored/possessions*100.
    defensive=other_score/possessions*100.
    if not 25<=offensive<=250 or not 25<=defensive<=250:
        raise ValueError("Unbounded estimated offensive/defensive efficiency")
    return {"poss":possessions, "off":offensive, "def":defensive,
            "factors":{"fga":own["FGA"],"fgm":own["FGM"],"fg3m":own["FGM3"],
                       "fta":own["FTA"],"tov":own["TO"],"orb":own["OR"],
                       "drb":own["DR"]},
            "extras":{"fg3a":own["FGA3"],"ftm":own["FTM"],"ast":own["Ast"],
                      "stl":own["Stl"],"blk":own["Blk"],"pf":own["PF"]}}


def parse_detail(raw:bytes, grouped:dict, years=HOLDOUT_YEARS):
    """Match exact game IDs from different source snapshots; drop discrepancies.

    A row with conflicting scores/venue is NOT allowed to provide statistics,
    even if team IDs and day happen to match. Duplicate or ambiguous rows are
    not allowed to win by filename order.
    """
    if len(raw)>MAX_BYTES:
        raise ValueError("Historical detailed source exceeds maximum allowed size")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    required=set(FIELD_BASE)|{p+k for p in "WL" for k in STATS}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Historical detailed source missing Kaggle box columns")
    lookup={}
    yearset=set(years)
    for year in yearset:
        for g in grouped.get(year, []):
            key=(g.season,g.day_num,g.winner,g.loser)
            if key in lookup:
                raise ValueError("Duplicate compact-source game identity")
            lookup[key]=g
    pairs={}
    blocked=set()
    counted=Counter()
    for row in reader:
        try:
            year=int(row["Season"])
        except (TypeError,ValueError) as exc:
            raise ValueError("Unparseable detailed source year") from exc
        if year not in yearset:
            continue
        try:
            key=tuple(int(row[t]) for t in ("Season","DayNum","WTeamID","LTeamID"))
        except (TypeError,ValueError) as exc:
            raise ValueError("Unparseable historical detailed game identity") from exc
        reference=lookup.get(key)
        if reference is None:
            counted["notInPinnedCompact"]+=1
            continue
        if key in pairs or key in blocked:
            # Reject all rows for duplicate game identity instead of trusting
            # the first copy's outcomes and features.
            blocked.add(key)
            pairs.pop(key,None)
            counted["duplicate"]+=1
            continue
        if (int(row["WScore"])!=reference.winner_score or
            int(row["LScore"])!=reference.loser_score or
            row["WLoc"]!=reference.winner_location):
            counted["scoreOrVenueMismatch"]+=1
            blocked.add(key)
            continue
        try:
            w=_metrics(row,"W")
            l=_metrics(row,"L")
            # Standard box-derived possession estimator. These are *never*
            # called official/observed possessions.
            pw=w["FGA"]-w["OR"]+w["TO"]+.475*w["FTA"]
            pl=l["FGA"]-l["OR"]+l["TO"]+.475*l["FTA"]
            poss=(pw+pl)/2
            if not 40<=poss<=120 or abs(pw-pl)>30:
                raise ValueError("Unreliable estimated historical possessions")
            wb=_box(w,l,reference.winner_score,reference.loser_score,poss)
            lb=_box(l,w,reference.loser_score,reference.winner_score,poss)
        except ValueError:
            counted["invalidBox"]+=1
            blocked.add(key)
            continue
        pairs[key]={"winnerId":reference.winner,"loserId":reference.loser,
                    "dayNum":reference.day_num,"winner":wb,"loser":lb}
        counted["matched"]+=1
    season_pairs=defaultdict(dict)
    for (year,day,w,l),record in pairs.items():
        contest=lookup[(year,day,w,l)].contest_id
        if contest in season_pairs[year]:
            raise ValueError("Duplicate contest ID when mapping detailed source")
        season_pairs[year][contest]=record
    source_counts={y:len(grouped.get(y,[])) for y in sorted(yearset)}
    matched_counts={y:len(season_pairs[y]) for y in sorted(yearset)}
    return dict(season_pairs), {
        "matched":sum(matched_counts.values()),
        "sourceGames":sum(source_counts.values()),
        "coverageBySeason":{str(year):{
            "sourceGames":source_counts[year],
            "matchedBoxGames":matched_counts[year],
            "coverage":round(matched_counts[year]/source_counts[year],6)
                       if source_counts[year] else None}
            for year in sorted(yearset)},
        "mismatches":dict(counted),
        "possessionSource":"ESTIMATED from observed FGA−ORB+TO+0.475×FTA, averaged across teams; NOT directly recorded",
        "identity":"Exact Kaggle season, day, winning/losing team IDs, scores and WLoc; separate pinned mirrors"}


def _paired(outcomes:dict[str,dict], games, year):
    if len({g.contest_id for g in games})!=len(games):
        raise ValueError("Duplicate outcome fixture in historical ablation")
    first={variant:{row["contestId"]:row for row in result["rows"]}
           for variant,result in outcomes.items()}
    expected={g.contest_id:g for g in games}
    if any(set(rows)!=set(expected) for rows in first.values()):
        raise ValueError("Unmatched historical box-model outcome cohorts")
    final=[]
    for gid,g in sorted(expected.items()):
        event={"contestId":gid,"day":g.day_num,"y":1. if g.winner<g.loser else 0.}
        for variant,rows in first.items():
            x=rows[gid]
            if x["day"]!=g.day_num or x["y"]!=event["y"]:
                raise ValueError("Detailed ablation date/outcome mismatch")
            event[variant]=x["elo3"]
        event["boxEligible"]=first["fourFactors"][gid]["fourFactorsUsed"]
        event["extendedEligible"]=first["extended"][gid]["extendedUsed"]
        final.append(event)
    return final


def evaluate(grouped:dict, pairs:dict, coverage:dict, years=HOLDOUT_YEARS):
    """Within each test season compare four Elo3 ablations on identical dates.

    No test-year result fits hyperparameters. Historical stable IDs allow
    preseason carryover from previous years; no modern 2027 joins are made.
    """
    seasons=[]
    all_rows=[]
    excluded=[]
    for year in years:
        games=grouped.get(year,[])
        prior=grouped.get(year-1,[])
        info=coverage["coverageBySeason"][str(year)]
        if not games or not prior or max(g.day_num for g in games)<132 or max(g.day_num for g in prior)<132:
            excluded.append({"season":year,"reason":"Incomplete score-only test or predecessor season"})
            continue
        if info["coverage"] is None or info["coverage"]<MIN_COVERAGE:
            excluded.append({"season":year,"reason":"Detailed-box coverage under 90% independent compact-score matches",
                             "coverage":info["coverage"]})
            continue
        names={g.winner for g in games}|{g.loser for g in games}
        priors=historical_priors(grouped,year,names,3)
        verified=pairs.get(year,{})
        result={
            "scoreOnly":replay(games,priors,stats_variant="scoreOnly"),
            "efficiency":replay(games,priors,paired_boxes=verified,stats_variant="efficiency"),
            "fourFactors":replay(games,priors,paired_boxes=verified,stats_variant="fourFactors"),
            "extended":replay(games,priors,paired_boxes=verified,stats_variant="extended")
        }
        aligned=_paired(result,games,year)
        # Feature eligibility depends *only on prior-date* observed boxes.
        # Evaluate all variants on the same predeclared matched cohort.
        eligible=[row for row in aligned if row["boxEligible"]]
        if not eligible:
            excluded.append({"season":year,"reason":"No previously eligible paired four-factor games"})
            continue
        baseline=metrics(eligible,"scoreOnly")
        comparisons={variant:metrics(eligible,variant) for variant in FEATURES}
        seasons.append({
            "season":year,"sourceGames":len(games),"pairedBoxGames":len(verified),
            "eligiblePregameGames":len(eligible),
            "extendedEligibleGames":sum(row["extendedEligible"] for row in eligible),
            "coverage":info["coverage"],
            "baseline":baseline,"variants":comparisons,
            "gains":{v:round(baseline["brier"]-comparisons[v]["brier"],8)
                     for v in FEATURES}})
        all_rows.extend(eligible)
    summary={key:metrics(all_rows,key) for key in FEATURES}
    baseline=summary["scoreOnly"]
    gains={key:round(baseline["brier"]-summary[key]["brier"],6)
           for key in FEATURES} if all_rows else {key:None for key in FEATURES}
    return {
        "schemaVersion":1,"type":"elo3-historical-box-ablation",
        "status":"ready" if len(seasons)>=5 else "insufficient-verified-seasons",
        "source":DETAIL_URL,"sourceCommit":DETAIL_COMMIT,
        "sourceBlobSha1":DETAIL_BLOB_SHA1,
        "boxSourceSha256":None,
        "holdoutSeasons":[s["season"] for s in seasons],
        "sourceCoverage":coverage,"exclusions":excluded,
        "eligiblePairedGames":len(all_rows),
        "variants":summary,"brierGainVsScoreOnly":gains,
        "seasonBlockGain95":{key:_gain_ci(seasons,key) for key in FEATURES[1:]},
        "positiveSeasons":{key:sum(s["gains"][key]>0 for s in seasons)
                           for key in FEATURES[1:]},
        "bySeason":seasons,
        "automaticPromotion":False,
        "limitations":[
            "The source supplies observed team shooting, rebounding, turnovers, assists, steals, blocks, fouls, and points, NOT directly counted possessions.",
            "Possessions and points per 100 are estimates from an explicit box-score formula; efficiency is not independently verified play-by-play.",
            "Two independent historical mirrors are strictly matched by stable Kaggle IDs, date, team IDs, result, and location; mismatched games are excluded.",
            "Historical compact-score dates are previous-day frozen, not published pre-tipoff timestamps.",
            "Same holdout years were inspected while designing this research; gains require new prospective evidence and prespecified future-seasons before promotion.",
            "Four Factors overlap with estimated efficiency. Improvements must be shown with independent paired ablations before trusting complexity.",
            "Never join 2027 NCAA school-name hashes to historical Kaggle IDs without independent authoritative identity."]}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--raw-csv",type=Path,help="Local historical detailed CSV fixture")
    cli.add_argument("--compact-csv",type=Path,help="Local pinned compact results fixture")
    cli.add_argument("--out",type=Path,default=Path("web/public/research/elo-v3-historical-box.json"))
    args=cli.parse_args()
    try:
        compact=args.compact_csv.read_bytes() if args.compact_csv else compact_download()
        grouped,compact_digest=read_games(compact)
        if args.raw_csv:
            detailed=args.raw_csv.read_bytes()
            source_provenance="local-test-file"
        else:
            detailed=download_detailed()
            source_provenance="pinned-public-mirror-verified-git-blob"
        pairs,coverage=parse_detail(detailed,grouped)
        report=evaluate(grouped,pairs,coverage)
        report["sourceSha256"]=compact_digest
        report["boxSourceSha256"]=hashlib.sha256(detailed).hexdigest()
        report["sourceVerification"]=source_provenance
    except (OSError,TimeoutError,ConnectionError) as exc:
        if args.raw_csv or args.compact_csv:
            raise
        report={"schemaVersion":1,"type":"elo3-historical-box-ablation",
                "status":"unavailable","eligiblePairedGames":0,
                "source":DETAIL_URL,"automaticPromotion":False,
                "reason":f"Pinned historical box source unreachable: {type(exc).__name__}: {str(exc)[:160]}"}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+chr(10),encoding="utf-8")
    print(json.dumps({k:report.get(k) for k in
          ("status","eligiblePairedGames","holdoutSeasons","brierGainVsScoreOnly","reason")},indent=2))


if __name__=="__main__":
    main()

"""Research-only Elo 3: six causal improvements with matched historical comparison."""
from __future__ import annotations
import argparse,json,math
from collections import defaultdict
from itertools import groupby
from pathlib import Path
from .core import matchup_probability
from .game_aware_elo import GameAwareEloEngine,margin_multiplier
from .elo_v2 import preseason_priors
from .elo_v2_historical import read_games,download,URL,HOLDOUT_YEARS

def metrics(rows,key):
    n=len(rows)
    if not n:return {"games":0,"brier":None,"logLoss":None}
    return {"games":n,"brier":round(sum((x[key]-x["y"])**2 for x in rows)/n,6),
            "logLoss":round(-sum(math.log(max(1e-12,x[key] if x["y"] else 1-x[key])) for x in rows)/n,6)}

def probability(gap,temperature=1.):
    return matchup_probability(1500.+gap/temperature,1500.)

def replay(games,priors=None,paired_boxes=None):
    """Frozen previous-date Elo; paired_boxes keyed by immutable contest ID."""
    games=sorted(games,key=lambda g:(g.day_num,min(g.winner,g.loser),max(g.winner,g.loser),g.contest_id))
    if not games:return {"rows":[],"pairedBoxes":0,"boxEligible":0}
    if len({g.season for g in games})!=1:raise ValueError("Multiple seasons")
    ids=[g.contest_id for g in games if g.contest_id]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate contest ID")
    ratings=defaultdict(lambda:1500.)
    for team,value in (priors or {}).items():
        if not math.isfinite(value) or not 1000<=value<=2000:raise ValueError("Invalid prior")
        ratings[team]=value
    form=defaultdict(float);counts=defaultdict(int)
    # Two-sided, source-verified ORTG/DRTG/poss; no fabricated data.
    off=defaultdict(float);defence=defaultdict(float);poss=defaultdict(float);boxcount=defaultdict(int)
    home=65.;history=[];rows=[];matched=eligible=0
    for day,group in groupby(games,key=lambda g:g.day_num):
        batch=list(group)
        if any(g.winner_location not in ("H","A","N") or g.winner_score<=g.loser_score
               or g.loser_score<=0 for g in batch):raise ValueError("Invalid scored game")
        # Calibrate only using completed previous dates, with a small
        # penalty for overfitting temperature.
        temperatures=(.8,.9,1.,1.1,1.2,1.35)
        if len(history)>=120 and len({x["day"] for x in history})>=15:
            temp=min(temperatures,key=lambda t:(
                sum((probability(x["gap"],t)-x["y"])**2 for x in history)/len(history)
                +.0003*(t-1.)**2,abs(t-1.)))
        else:temp=1.
        frozen=[]
        for g in batch:
            w,l=g.winner,g.loser
            venue={"H":home,"A":-home,"N":0.}[g.winner_location]
            recency=max(-30.,min(30.,form[w]*counts[w]/(counts[w]+12.)
                                     -form[l]*counts[l]/(counts[l]+12.)))
            efficiency=0.
            if boxcount[w]>=3 and boxcount[l]>=3:
                netw=(off[w]-defence[w])/(poss[w]+500.)*100.
                netl=(off[l]-defence[l])/(poss[l]+500.)*100.
                efficiency=max(-45.,min(45.,2.*(netw-netl)))
                eligible+=1
            gap=ratings[w]-ratings[l]+venue+recency+efficiency
            raw=probability(gap)
            p=probability(gap,temp)
            y=1. if w<l else 0.
            rows.append({"contestId":g.contest_id,"day":day,"y":y,
                         "elo3":p if y else 1-p,"uncalibrated":raw if y else 1-raw,
                         "temperature":temp,"boxUsed":bool(efficiency)})
            frozen.append((g,gap,raw))
        # All game predictions are frozen before updating ANY result of day.
        for g,gap,raw in frozen:
            w,l=g.winner,g.loser
            margin=g.winner_score-g.loser_score
            k=24.*margin_multiplier(margin)/(1.+max(0.,ratings[w]-ratings[l])/1800.)
            k*=.65+.35*min(counts[w],counts[l])/(min(counts[w],counts[l])+6.)
            delta=k*(1.-raw)
            ratings[w]+=delta;ratings[l]-=delta
            form[w]=.8*form[w]+.2*delta
            form[l]=.8*form[l]-.2*delta
            counts[w]+=1;counts[l]+=1
            if g.winner_location!="N":
                home_won=g.winner_location=="H"
                expected_home=raw if home_won else 1.-raw
                home=max(15.,min(110.,home+1.5*((1. if home_won else 0.)-expected_home)))
            box=(paired_boxes or {}).get(g.contest_id)
            if box is not None:
                if (box.get("winnerId")!=w or box.get("loserId")!=l or box.get("dayNum")!=day):
                    raise ValueError("Paired-box identity mismatch")
                for team,side in ((w,"winner"),(l,"loser")):
                    b=box[side]
                    if any(type(b.get(k)) not in (float,int) or not math.isfinite(b[k]) or
                           not (30<=b[k]<=180 if k=="poss" else 25<=b[k]<=250)
                           for k in ("poss","off","def")):
                        raise ValueError("Invalid source paired-box metric")
                    off[team]+=b["off"]*b["poss"]/100.
                    defence[team]+=b["def"]*b["poss"]/100.
                    poss[team]+=b["poss"];boxcount[team]+=1
                matched+=1
        for g,gap,raw in frozen:
            y=1. if g.winner<g.loser else 0.
            history.append({"day":day,"gap":gap if y else -gap,"y":y})
    return {"rows":rows,"pairedBoxes":matched,"boxEligible":eligible,
            "finalHomeAdvantage":round(home,3)}

def evaluate(grouped,years=HOLDOUT_YEARS):
    reports=[];allrows=[]
    for year in years:
        if year-1 not in grouped or year not in grouped:continue
        prev,now=grouped[year-1],grouped[year]
        if max(g.day_num for g in prev)<132 or max(g.day_num for g in now)<132:continue
        ids={g.winner for g in now}|{g.loser for g in now}
        old=GameAwareEloEngine().fit(prev,{})
        priors=preseason_priors({i:s.rating for i,s in old.states.items()},ids)
        base=GameAwareEloEngine().fit(now,{})
        challenger=replay(now,priors)
        byid={x["contestId"]:x for x in base.game_receipts}
        if len(byid)!=len(challenger["rows"]):raise ValueError("Unmatched cohort")
        cohort=[]
        for row in challenger["rows"]:
            b=byid[row["contestId"]]
            if b["dayNum"]!=row["day"]:raise ValueError("Date mismatch")
            p=b["winnerProbability"] if row["y"] else 1.-b["winnerProbability"]
            cohort.append({**row,"baseline":p})
        a,b=metrics(cohort,"baseline"),metrics(cohort,"elo3")
        reports.append({"season":year,"games":len(cohort),"baseline":a,"elo3":b,
                        "brierGain":round(a["brier"]-b["brier"],6)})
        allrows.extend(cohort)
    a,b=metrics(allrows,"baseline"),metrics(allrows,"elo3")
    return {"schemaVersion":1,"mode":"elo3-historical-previous-date-research",
            "holdoutSeasons":[x["season"] for x in reports],"games":len(allrows),
            "baseline":a,"elo3":b,"uncalibrated":metrics(allrows,"uncalibrated"),
            "brierGain":round(a["brier"]-b["brier"],6) if allrows else None,
            "bySeason":reports,"source":URL,"automaticPromotion":False,
            "capabilities":{"verifiedOpponentEfficiency":"optional paired-box inputs; not available in compact historical score file",
                            "adaptiveHome":True,"boundedMargin":True,"recentFormAndUncertainty":True,
                            "stableIdPriorSeason":True,"previousDateCalibration":True},
            "limitations":["Historical compact score source has no paired box scores, so historical efficiency feature is disabled, not imputed.",
                           "Hyperparameters are research hypotheses, not nested-tuned.",
                           "Date-frozen replay is not a prospective first-pick test.",
                           "Source-linked current-season paired-box benchmark is a separate evaluation.",
                           "Production model unchanged."]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--raw-csv",type=Path)
    p.add_argument("--out",type=Path,default=Path("research/outputs/elo3-historical.json"))
    args=p.parse_args()
    grouped,digest=read_games(args.raw_csv.read_bytes() if args.raw_csv else download())
    report=evaluate(grouped);report["sourceSha256"]=digest
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("games","baseline","elo3","brierGain")},indent=2))
if __name__=="__main__":main()

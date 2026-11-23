"""Research-only Elo 2.0: offseason carryover and causal strength of schedule.

This is deliberately not used by the production predictor. It replays exactly
the existing day-grouped game records. Ratings for a day's games are frozen at
the START of that date; only afterwards are updates and opponent-strength
receipts applied. Candidate prior rating for a team is sourced from the
PREVIOUS season (never its current-season final standings).

Historical IDs: the pinned Kaggle team ID (year-to-year stable within source).
2027 IDs: a strict *exact-school-name* join to an explicitly incomplete pinned
2026 snapshot. This name-only crosswalk is provisional, NOT an independently
verified cross-season identity link and is unsuitable for promotion.
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import groupby
from typing import Mapping, Sequence

from .core import Game, TeamState, matchup_probability
from .game_aware_elo import margin_multiplier

CENTER=1500.0
K=24.0
HOME=65.0
PRIOR_WEIGHT=.55
PRIOR_CAP=160.0
SOS_WEIGHT=.16
SOS_CAP=35.0
SOS_SHRINK_GAMES=6.0


def preseason_priors(previous: Mapping[int,float],
                     current_team_ids: set[int],
                     weight: float=PRIOR_WEIGHT) -> dict[int,float]:
    """Fixed 55% year-to-year memory, clipped to a 160-point prior deviation."""
    if not (0 <= weight <= 1):
        raise ValueError("Invalid offseason regression factor")
    out={}
    for tid in sorted(current_team_ids):
        old=previous.get(tid)
        if old is None:
            continue  # first-year team has ordinary 1500 Elo
        if not math.isfinite(float(old)):
            raise ValueError("Nonfinite previous-season rating")
        delta=max(-PRIOR_CAP,min(PRIOR_CAP,float(old)-CENTER))
        out[tid]=CENTER+weight*delta
    return out


class Elo2Engine:
    """Date-frozen Elo with optional carried priors and historical SOS signals.

    Schedule term at start of date:
      clip(beta * sum(opponent PRE-DATE Elo - 1500)/(n + 6), +/-35).
    It is a small, shrunken adjustment to expected strength, not a second
    application of the final opponent rating. It is never based on
    current-date final scores or end-of-season opponents.
    """

    def __init__(self, initial_ratings:Mapping[int,float]|None=None,
                 sos_weight:float=SOS_WEIGHT):
        if not (0 <= sos_weight <= .5):
            raise ValueError("SOS weight must be bounded")
        self.initial_ratings=dict(initial_ratings or {})
        if any(not math.isfinite(x) or x < 1000 or x > 2000
               for x in self.initial_ratings.values()):
            raise ValueError("Unbounded or invalid initial ratings")
        self.sos_weight=sos_weight
        self.states:dict[int,TeamState]={}
        self.game_receipts:list[dict]=[]
        self.team_receipts:dict[int,list[dict]]={}
        self.pregame_brier:list[float]=[]
        self.pregame_accuracy:list[float]=[]
        self.last_day:int|None=None
        self.sos_sums:dict[int,float]=defaultdict(float)
        self.sos_counts:dict[int,int]=defaultdict(int)
        self.conservation_error=0.0

    def _state(self, team:int, names:Mapping[int,str]) -> TeamState:
        if team not in self.states:
            rating=self.initial_ratings.get(team,CENTER)
            self.states[team]=TeamState(team,names.get(team,str(team)),
                                        rating=rating,history=[rating])
        return self.states[team]

    def schedule_adjustment(self, team:int)->float:
        count=self.sos_counts[team]
        if count==0:
            return 0.0
        val=self.sos_weight*self.sos_sums[team]/(count+SOS_SHRINK_GAMES)
        return max(-SOS_CAP,min(SOS_CAP,val))

    def fit(self, games:Sequence[Game],names:Mapping[int,str]) -> "Elo2Engine":
        self.states={};self.game_receipts=[];self.team_receipts={}
        self.pregame_brier=[];self.pregame_accuracy=[]
        self.sos_sums=defaultdict(float);self.sos_counts=defaultdict(int)
        self.last_day=None;self.conservation_error=0.0
        ordered=sorted(games,key=lambda g:(g.day_num,
            min(g.winner,g.loser),max(g.winner,g.loser),
            g.contest_id,g.winner_score,g.loser_score))
        seen=set();season=None
        for day,group in groupby(ordered,key=lambda g:g.day_num):
            batch=list(group)
            frozen=[]
            # Birth of an unrated team is allowed only from a previous
            # season or the neutral 1500 prior. No current result leakage.
            for g in batch:
                if season is None:season=g.season
                if g.season!=season or g.day_num<0:
                    raise ValueError("Elo 2.0 accepts a single valid season")
                if (g.winner==g.loser or g.winner_score<=g.loser_score
                    or g.loser_score<=0 or g.winner_location not in ("H","A","N")):
                    raise ValueError("Invalid score or venue in Elo 2.0")
                if g.contest_id and g.contest_id in seen:
                    raise ValueError("Duplicate contest in Elo 2.0")
                if g.contest_id:seen.add(g.contest_id)
                w,l=self._state(g.winner,names),self._state(g.loser,names)
                hw=self.schedule_adjustment(w.team_id)
                hl=self.schedule_adjustment(l.team_id)
                venue={"H":HOME,"A":-HOME,"N":0.0}[g.winner_location]
                p=matchup_probability(w.rating+hw,l.rating+hl,venue)
                # Evaluate outcomes in source-independent team-ID orientation.
                first_id_won=g.winner<g.loser
                pfirst=p if first_id_won else 1-p
                outcome=1.0 if first_id_won else 0.0
                self.pregame_brier.append((pfirst-outcome)**2)
                self.pregame_accuracy.append(1.0 if p>.5 else .5 if p==.5 else 0.0)
                margin=g.winner_score-g.loser_score
                delta=K*margin_multiplier(margin)*(1.0-p)
                receipt={"contestId":g.contest_id,"dayNum":day,
                  "winnerId":g.winner,"loserId":g.loser,
                  "preWinnerElo":round(w.rating,6),
                  "preLoserElo":round(l.rating,6),
                  "winnerProbability":round(p,7),
                  "winnerDelta":round(delta,5),"loserDelta":round(-delta,5),
                  "winnerSosAdjustment":round(hw,5),
                  "loserSosAdjustment":round(hl,5),
                  "winnerPriorOpponentGames":self.sos_counts[w.team_id],
                  "loserPriorOpponentGames":self.sos_counts[l.team_id],
                  "scoreMargin":margin,"venue":g.winner_location}
                frozen.append((g,w,l,delta,receipt))
            # Rating movements and opponent receipts both apply after ALL
            # frozen-date predictions were calculated.
            for g,w,l,delta,receipt in frozen:
                w.rating+=delta;l.rating-=delta
                w.wins+=1;l.losses+=1
                w.history.append(w.rating);l.history.append(l.rating)
                self.game_receipts.append(receipt)
                self.team_receipts.setdefault(g.winner,[]).append(receipt)
                self.team_receipts.setdefault(g.loser,[]).append(receipt)
                # Store the opponent strength *as it was before* this date.
                self.sos_sums[g.winner]+=receipt["preLoserElo"]-CENTER
                self.sos_sums[g.loser]+=receipt["preWinnerElo"]-CENTER
                self.sos_counts[g.winner]+=1
                self.sos_counts[g.loser]+=1
            self.last_day=day
        # Prior-anchored Elo is not required to sum to 1500*N. The
        # updates must still be exactly zero-sum relative to initial mass.
        start=sum(self.initial_ratings.get(t,CENTER) for t in self.states)
        end=sum(s.rating for s in self.states.values())
        self.conservation_error=end-start
        if not math.isclose(start,end,abs_tol=1e-7):
            raise ValueError("Elo 2.0 ratings failed zero-sum delta conservation")
        return self

    def standings(self) -> list[dict]:
        return [
            {"teamId":str(t.team_id),"name":t.name,
             "rating":round(t.rating,1),
             "prior":round(self.initial_ratings.get(t.team_id,CENTER),1),
             "wins":t.wins,"losses":t.losses,
             "causalSosAdjustment":round(self.schedule_adjustment(t.team_id),2),
             "sosPreviousOpponentGames":self.sos_counts[t.team_id]}
            for t in sorted(self.states.values(),
                            key=lambda s:(-s.rating,s.name,s.team_id))
        ]


def paired_metrics(control:list[dict],challenger:list[dict],
                   subset:set[str]|None=None)->dict:
    """Same games, identical IDs and date embargo, no cherry-picked fixtures."""
    a={r["contestId"]:r for r in control}
    b={r["contestId"]:r for r in challenger}
    if len(a)!=len(control) or len(b)!=len(challenger) or set(a)!=set(b):
        raise ValueError("Different or duplicate game cohorts for comparison")
    diffs=[];acc_a=acc_b=0;cal_a=[];cal_b=[]
    bins_a=[[0,0.0,0.0] for _ in range(5)]
    bins_b=[[0,0.0,0.0] for _ in range(5)]
    for ident in sorted(a):
        x,y=a[ident],b[ident]
        if (x["dayNum"]!=y["dayNum"] or x["winnerId"]!=y["winnerId"]
            or x["loserId"]!=y["loserId"]):
            raise ValueError("Paired source event mismatches")
        if subset is not None and ident not in subset:
            continue
        pa=float(x["winnerProbability"]);pb=float(y["winnerProbability"])
        diffs.append(((1-pa)**2,(1-pb)**2,ident))
        acc_a+=1 if pa>.5 else .5 if pa==.5 else 0
        acc_b+=1 if pb>.5 else .5 if pb==.5 else 0
        cal_a.append(-math.log(max(pa,1e-12)))
        cal_b.append(-math.log(max(pb,1e-12)))
        # Orientation by immutable numeric ID, not hindsight winner side:
        # 5 reliability bins for P(first team ID wins) versus that outcome.
        first_won=1.0 if x["winnerId"]<x["loserId"] else 0.0
        for prob,bins in ((pa,bins_a),(pb,bins_b)):
            p_first=prob if first_won else 1-prob
            index=min(4,int(p_first*5))
            bins[index][0]+=1
            bins[index][1]+=p_first
            bins[index][2]+=first_won
    n=len(diffs)
    if not n:
        return {"games":0,"baselineBrier":None,"challengerBrier":None,
                "brierGain":None,"baselineAccuracy":None,"challengerAccuracy":None,
                "baselineLogLoss":None,"challengerLogLoss":None}
    left=sum(x for x,_,_ in diffs)/n
    right=sum(y for _,y,_ in diffs)/n
    def ece(bins:list[list[float]])->float:
        return sum(abs(p/c-y/c)*c for c,p,y in bins if c)/n
    return {"games":n,
            "calibrationBinPolicy":"Five equal-width bins, first team numerical ID orientation, no label leakage",
            "baselineCalibrationBins":bins_a,
            "challengerCalibrationBins":bins_b,
            "baselineECE":round(ece(bins_a),6),
            "challengerECE":round(ece(bins_b),6),
            "baselineBrier":round(left,6),
            "challengerBrier":round(right,6),
            "brierGain":round(left-right,6),
            "baselineAccuracy":round(acc_a/n,6),
            "challengerAccuracy":round(acc_b/n,6),
            "baselineLogLoss":round(sum(cal_a)/n,6),
            "challengerLogLoss":round(sum(cal_b)/n,6)}

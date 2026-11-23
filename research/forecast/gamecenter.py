"""Source-verified 2027 upcoming Game Center with relevant prior-game evidence.

No ESPN event becomes a real scheduled pick unless it reports STATUS_SCHEDULED,
has an explicit start >15 minutes after forecast generation, and falls inside
the regular-season cutoff. No model odds for ambiguous or unverified NCAA↔ESPN
team identities. Previously played source games are evidence only, not an
officially calibrated causal attribution of the current probability.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime,timedelta,timezone,date
from pathlib import Path
from zoneinfo import ZoneInfo

from .snapshot import (parse_time,retrieve_fixture,
                       forecast_scheduled,BUFFER_MINUTES,ESPN_BASE)
from .live import REGULAR_SEASON_CUTOFF

LOCAL=ZoneInfo("America/New_York")
DAYS_AHEAD=5


def _evidence(games:list[dict],team:str,reference_date:str,limit:int=5)->list[dict]:
    result=[]
    for g in reversed(games):
        if g["date"]>=reference_date or team not in (g["home"],g["away"]):
            continue
        is_home=g["home"]==team
        own=int(g["homeScore"] if is_home else g["awayScore"])
        against=int(g["awayScore"] if is_home else g["homeScore"])
        result.append({"id":g["id"],"date":g["date"],"opponent":g["away"] if is_home else g["home"],
                       "home":is_home,"for":own,"against":against,
                       "outcome":"W" if own>against else "L"})
        if len(result)>=limit:
            break
    return result


def _common(games:list[dict],home:str,away:str,cutoff_date:str)->list[dict]:
    def one(t:str):
        result={}
        for g in games:
            if g["date"]>=cutoff_date or t not in (g["home"],g["away"]):
                continue
            opponent=g["away"] if g["home"]==t else g["home"]
            margin=(g["homeScore"]-g["awayScore"])*(1 if g["home"]==t else -1)
            result.setdefault(opponent,[]).append((g["date"],margin))
        return result
    one_h=one(home);one_a=one(away)
    output=[]
    for opponent in set(one_h)&set(one_a):
        left=one_h[opponent][-1]
        right=one_a[opponent][-1]
        output.append({"opponent":opponent,"homeResultDate":left[0],
                       "awayResultDate":right[0],
                       "homeMargin":left[1],"awayMargin":right[1]})
    return sorted(output,key=lambda x:(max(x["homeResultDate"],x["awayResultDate"]),
                                       x["opponent"]),reverse=True)[:5]


def _team_detail(row:dict,history:list[dict])->dict:
    n=row["wins"]+row["losses"]
    return {"name":row["name"],"teamId":row["teamId"],"rating":row["rating"],
            "trend":row.get("trend",0),"adaptiveRating":row.get("adaptiveRating"),
            "volatility":row.get("volatility"),
            "wins":row["wins"],"losses":row["losses"],
            "conference":row.get("conference"),"divisionIConfirmed":row.get("divisionIConfirmed"),
            "opponentAverageElo":row.get("opponentAverageElo"),
            "recentGames":history,
            "ratingHistory":row.get("history",[])}


def build_game_center(scoreboards:list[dict],ratings:dict,games:list[dict],
                      now:datetime,online_model:dict|None=None,
                      state_space:dict|None=None,
                      opponent_model:dict|None=None,ensemble_model:dict|None=None)->dict:
    if now.tzinfo is None:
        raise ValueError("scheduled snapshot requires timezone-aware clock")
    now=now.astimezone(timezone.utc)
    if ratings.get("season")!=2027 or ratings.get("mode")!="current" or not ratings.get("retrievedAtUtc"):
        raise ValueError("expected current verified 2027 season")
    if len(games)!=ratings.get("regularSeasonGames"):
        raise ValueError("source games and ratings must describe the same accepted games")
    if state_space and state_space.get("ratingRetrievedAtUtc")!=ratings["retrievedAtUtc"]:
        raise ValueError("state space does not share source snapshot")
    included_before=now.astimezone(LOCAL).date().isoformat()
    eligible_games=sorted((g for g in games if g["date"]<included_before),
                          key=lambda g:(g["date"],g["id"]))
    by_team_id={team["teamId"]:team for team in ratings["teams"]}
    if len(by_team_id)!=len(ratings["teams"]):
        raise ValueError("Duplicated current-season team identity")
    # Reuse the exact probability engine used by Git's immutable pregame ledger.
    forecast=forecast_scheduled(scoreboards,ratings,now,online_model,state_space,opponent_model,ensemble_model,
                                scored_games=games)
    frozen={p["eventId"]:p for p in forecast["predictions"]}
    results={}
    coverage={"futureScheduled":0,"eligibleForecasts":0,"unmatchedOrAmbiguous":0,
              "tooCloseOrStarted":0,"duplicateEvents":0}
    for board in scoreboards:
        if not isinstance(board,dict) or not isinstance(board.get("events"),list):
            raise ValueError("ESPN schedule must include events")
        for ev in board["events"]:
            eid=str(ev.get("id") or "").strip()
            status=((ev.get("status") or {}).get("type") or {})
            if not eid or status.get("name")!="STATUS_SCHEDULED" or status.get("completed"):
                continue
            try:
                starts=parse_time(ev["date"])
            except (KeyError,TypeError,ValueError):
                continue
            edate=starts.astimezone(LOCAL).date().isoformat()
            if date.fromisoformat(edate)>REGULAR_SEASON_CUTOFF:
                continue
            if eid in results:
                coverage["duplicateEvents"]+=1
                continue
            if starts <= now+timedelta(minutes=BUFFER_MINUTES):
                coverage["tooCloseOrStarted"]+=1
                continue
            competitions=ev.get("competitions") or []
            if not competitions or not isinstance(competitions[0],dict):
                continue
            competitors=competitions[0].get("competitors") or []
            side_h=[s for s in competitors if s.get("homeAway")=="home"]
            side_a=[s for s in competitors if s.get("homeAway")=="away"]
            if len(side_h)!=1 or len(side_a)!=1:
                continue
            def label(side):
                team=side.get("team") or {}
                return str(team.get("location") or team.get("shortDisplayName") or
                           team.get("displayName") or "Unidentified program").strip()
            # Only use the actual archived-forecast probability engine's
            # unique identity decision. No second approximate name join in
            # this presentation module is allowed to override it.
            pick=frozen.get(eid)
            coverage["futureScheduled"]+=1
            home=by_team_id.get(pick["homeTeamId"]) if pick else None
            away=by_team_id.get(pick["awayTeamId"]) if pick else None
            if pick and home and away:
                coverage["eligibleForecasts"]+=1
                h_hist=_evidence(eligible_games,home["name"],included_before)
                a_hist=_evidence(eligible_games,away["name"],included_before)
                meetings=[g for g in eligible_games if set((g["home"],g["away"])) ==
                          set((home["name"],away["name"]))][-4:]
                home_input={**home, **((pick.get("ratingInputs") or {}).get("home") or {})}
                away_input={**away, **((pick.get("ratingInputs") or {}).get("away") or {})}
                diff=home_input["rating"]-away_input["rating"]
                neutral=pick["neutralSite"]
                factors=[
                    {"title":"Strength gap","value":round(diff,1),
                     "detail":"Home minus away source Elo rating. Both include previous results."},
                    {"title":"Venue adjustment","value":0 if neutral else 65,
                     "detail":"Elo points credited to the scheduled home team; zero at a neutral site."},
                    {"title":"Recent trend","value":round(home_input.get("trend",0)-away_input.get("trend",0),1),
                     "detail":"Difference in bounded recent Elo adjustments; informs the logistic challenger only."},
                    {"title":"Opponent quality","value":round((home_input.get("opponentAverageElo") or 1500)-
                                            (away_input.get("opponentAverageElo") or 1500),1),
                     "detail":"Descriptive difference in average opponents' current Elo; not a separate model coefficient."}
                ]
                if opponent_model is not None:
                    candidate=opponent_model.get("strengths",{})
                    if home["name"] in candidate and away["name"] in candidate:
                        factors.append({
                            "title":"Opponent-adjusted signal",
                            "value":round(candidate[home["name"]]["eloAdjustment"]-
                                          candidate[away["name"]]["eloAdjustment"],1),
                            "detail":"Experimental pre-date surprise margins relative to opponent Elo. Research comparison only, not the active forecast formula."
                        })
                item={"eventId":eid,"scheduledStartUtc":pick["scheduledStartUtc"],
                      "scheduledEasternDate":edate,
                      "neutralSite":neutral,"home":home["name"],"away":away["name"],
                      "homeTeamId":home["teamId"],"awayTeamId":away["teamId"],
                      "homeWinProbability":pick["homeWinProbability"],
                      "baselineHomeWinProbability":pick["baselineHomeWinProbability"],
                      "challengerHomeWinProbability":pick.get("challengerHomeWinProbability"),
                      "stateSpaceHomeWinProbability":pick.get("stateSpaceHomeWinProbability"),
                      "opponentAdjustedHomeWinProbability":pick.get("opponentAdjustedHomeWinProbability"),
                      "adaptiveStateSpaceHomeWinProbability":pick.get("adaptiveStateSpaceHomeWinProbability"),
                      "ensembleHomeWinProbability":pick.get("ensembleHomeWinProbability"),
                      "ensembleResearchWeight":pick.get("ensembleResearchWeight"),
                      "ensembleComponentCount":pick.get("ensembleComponentCount"),
                      "model":pick["model"],"modelId":pick.get("modelId"),
                      "ratingReplayMode":pick.get("ratingReplayMode"),
                      "ratingSourceIncludedThroughDate":pick.get("ratingSourceIncludedThroughDate"),
                      "status":"ready","reason":None,
                      "homeProfile":_team_detail(home_input,h_hist),
                      "awayProfile":_team_detail(away_input,a_hist),
                      "factors":factors,
                      "headToHead":[{"date":g["date"],"home":g["home"],"away":g["away"],
                                     "homeScore":g["homeScore"],"awayScore":g["awayScore"]} for g in reversed(meetings)],
                      "commonOpponents":_common(eligible_games,home["name"],away["name"],included_before),
                      "driftWatch":{
                          "home":(state_space or {}).get("adaptiveStrengths",{}).get(home["name"],{}).get("driftWatch"),
                          "away":(state_space or {}).get("adaptiveStrengths",{}).get(away["name"],{}).get("driftWatch"),
                          "homeInnovations":(state_space or {}).get("adaptiveStrengths",{}).get(home["name"],{}).get("recentStandardizedInnovations",[]),
                          "awayInnovations":(state_space or {}).get("adaptiveStrengths",{}).get(away["name"],{}).get("recentStandardizedInnovations",[]),
                      }}
            else:
                coverage["unmatchedOrAmbiguous"]+=1
                reason_code=forecast.get("rejectionReasons",{}).get(eid,"unverified-team-identity")
                reason=("A safe prior-date Elo replay was unavailable. This game stays pending rather than using same-day outcomes."
                        if reason_code=="missing-verified-prior-date-replay" else
                        "One or both ESPN schools could not be linked to a uniquely source-verified NCAA rated team; an identity guess would make the forecast unreliable.")
                item={"eventId":eid,"scheduledStartUtc":starts.isoformat().replace("+00:00","Z"),
                      "scheduledEasternDate":edate,"neutralSite":bool(competitions[0].get("neutralSite")),
                      "home":label(side_h[0]),"away":label(side_a[0]),
                      "homeWinProbability":None,"status":"unmatched",
                      "reasonCode":reason_code,"reason":reason}
            results[eid]=item
    return {"schemaVersion":1,"season":2027,"type":"verified-future-fixtures",
            "generatedAtUtc":now.isoformat().replace("+00:00","Z"),
            "ratingRetrievedAtUtc":ratings["retrievedAtUtc"],
            "lastIncludedGameDate":ratings["lastGameDate"],
            "scheduleSource":ESPN_BASE,"ratingSource":ratings.get("sourceUrl"),
            "timeBufferMinutes":BUFFER_MINUTES,"daysAhead":DAYS_AHEAD,
            "coverage":coverage,"games":sorted(results.values(),key=lambda x:(x["scheduledStartUtc"],x["eventId"])),
            "limitations":["ESPN scheduled fixtures are not a verified actual tipoff clock.",
                           "Only source-matched, future-start, unambiguous programs receive win probabilities.",
                           "Related completed games are descriptive evidence of form, not independent proofs of a winner.",
                           "Scores, odds and model form refresh on scheduled GitHub Actions, not second-by-second live streaming.",
                           "No bracket seed or field is asserted before the NCAA officially releases it."]}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--online-model",type=Path)
    p.add_argument("--state-space",type=Path)
    p.add_argument("--opponent-model",type=Path)
    p.add_argument("--ensemble-model",type=Path)
    p.add_argument("--scoreboards-json",type=Path,help="Hermetic list of ESPN scoreboard dictionaries")
    p.add_argument("--out",type=Path,default=Path("web/public/current/upcoming.json"))
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    ratings=json.loads(args.ratings.read_text(encoding="utf-8"))
    games_file=json.loads(args.games.read_text(encoding="utf-8"))
    if games_file.get("retrievedAtUtc")!=ratings.get("retrievedAtUtc") or games_file.get("season")!=2027:
        raise ValueError("Current score/ratings source snapshot mismatch")
    model=json.loads(args.online_model.read_text(encoding="utf-8")) if args.online_model else None
    state=json.loads(args.state_space.read_text(encoding="utf-8")) if args.state_space else None
    opponent=json.loads(args.opponent_model.read_text(encoding="utf-8")) if args.opponent_model else None
    ensemble=json.loads(args.ensemble_model.read_text(encoding="utf-8")) if args.ensemble_model else None
    if args.scoreboards_json:
        boards=json.loads(args.scoreboards_json.read_text(encoding="utf-8"))
    else:
        days=[now.astimezone(LOCAL).date()+timedelta(days=i) for i in range(DAYS_AHEAD)]
        boards=[]
        failures=[]
        for day in days:
            try:
                boards.append(retrieve_fixture(day))
            except (OSError,ValueError,TimeoutError) as exc:
                failures.append(f"{day.isoformat()}: {exc}")
        if not boards:
            # Protect the core score/rating refresh from an ESPN outage.
            # Emit an EXPLICIT unavailable status, never an invented empty
            # schedule or fabricated fixture probability.
            boards=[{"events":[]}]
        if failures:
            print("WARNING: ESPN schedule days unavailable; current game center incomplete: "+"; ".join(failures))
    output=build_game_center(boards,ratings,games_file["games"],now,model,state,opponent,ensemble)
    if not args.scoreboards_json and failures:
        output["sourceWarnings"]=failures
        output["scheduleSourceAvailable"]=len(failures)<DAYS_AHEAD
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(f"Game Center: {output['coverage']['eligibleForecasts']} verified probabilities "
          f"from {output['coverage']['futureScheduled']} future sourced fixtures; "
          f"published {args.out}")


if __name__=="__main__":
    main()

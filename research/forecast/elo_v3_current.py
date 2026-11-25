"""Build a timestamp-matched current Elo 3.0 team-ranking artifact.

Never assign provisional historical school-name priors. All 2027 IDs are
source-local and have neutral priors until authoritative cross-year IDs exist.
"""
import argparse,json
from pathlib import Path
from .elo_v2_current import _to_games
from .elo_v3 import replay

def build(games,ratings,boxes):
    if games.get("season")!=2027 or ratings.get("season")!=2027 or ratings.get("mode")!="current":
        raise ValueError("Expected verified current 2027 source")
    stamp=ratings.get("retrievedAtUtc")
    if not stamp or games.get("retrievedAtUtc")!=stamp or boxes.get("retrievedAtUtc")!=stamp:
        raise ValueError("Source retrieval timestamps differ")
    records=games["games"]
    if len(records)!=ratings["regularSeasonGames"]:raise ValueError("Scored game count differs")
    fixtures,names=_to_games(records)
    if not fixtures:raise ValueError("No accepted scored games")
    # Current source box pairs use exact source contest IDs and full school
    # names. A mismatch is an error, not an inferred alias.
    lookup={g.contest_id:g for g in fixtures}
    records_by_id={str(g["id"]):g for g in records}
    pairs={}
    for item in boxes.get("games",[]):
        key=str(item["id"])
        g=lookup.get(key)
        if g is None:raise ValueError("Unmatched paired box contest")
        home_won=(names[g.winner]==item["home"])
        if (names[g.winner] not in (item["home"],item["away"]) or
            names[g.loser] not in (item["home"],item["away"]) or
            item["date"]!=records_by_id[key]["date"]):
            raise ValueError("Paired box school identity mismatch")
        winner=item["homeBox"] if home_won else item["awayBox"]
        loser=item["awayBox"] if home_won else item["homeBox"]
        pairs[key]={"winnerId":g.winner,"loserId":g.loser,"dayNum":g.day_num,
                    "winner":winner,"loser":loser}
    if len(pairs)!=len(boxes.get("games",[])):raise ValueError("Duplicate paired box")
    report=replay(fixtures,paired_boxes=pairs)
    source={t["name"]:t for t in ratings["teams"]}
    rows=[]
    for tid,name in names.items():
        original=source.get(name)
        if original is None:raise ValueError("Missing team from source ratings")
        rows.append({"teamId":original["teamId"],"name":name,
                     "rating":round(report["ratings"].get(tid,1500.),2),
                     "games":report["gamesPlayed"].get(tid,0),
                     "record":str(original["wins"])+"-"+str(original["losses"]),
                     "sourceRating":original["rating"],
                     "boxGames":report["boxGames"].get(tid,0),
                     "fourFactorGames":report["fourFactorGames"].get(tid,0)})
    if len(rows)!=len(ratings["teams"]):raise ValueError("Team coverage mismatch")
    rows.sort(key=lambda t:(-t["rating"],t["name"]))
    for i,row in enumerate(rows,1):row["rank"]=i
    return {"schemaVersion":1,"season":2027,"model":"elo3","status":"current-research-primary-teams",
            "retrievedAtUtc":stamp,"lastGameDate":ratings["lastGameDate"],
            "sourceGames":len(fixtures),"teams":rows,
            "pairedBoxes":report["pairedBoxes"],"boxEligible":report["boxEligible"],
            "homeAdvantage":report["finalHomeAdvantage"],
            "previousSeasonPriors":"neutral-until-authoritative-cross-year-ID",
            "limitations":["Elo 3.0 research ratings, not a proven better forward predictor.",
                           "No provisional exact-name historical priors used.",
                           "Missing source box scores do not become invented efficiency.",
                           "Archived published picks remain on their originally recorded models."]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--games",type=Path,required=True)
    p.add_argument("--ratings",type=Path,required=True)
    p.add_argument("--boxes",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=build(*[json.loads(path.read_text()) for path in (a.games,a.ratings,a.boxes)])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("Elo 3.0 current teams:",len(result["teams"]),"paired boxes:",result["pairedBoxes"])
if __name__=="__main__":main()

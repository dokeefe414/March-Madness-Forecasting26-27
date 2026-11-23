"use client";
import {useEffect,useMemo,useState} from "react";
import type {Team,RatingsDataset} from "../lib/models";
import {matchupProbability} from "../lib/models";
import GameAudit, {type ArchivedSnapshot,type ArchivedSettlement} from "./GameAudit";
import MatchupIntelligence from "./MatchupIntelligence";
import DailyDesk from "./DailyDesk";
import RecentFinals,{type RecentFinalsReport} from "./RecentFinals";
import ScoreProjection from "./ScoreProjection";

const basePath=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Past={id:string;date:string;opponent:string;home:boolean;for:number;against:number;outcome:"W"|"L"};
type Profile={name:string;teamId:string;rating:number;trend:number;adaptiveRating?:number;volatility?:number;
  wins:number;losses:number;conference?:string;opponentAverageElo?:number;recentGames:Past[];ratingHistory:number[]};
type Factor={title:string;value:number;detail:string};
type Fixture={eventId:string;scheduledStartUtc:string;scheduledEasternDate:string;neutralSite:boolean;
  home:string;away:string;homeTeamId?:string;awayTeamId?:string;homeWinProbability:number|null;
  baselineHomeWinProbability?:number;challengerHomeWinProbability?:number|null;
  stateSpaceHomeWinProbability?:number|null;model?:string;status:"ready"|"unmatched";
  opponentAdjustedHomeWinProbability?:number|null;
  adaptiveStateSpaceHomeWinProbability?:number|null;
  ensembleHomeWinProbability?:number|null;ensembleResearchWeight?:number|null;ensembleComponentCount?:number|null;
  driftWatch?:{home:boolean|null;away:boolean|null;homeInnovations?:number[];awayInnovations?:number[]};
  modelId?:string|null;reason?:string|null;reasonCode?:string|null;
  ratingReplayMode?:string|null;ratingSourceIncludedThroughDate?:string|null;
  homeProfile?:Profile;awayProfile?:Profile;
  factors?:Factor[];headToHead?:Array<{date:string;home:string;away:string;homeScore:number;awayScore:number}>;
  commonOpponents?:Array<{opponent:string;homeResultDate:string;awayResultDate:string;homeMargin:number;awayMargin:number}>};
type Schedule={schemaVersion:number;generatedAtUtc:string;ratingRetrievedAtUtc:string;
  lastIncludedGameDate:string;coverage:{futureScheduled:number;eligibleForecasts:number;unmatchedOrAmbiguous:number};
  sourceWarnings?:string[];scheduleSourceAvailable?:boolean;games:Fixture[]};
type Forward={score:{games:number;accuracy:number|null;brier:number|null};
  settledUniqueGames:number;forecastedUniqueGames:number;
  shadowComparison?:{pairedGames:number;eloBrier:number|null;challengerBrier:number|null}};
type Ledger={uniqueGames?:Forward;snapshots?:ArchivedSnapshot[];settlements?:ArchivedSettlement[]};
const percent=(v:number)=>(v*100).toFixed(1)+"%";
const when=(v:string)=>new Date(v).toLocaleString("en-US",{timeZone:"America/New_York",
  weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
const plus=(v:number)=> (v>0?"+":"")+v.toFixed(1);
function Marker({tag}:{tag:string}){return <span className="gc-tag">{tag}</span>;}

function GameReceipt({game}:{game:Past}){
  return <div className="gc-result"><span className={game.outcome==="W"?"gc-win":"gc-loss"}>{game.outcome}</span>
    <div><strong>{game.opponent}</strong><small>{game.date}</small></div>
    <b>{game.for}–{game.against}</b></div>;
}
function TeamStrengthCurve({team,values}:{team:string;values:number[]}){
  const valid=values.filter(v=>Number.isFinite(v));
  if(valid.length<2)return <p className="gc-curve-empty">Not enough earlier results to chart a real team trend.</p>;
  const lo=Math.min(...valid)-8,hi=Math.max(...valid)+8,span=Math.max(1,hi-lo);
  const x=(i:number)=>12+i*260/Math.max(1,valid.length-1);
  const y=(v:number)=>73-(v-lo)/span*56;
  const path=valid.map((v,i)=>(i===0?"M":"L")+x(i).toFixed(1)+","+y(v).toFixed(1)).join(" ");
  const gain=valid[valid.length-1]-valid[valid.length-2];
  return <div className="gc-team-trend"><div><small>EARLIER RESULTS → RATING CURVE</small>
     <strong>{gain>=0?"+":""}{gain.toFixed(1)} ELO LAST RECORDED GAME</strong></div>
     <svg viewBox="0 0 285 84" role="img" aria-label={team+" actual earlier-game Elo strength from "+valid[0].toFixed(1)+" to "+valid[valid.length-1].toFixed(1)}>
        <line x1="12" x2="274" y1="73" y2="73" stroke="#37645b" strokeDasharray="4 6"/>
        <path d={path} fill="none" stroke="#baffcf" strokeWidth="2.7" strokeLinejoin="round" strokeLinecap="round"/>
        <circle cx={x(valid.length-1)} cy={y(valid[valid.length-1])} r="3.8" fill="#e6ffd8"/>
     </svg><p>One change per sourced game, not a real-time possession chart.</p></div>;
}
function ProfilePanel({profile,side}:{profile:Profile;side:"HOME"|"AWAY"}){
  return <div className="gc-profile"><div className="gc-profile-heading"><small>{side} / RATING INPUTS</small>
    <h4>{profile.name}</h4><span>{profile.conference||"Conference unverified"}</span></div>
    <div className="gc-profile-stats">
      <div><small>RECORD</small><strong>{profile.wins}–{profile.losses}</strong></div>
      <div><small>ELO</small><strong>{profile.rating.toFixed(0)}</strong></div>
      <div><small>RECENT FORM</small><strong>{plus(profile.trend)}</strong></div>
      <div><small>AVG OPP ELO</small><strong>{profile.opponentAverageElo?.toFixed(0)??"—"}</strong></div>
    </div>
    <TeamStrengthCurve team={profile.name} values={profile.ratingHistory||[]}/>
    <p className="gc-eyebrow">LATEST VERIFIED PRIOR-DATE RESULTS</p>
    <div className="gc-results">{profile.recentGames.length?
      profile.recentGames.map(g=><GameReceipt key={g.id} game={g}/>):
      <p className="gc-empty">No earlier source games for this program.</p>}</div>
  </div>;
}

export default function GameCenter({onOpenAccuracy,onOpenModels,onOpenSelection}:{onOpenAccuracy?:()=>void;onOpenModels?:()=>void;onOpenSelection?:()=>void}){
  const [schedule,setSchedule]=useState<Schedule|null>(null);
  const [ratings,setRatings]=useState<RatingsDataset|null>(null);
  const [forward,setForward]=useState<Forward|null>(null);
  const [ledger,setLedger]=useState<Ledger|null>(null);
  const [archiveHealth,setArchiveHealth]=useState<{status:string;message:string;lastArchiveUtc:string|null}|null>(null);
  const [recentFinals,setRecentFinals]=useState<RecentFinalsReport|null>(null);
  const [refreshing,setRefreshing]=useState(false);
  const [refreshVersion,setRefreshVersion]=useState(0);
  const refreshPublished=()=>setRefreshVersion(value=>value+1);
  const [copied,setCopied]=useState(false);
  const [problem,setProblem]=useState("");
  const [search,setSearch]=useState("");
  const [day,setDay]=useState("all");
  const [teamFilter,setTeamFilter]=useState("");
  const [selectedId,setSelectedId]=useState("");
  const [showAll,setShowAll]=useState(false);
  const [watchedTeams,setWatchedTeams]=useState<string[]>([]);
  const [onlyWatched,setOnlyWatched]=useState(false);
  const [watchTarget,setWatchTarget]=useState("");
  useEffect(()=>{
    try {
      const stored=JSON.parse(window.localStorage.getItem("marchforecast-watchlist-v20")||"[]");
      if(Array.isArray(stored))setWatchedTeams(stored.filter(x=>typeof x==="string").slice(0,12));
    } catch {setWatchedTeams([]);}
  },[]);
  const [a,setA]=useState("");
  const [b,setB]=useState("");
  const [now,setNow]=useState(0);
  useEffect(()=>{
    // Keep the scheduled-start warning accurate while a page stays open.
    const refresh=()=>setNow(Date.now());
    refresh();
    const timerId=window.setInterval(refresh,60_000);
    return()=>window.clearInterval(timerId);
  },[]);
  useEffect(()=>{
    // Static GitHub Pages snapshots do not push updates to an already-open
    // browser. Check the published JSON every ten minutes and on tab return.
    // Nothing here changes the immutable original pretipoff prediction ledger.
    const timer=window.setInterval(refreshPublished,10*60_000);
    const onVisible=()=>{if(document.visibilityState==="visible")refreshPublished();};
    document.addEventListener("visibilitychange",onVisible);
    return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",onVisible);};
  },[]);
  useEffect(()=>{
    let alive=true;
    setRefreshing(true);
    Promise.all([
      fetch(basePath+"/current/upcoming.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Upcoming-game snapshot is not published.");return r.json() as Promise<Schedule>}),
      fetch(basePath+"/current/2027.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Current NCAA-source ratings unavailable.");return r.json() as Promise<RatingsDataset>}),
      fetch(basePath+"/forecasts/index.json",{cache:"no-store"}).then(r=>r.ok?r.json():null).catch(()=>null) as Promise<Ledger|null>,
      fetch(basePath+"/current/archive-health.json",{cache:"no-store"}).then(r=>r.ok?r.json():null).catch(()=>null),
      fetch(basePath+"/current/recent-finals.json",{cache:"no-store"}).then(r=>r.ok?r.json():null).catch(()=>null) as Promise<RecentFinalsReport|null>,
    ]).then(([s,r,l,h,latestFinals])=>{
      if(!alive)return;
      if(s.schemaVersion!==1||!Array.isArray(s.games)||r.mode!=="current"||r.season!==2027)
        throw new Error("Scheduled game/ratings source validation failed.");
      setSchedule(s);setRatings(r);setForward(l?.uniqueGames||null);setLedger(l);
      setArchiveHealth(h);
      // Reject mismatched score and rating snapshots, not just HTTP 200.
      setRecentFinals(latestFinals?.schemaVersion===1&&
        latestFinals?.season===2027&&latestFinals?.ratingRetrievedAtUtc===r.retrievedAtUtc?
        latestFinals:null);
      setA(old=>old&&r.teams.some(t=>t.teamId===old)?old:(r.teams[0]?.teamId||""));
      setB(old=>old&&r.teams.some(t=>t.teamId===old)?old:(r.teams[1]?.teamId||""));
      const params=new URLSearchParams(window.location.search);
      const team=params.get("team");
      if(team&&r.teams.some(t=>t.teamId===team))setTeamFilter(team);
      const link=params.get("game");
      const archivedIds=new Set((l?.settlements||[]).map(x=>x.eventId));
      const initial=(s.games.find(g=>g.eventId===link)||archivedIds.has(link||""))?
        (link||""):s.games.find(g=>g.status==="ready")?.eventId||s.games[0]?.eventId||"";
      setSelectedId(previous=>
        previous&&(s.games.some(g=>g.eventId===previous)||archivedIds.has(previous))?
        previous:initial);
      setNow(Date.now());
      setProblem("");
    }).catch((e:Error)=>{if(alive)setProblem(e.message)})
      .finally(()=>{if(alive)setRefreshing(false)});
    return()=>{alive=false};
  },[refreshVersion]);
  const eligible=useMemo(()=>schedule?.games||[],[schedule]);
  function toggleWatch(id:string|undefined){
    if(!id||!ratings?.teams.some(t=>t.teamId===id))return;
    setWatchedTeams(current=>{
      const next=current.includes(id)?current.filter(t=>t!==id):current.length>=12?current:[...current,id];
      try{window.localStorage.setItem("marchforecast-watchlist-v20",JSON.stringify(next))}catch{}
      return next;
    });
  }
  const watchedUpcoming=useMemo(()=>eligible.filter(g=>
    (watchedTeams.includes(g.homeTeamId||"")||watchedTeams.includes(g.awayTeamId||""))&&
    (!now||Date.parse(g.scheduledStartUtc)>now)).sort((a,b)=>a.scheduledStartUtc.localeCompare(b.scheduledStartUtc)).slice(0,6),
    [eligible,watchedTeams,now]);
  const availableDays=useMemo(()=>[...new Set(eligible.map(x=>x.scheduledEasternDate))].sort(),[eligible]);
  const rows=useMemo(()=>eligible.filter(x=>(day==="all"||x.scheduledEasternDate===day) &&
      (!teamFilter||x.homeTeamId===teamFilter||x.awayTeamId===teamFilter) &&
      (!onlyWatched||watchedTeams.includes(x.homeTeamId||"")||watchedTeams.includes(x.awayTeamId||"")) &&
      (showAll||!now||new Date(x.scheduledStartUtc).getTime()>now) &&
      (x.home+" "+x.away).toLowerCase().includes(search.toLowerCase())),
    [eligible,search,day,showAll,now,teamFilter,onlyWatched,watchedTeams]);
  // Never display an expired source capture as a currently upcoming pick.
  // Started games remain inspectable only when the user explicitly enables it.
  const settledGames=useMemo(()=>{
    const unique=new Map<string,ArchivedSettlement>();
    for(const r of ledger?.settlements||[]){
      if(!unique.has(r.eventId))unique.set(r.eventId,r);
    }
    return [...unique.values()].sort((a,b)=>b.actualResultDate.localeCompare(a.actualResultDate))
      .slice(0,12);
  },[ledger]);
  const archivedGame=settledGames.find(x=>x.eventId===selectedId);
  const selected=rows.find(x=>x.eventId===selectedId)||
                 (archivedGame?undefined:rows[0]);
  const alreadyStarted=Boolean(selected&&now&&new Date(selected.scheduledStartUtc).getTime()<=now);
  const availableShadows=selected?([
    ["Online logistic",selected.challengerHomeWinProbability],
    ["State space",selected.stateSpaceHomeWinProbability],
    ["Opponent adjusted",selected.opponentAdjustedHomeWinProbability],
    ["Adaptive state space",selected.adaptiveStateSpaceHomeWinProbability],
    ["Experimental ensemble",selected.ensembleHomeWinProbability],
  ] as Array<[string,number|null|undefined]>).filter((p):p is [string,number]=>
    typeof p[1]==="number"&&Number.isFinite(p[1])&&p[1]>0&&p[1]<1):[];
  const shadowDisagreements=selected?.homeWinProbability==null?0:availableShadows.filter(([,p])=>
    (p>.5)!==(selected.homeWinProbability!>.5) && p!==.5&&selected.homeWinProbability!==.5).length;

  const canCompare=ratings?.teams?.length && a&&b&&a!==b;
  const left=ratings?.teams.find(t=>t.teamId===a);
  const right=ratings?.teams.find(t=>t.teamId===b);
  const demo=canCompare&&left&&right?matchupProbability(left.rating,right.rating):null;
  const choose=(id:string)=>{
    setSelectedId(id);
    const url=new URL(window.location.href);url.searchParams.set("game",id);
    window.history.replaceState(null,"",url.toString());
    setCopied(false);
    // On mobile, move directly from the fixture card to its detailed model
    // analysis instead of making the user scroll through the full fixture list.
    document.getElementById("gc-match-detail")?.scrollIntoView({behavior:"smooth",block:"start"});
  };
  async function copyGameLink(){
    if(!selected&&!archivedGame)return;
    const url=new URL(window.location.href);
    url.searchParams.set("view","games");
    url.searchParams.set("game",selected?.eventId||archivedGame!.eventId);
    try{
      await navigator.clipboard.writeText(url.toString());
      setCopied(true);
    }catch{setCopied(false);}
  }
  const total=eligible.length;
  const easternParts=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(now||Date.now()));
  const datePart=(name:string)=>easternParts.find(p=>p.type===name)?.value||"";
  const easternDay=`${datePart("year")}-${datePart("month")}-${datePart("day")}`;
  const chooseToday=()=>{setDay(easternDay);setShowAll(false);setTeamFilter("");setSearch("");document.getElementById("gc-fixture-browser")?.scrollIntoView({block:"start",behavior:"smooth"});};
  return <section className="content-section gc" id="games">
    <div className="gc-hero">
      <div><span className="gc-overline"><span className="live-dot"/> THE NEXT MATCHUP IS YOURS TO EXPLORE</span>
        <h1>GAME <em>INTELLIGENCE.</em></h1>
        <p>Choose a real scheduled college basketball game. See the pregame win percentage, who the model favors, and the other games that shaped each team's rating.</p>
        <div className="gc-hero-chips"><Marker tag="REAL ESPN FIXTURES"/><Marker tag="VERIFIED NCAA TEAM LINKS"/><Marker tag="NO INVENTED ODDS"/></div>
      </div>
      <aside className="gc-hero-score"><small>REAL FORWARD FORECAST ACCURACY</small><strong>{forward?.score.accuracy!=null?percent(forward.score.accuracy):"—"}</strong>
        <span>{forward?.settledUniqueGames||0} uniquely settled future games</span>
        <p>{!forward?.settledUniqueGames?"Not a historical backtest. This percentage starts when real pretipoff predictions have settled.":"Every actual game counts once; repeated snapshots cannot inflate accuracy."}</p>
        {onOpenModels&&<button className="gc-accuracy-cta gc-model-cta" onClick={onOpenModels}>COMPARE THE MODELS ↗</button>}
        {onOpenAccuracy?<button className="gc-accuracy-cta" onClick={onOpenAccuracy}>OPEN ACCURACY & PICKS ↗</button>:
          <a href="#gc-accuracy-notes">HOW THIS IS MEASURED ↓</a>}
        <p className="gc-archive-health">ARCHIVE {archiveHealth?.status?.toUpperCase()||"UNVERIFIED"} · {archiveHealth?.message||"Public archive status has not been verified."}</p>
      </aside>
    </div>
    {selected?.status==="ready"&&selected.homeWinProbability!=null&&
      <div className="v19-game-glance" aria-label="Selected game quick prediction summary">
        <div><small>SELECTED MATCHUP</small><strong>{selected.away} at {selected.home}</strong><span>{when(selected.scheduledStartUtc)}</span></div>
        <div><small>ORIGINAL PUBLIC WINNER MODEL</small><strong>{selected.homeWinProbability>=.5?selected.home:selected.away} {percent(Math.max(selected.homeWinProbability,1-selected.homeWinProbability))}</strong><span>{selected.model||"Elo"} · {selected.ratingReplayMode==="prior-date-safe"?"Previous-date replay · ":""}{alreadyStarted?"Previously scheduled, not live in-game odds":"Source-frozen matchup at last update"}</span></div>
        <div><small>RESEARCH MODEL AGREEMENT</small><strong>{availableShadows.length?availableShadows.length-shadowDisagreements+"/"+availableShadows.length+" agree":"Not enough signals"}</strong><span>{shadowDisagreements>0?"Research models disagree on the favorite; see comparison below":"Agreement alone does not prove accuracy"}</span></div>
        <a href="#gc-match-detail">View this game's full breakdown ↓</a>
      </div>}
    <nav className="daily-shortcuts" aria-label="Explore March Forecast">
      <a href="#daily-desk">TODAY'S GAMES ↓</a>
      <button type="button" onClick={onOpenAccuracy}>ACCURACY & PICKS ↗</button>
      <button type="button" onClick={onOpenModels}>MODEL RESEARCH ↗</button>
      <button type="button" onClick={onOpenSelection}>ROAD TO MARCH ↗</button>
    </nav>
    {schedule&&<div id="daily-desk"><DailyDesk games={schedule.games} today={easternDay}
      health={archiveHealth} generatedAt={schedule.generatedAtUtc}
      settled={forward?.settledUniqueGames||0} onChoose={(id)=>{setDay("all");setShowAll(true);setTeamFilter("");setSearch("");choose(id);}}
      onToday={chooseToday}/></div>}
    <RecentFinals report={recentFinals}
      ncaaLastDate={ratings?.sourceReconciliation?.ncaaLastGameDate||ratings?.lastGameDate||null}
      eloLastDate={ratings?.lastGameDate||null}
      espnRatedGames={ratings?.sourceReconciliation?.ratedEspnOnlyFinals||0}
      onRefresh={refreshPublished} refreshing={refreshing}/>
    <div className="gc-intro" id="gc-fixture-browser"><div><span className="section-kicker">01 / THE VERIFIED SCHEDULE</span><h2>Pick a <span>game.</span></h2>
      <p>Future ESPN scheduled fixtures only. The scheduled site refresh updates probabilities as validated NCAA scores arrive. ESPN-confirmed recent finals are shown above, including results still awaiting NCAA rating-source confirmation.</p></div>
      <span className="gc-source-pill">{schedule?formatTime(schedule.generatedAtUtc):"CHECKING LATEST SOURCE…"}</span></div>
    {!schedule?<div className="premium-empty" role={problem?"alert":"status"}><h3>{problem||"LOADING REAL GAMES…"}</h3>
      <p>The site does not manufacture matchups if the schedule is unavailable.</p></div>:<>
      <div className="gc-toolbar">
        <label className="gc-search">SEARCH MATCHUP<input aria-label="Search upcoming games" value={search} onChange={e=>setSearch(e.target.value)} placeholder="School, conference, opponent…"/></label>
        <label className="gc-date">GAME DATE<select aria-label="Filter upcoming games by date" value={day} onChange={e=>setDay(e.target.value)}>
          <option value="all">All upcoming days</option>{availableDays.map(d=><option key={d} value={d}>{d}</option>)}</select></label>
        <label className="gc-date">TEAM<select aria-label="Filter fixtures by team" value={teamFilter}
          onChange={e=>{setTeamFilter(e.target.value);const url=new URL(window.location.href);
            if(e.target.value)url.searchParams.set("team",e.target.value);else url.searchParams.delete("team");
            window.history.replaceState(null,"",url.toString());}}>
          <option value="">All teams</option>{[...(ratings?.teams||[])].sort((x,y)=>x.name.localeCompare(y.name)).map(t=><option key={t.teamId} value={t.teamId}>{t.name}</option>)}
        </select></label>
        <label className="gc-check"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/> Include started since last refresh</label>
      </div>
      <section className="v20-watchlist" aria-label="Your favorite teams and upcoming games">
        <div className="v20-watch-header">
          <div><strong>MY TEAMS</strong><p>Follow up to 12 teams for quick matchups. Saved only in your browser—not linked to an account.</p></div>
          <label>CHOOSE TEAM
            <select aria-label="Choose a team to follow" value={watchTarget} onChange={e=>setWatchTarget(e.target.value)}>
              <option value="">Select a school…</option>
              {[...(ratings?.teams||[])].sort((a,b)=>a.name.localeCompare(b.name)).map(t=>
                <option key={t.teamId} value={t.teamId}>{t.name}</option>)}
            </select>
          </label>
          <button type="button" disabled={!watchTarget||(!watchedTeams.includes(watchTarget)&&watchedTeams.length>=12)}
            onClick={()=>watchTarget&&toggleWatch(watchTarget)}>
            {watchedTeams.includes(watchTarget)?"Remove team":"☆ Follow team"}
          </button>
          <button type="button" className={onlyWatched?"active":""} aria-pressed={onlyWatched}
            onClick={()=>setOnlyWatched(v=>!v)}>Only my teams</button>
        </div>
        {watchedTeams.length>0?<div className="v20-watch-chips">
          {watchedTeams.filter(id=>ratings?.teams.some(t=>t.teamId===id)).map(id=>
            <button type="button" key={id} onClick={()=>toggleWatch(id)}
              aria-label={"Unfollow "+(ratings?.teams.find(t=>t.teamId===id)?.name||id)}>
              ★ {ratings?.teams.find(t=>t.teamId===id)?.name} <span aria-hidden="true">×</span>
            </button>)}
        </div>:<p className="v12-subtle">No teams followed yet. Select a school above or star a team from a matchup report.</p>}
        {watchedUpcoming.length>0?<div className="v20-watch-games">
          <strong>UP NEXT FOR YOUR TEAMS</strong>
          {watchedUpcoming.map(g=><button type="button" key={g.eventId} onClick={()=>{
            setDay("all");setTeamFilter("");setSearch("");setOnlyWatched(false);choose(g.eventId);
          }}>
            <span>{when(g.scheduledStartUtc)}</span><b>{g.away} at {g.home}</b><span>{g.status==="ready"?"View forecast ↗":"Fixture listed / model pending"}</span>
          </button>)}
        </div>:watchedTeams.length>0?<p className="v12-subtle">No future source-listed games for followed teams in the published schedule. This does not mean they have no later games.</p>:null}
      </section>
      {schedule.sourceWarnings?.length?<p className="gc-warning" role="status">ESPN schedule partly unavailable; listed games may be incomplete. No missing schedule is filled in.</p>:null}
      {schedule.generatedAtUtc&&now-Date.parse(schedule.generatedAtUtc)>36*60*60*1000&&<p className="gc-warning" role="status">
         The published fixture snapshot is older than 36 hours. Details may have changed. Check the archive-health monitor before treating a percentage as current.
       </p>}
      <div className="gc-stage">
        <div className="gc-fixtures">
          <div className="gc-list-header"><strong>{rows.length} GAMES FOUND</strong><span>{schedule.coverage.eligibleForecasts} rated / {schedule.coverage.futureScheduled} future scheduled at capture</span></div>
          <div className="gc-fixtures-scroll">
            {rows.map(g=><button key={g.eventId} type="button" className={"gc-fixture"+(g.eventId===selected?.eventId?" gc-selected":"")} onClick={()=>choose(g.eventId)}>
              <div className="gc-fixture-top"><span>{when(g.scheduledStartUtc)}</span><span>{g.status==="ready"?"PREDICTION READY":g.reasonCode==="missing-verified-prior-date-replay"?"RATING REPLAY PENDING":"TEAM ID PENDING"}</span></div>
              <div className="gc-fixture-teams"><div><small>AWAY</small><strong>{g.away}</strong></div><span className="gc-at">@</span><div><small>{g.neutralSite?"NEUTRAL":"HOME"}</small><strong>{g.home}</strong></div></div>
              <div className="gc-fixture-bottom"><span>{g.model||"No verified rating match"}</span><b>{g.homeWinProbability==null?"—":percent(Math.max(g.homeWinProbability,1-g.homeWinProbability))+" favorite"}</b></div>
            </button>)}
            {!rows.length?<div className="gc-list-empty">No qualifying source fixtures in this view. Try another day or explore a hypothetical matchup below.</div>:null}
          </div>
        </div>
        <article className="gc-detail" id="gc-match-detail" aria-live="polite">
          {selected&&selected.status==="ready"&&selected.homeWinProbability!=null&&selected.homeProfile&&selected.awayProfile?
          <>
            {alreadyStarted&&<div className="gc-warning" role="status">HISTORICAL CAPTURE ONLY · The listed tipoff time has passed since the source refresh. This frozen percentage is not a live in-game forecast.</div>}
            <div className="gc-detail-cap"><span>MODEL MATCHUP REPORT / ESPN {selected.eventId}</span><span>{when(selected.scheduledStartUtc)}</span></div>
            <div className="gc-quick-actions">
              <button type="button" onClick={copyGameLink}>{copied?"LINK COPIED ✓":"COPY GAME ANALYSIS LINK ↗"}</button>
               <button type="button" onClick={()=>toggleWatch(selected.homeTeamId)}>
                 {watchedTeams.includes(selected.homeTeamId||"")?"★":"☆"} {watchedTeams.includes(selected.homeTeamId||"")?"Unfollow":"Follow"} {selected.home}
               </button>
               <button type="button" onClick={()=>toggleWatch(selected.awayTeamId)}>
                 {watchedTeams.includes(selected.awayTeamId||"")?"★":"☆"} {watchedTeams.includes(selected.awayTeamId||"")?"Unfollow":"Follow"} {selected.away}
               </button>
              {onOpenModels&&<button type="button" onClick={onOpenModels}>COMPARE FORECASTING MODELS ↗</button>}
            </div>
            <div className="gc-matchup-title"><div><small>ROAD</small><h3>{selected.away}</h3><span>{selected.awayProfile.wins}–{selected.awayProfile.losses}</span></div>
              <div className="gc-vs">VS</div><div><small>{selected.neutralSite?"NEUTRAL":"HOME"}</small><h3>{selected.home}</h3><span>{selected.homeProfile.wins}–{selected.homeProfile.losses}</span></div></div>
            <div className="gc-odds-head"><div><small>AWAY WIN PROBABILITY</small><strong>{percent(1-selected.homeWinProbability)}</strong></div>
              <span>PREDICTED WIN SHARE</span>
              <div><small>HOME WIN PROBABILITY</small><strong>{percent(selected.homeWinProbability)}</strong></div></div>
            <div className="gc-odds-bar" role="img" aria-label={selected.away+" "+percent(1-selected.homeWinProbability)+", "+selected.home+" "+percent(selected.homeWinProbability)}>
              <div style={{width:percent(1-selected.homeWinProbability)}}/></div>
            <p className="gc-model-name">{selected.model} · {selected.neutralSite?"No home advantage (neutral venue)":"65 Elo-point home adjustment"} · <strong>{selected.homeWinProbability>.5?selected.home:selected.away} favored</strong></p>
            <details className="v18-model-guide">
              <summary>What is this prediction based on? How does it differ from the score?</summary>
              <p><strong>Active game favorite:</strong> The displayed {selected.model||"Elo"} win probability is the model's probability of a win, not its projected score or a sportsbook spread.</p>
              <p><strong>Projected score:</strong> The points model below estimates scoring rates and pace using available source statistics. It is a separate experimental estimator, so its favorite may disagree with Elo.</p>
              {selected.ensembleHomeWinProbability!=null&&<p><strong>Experimental ensemble:</strong> {selected.home} {percent(selected.ensembleHomeWinProbability)} vs {selected.away} {percent(1-selected.ensembleHomeWinProbability)}. This frozen research-only probability combines Elo with {selected.ensembleComponentCount||"available"} shadow model signals; it is not the official public favorite.</p>}
              {selected.challengerHomeWinProbability!=null&&<p><strong>Other model research:</strong> Online challenger gives {selected.home} {percent(selected.challengerHomeWinProbability)}. Models can disagree because they learn from different strengths, time windows or regularization.</p>}
              <p><strong>Historical accuracy:</strong> The Model Lab evaluates earlier tournament matchups separately from real archived first-pick evidence. A promising historical result does not prove a stronger prediction for this game.</p>
              {onOpenModels&&<button type="button" onClick={onOpenModels}>COMPARE HISTORICAL MODEL EVIDENCE ↗</button>}
            </details>
            <div className="gc-explain-head"><span className="section-kicker">02 / WHY THE MODEL THINKS THIS</span><h3>Explain the <em>percentage.</em></h3>
              <p>The same team ratings are built from results against other opponents. Factors below are evidence, not four separate probability coefficients.</p></div>
            <div className="gc-factors">{(selected.factors||[]).map(f=><div key={f.title}><small>{f.title}</small>
              <strong>{plus(f.value)}</strong><p>{f.detail}</p></div>)}</div>
            <ScoreProjection home={ratings?.teams.find(t=>t.teamId===selected.homeTeamId)}
              away={ratings?.teams.find(t=>t.teamId===selected.awayTeamId)}
              neutralSite={selected.neutralSite} winProbability={selected.homeWinProbability}/>
            <MatchupIntelligence home={ratings?.teams.find(t=>t.teamId===selected.homeTeamId)}
              away={ratings?.teams.find(t=>t.teamId===selected.awayTeamId)}/>
            <div className="gc-profiles"><ProfilePanel profile={selected.awayProfile} side="AWAY"/><ProfilePanel profile={selected.homeProfile} side="HOME"/></div>
            <div className="gc-evidence"><div><span className="section-kicker">03 / THE OTHER GAMES</span><h3>Shared opponents.</h3>
                <p>When both teams previously played the same opponent, compare their actual margins. These games also contribute to Elo through each program's sequence of results.</p>
                {(selected.commonOpponents||[]).length?<div className="gc-common-list">{selected.commonOpponents!.map(x=><div key={x.opponent}>
                  <strong>{x.opponent}</strong><span>{selected.home}: {x.homeMargin>0?"+":""}{x.homeMargin} ({x.homeResultDate})</span>
                  <span>{selected.away}: {x.awayMargin>0?"+":""}{x.awayMargin} ({x.awayResultDate})</span>
                </div>)}</div>:<p className="gc-empty">No shared, earlier-date opponents in the currently published scores.</p>}</div>
              <div><span className="section-kicker">04 / PREVIOUS MEETINGS</span><h3>Head to head.</h3>
                {(selected.headToHead||[]).length?<div className="gc-common-list">{selected.headToHead!.map(x=><div key={x.date+x.home}>
                  <strong>{x.date}</strong><span>{x.away} {x.awayScore} · {x.home} {x.homeScore}</span></div>)}</div>:
                  <p className="gc-empty">No earlier season matchup appears in the accepted results.</p>}
                <div className="gc-research"><small>RESEARCH COMPARISONS · NOT ACTIVE PICKS</small>
                  <p>Prepublished Elo: <strong>{percent(selected.baselineHomeWinProbability!)}</strong> home</p>
                  {selected.challengerHomeWinProbability!=null?<p>Shadow-trained logistic: <strong>{percent(selected.challengerHomeWinProbability)}</strong> home</p>:null}
                  {selected.stateSpaceHomeWinProbability!=null?<p>Causal state space: <strong>{percent(selected.stateSpaceHomeWinProbability)}</strong> home</p>:null}
                  {selected.opponentAdjustedHomeWinProbability!=null?<p>Opponent-aware candidate: <strong>{percent(selected.opponentAdjustedHomeWinProbability)}</strong> home</p>:null}
                  {selected.adaptiveStateSpaceHomeWinProbability!=null?<p>Adaptive state-space candidate: <strong>{percent(selected.adaptiveStateSpaceHomeWinProbability)}</strong> home</p>:null}
                  {selected.driftWatch&&<p>Innovation drift watch: <strong>{selected.driftWatch.home?"home team ":""}{selected.driftWatch.away?"away team":""}{!selected.driftWatch.home&&!selected.driftWatch.away?"no persistent alert":""}</strong></p>}
                  <small>The headline percentage uses only the model actually selected for publication.</small>
                </div>
              </div></div>
            <GameAudit eventId={selected.eventId} snapshots={ledger?.snapshots||[]} settlements={ledger?.settlements||[]}/>
          </>:selected?<div className="gc-unmatched"><span className="section-kicker">NO VERIFIED ODDS</span><h3>{selected.away} at {selected.home}</h3><p>{selected.reason}</p>
            <p>We show this scheduled fixture but do not invent a NCAA-to-ESPN team join or falsely label a guess as a prediction.</p></div>:
          archivedGame?<div className="gc-postgame-view">
             <div className="gc-detail-cap"><span>VERIFIED ARCHIVED RESULT / ESPN {archivedGame.eventId}</span><span>{archivedGame.actualResultDate}</span></div>
             <button type="button" className="gc-back" onClick={()=>setSelectedId(rows[0]?.eventId||"")}>← BACK TO UPCOMING GAMES</button>
             <GameAudit eventId={archivedGame.eventId} snapshots={ledger?.snapshots||[]} settlements={ledger?.settlements||[]} closed/>
          </div>:
          <div className="gc-unmatched"><span className="section-kicker">SOURCE HAS NO CURRENT GAME</span><h3>More games incoming.</h3>
            <p>No future, confidently source-matched fixture is currently available. Try the hypothetical neutral matchup lab below; it does not represent a scheduled game.</p></div>}
        </article>
      </div>
      {settledGames.length>0&&<section className="gc-recent-settled" aria-label="Recently settled source-backed pregame predictions">
        <div><span className="section-kicker">ARCHIVED RESULTS / VERIFIED PRETIPOFF PICKS</span>
          <h3>From prediction <em>to final.</em></h3>
          <p>Open a completed game to see the original frozen percentage, verified final score, and prediction's correctness.</p></div>
        <div className="gc-settled-grid">{settledGames.slice(0,8).map(x=><button type="button" key={x.eventId}
          className={selectedId===x.eventId?"active":""} onClick={()=>choose(x.eventId)}>
          <small>{x.actualResultDate} · {x.espnFinalVerified?"FINAL VERIFIED":"ARCHIVED SOURCE RESULT"}</small>
          <strong>{x.away} {x.awayScore} · {x.home} {x.homeScore}</strong>
          <span>{x.winnerCorrect===1?"CORRECT":x.winnerCorrect===0?"MISSED":"EVEN ODDS"} · {percent(x.predictedHome)} home win forecast</span>
        </button>)}</div>
      </section>}
      <div className="gc-whatif"><div><span className="section-kicker">05 / COMPARE ANY PROGRAMS</span><h2>Matchup <span>sandbox.</span></h2>
        <p>Pick any two current teams for an explicitly hypothetical neutral-site comparison. This is not a scheduled game and is never logged as a pregame forecast.</p></div>
        <div className="gc-whatif-controls"><label>TEAM A<select aria-label="Hypothetical team A" value={a} onChange={e=>setA(e.target.value)}>
          {(ratings?.teams||[]).map(t=><option key={t.teamId} value={t.teamId}>{t.name}</option>)}</select></label>
          <label>TEAM B<select aria-label="Hypothetical team B" value={b} onChange={e=>setB(e.target.value)}>
          {(ratings?.teams||[]).map(t=><option key={t.teamId} value={t.teamId}>{t.name}</option>)}</select></label>
          <div><small>NEUTRAL-COURT ELO SCENARIO</small><strong>{demo!=null?percent(demo):"Choose distinct teams"}</strong><span>{left?.name||"Team A"} win chance</span></div></div>
      </div>
      <p className="source-note" id="gc-accuracy-notes">Fixture dates/status: ESPN public schedule; verified current team ratings and prior scores: NCAA-derived SportsDataverse data. Published probabilities are computed from information available at source retrieval, not from future results. Site content updates on GitHub Actions' scheduled refreshes; this is not an instantaneous live odds service. Forward accuracy uses each event's earliest archived before-tipoff forecast and becomes meaningful only when real settled events exist. A miss is recorded and used in later chronological retraining rather than changing a probability after the outcome.</p>
    </>}
  </section>;
}
function formatTime(iso:string){return "CAPTURED "+new Date(iso).toLocaleString("en-US",{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"America/New_York"})+" ET";}

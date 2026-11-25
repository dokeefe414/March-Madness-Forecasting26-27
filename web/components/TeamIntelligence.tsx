"use client";
import {useEffect,useMemo,useState} from "react";
import type {RatingsDataset,Team} from "../lib/models";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Elo3Components={rawElo:number;reliableElo:number;prior:number;reliability:number;sos:number;form:number;efficiency:number;fourFactors:number;power:number;games:number;boxGames:number;fourFactorGames:number};
type Elo3Team={teamId:string;rating:number;rank:number;boxGames:number;components?:Elo3Components};
type Game={id:string;date:string;home:string;away:string;homeScore:number;awayScore:number};
type Fixture={eventId:string;homeTeamId?:string;awayTeamId?:string;home:string;away:string;scheduledStartUtc:string;homeWinProbability:number|null};
const pct=(n:number)=>(n*100).toFixed(1)+"%";
function Trend({values}:{values:number[]}){
 if(values.length<2)return <p className="v12-subtle">More recorded games are needed to show a rating trend.</p>;
 const min=Math.min(...values)-5,max=Math.max(...values)+5,scale=Math.max(1,max-min);
 const path=values.map((n,i)=>(i?"L":"M")+` ${(i/(values.length-1)*500).toFixed(1)} ${(105-90*(n-min)/scale).toFixed(1)}`).join(" ");
 return <svg className="v12-curve" role="img" aria-label="Elo rating trajectory from earlier source games" viewBox="0 0 500 120" preserveAspectRatio="none"><path d={path} stroke="#a8ffd0" strokeWidth="3" fill="none" strokeLinejoin="round" strokeLinecap="round"/></svg>;
}
export default function TeamIntelligence(){
 const [data,setData]=useState<RatingsDataset|null>(null);
 const [elo3,setElo3]=useState<{retrievedAtUtc:string;teams:Array<Elo3Team>;pairedBoxes:number;limitations:string[]}|null>(null);
 const [games,setGames]=useState<Game[]>([]);
 const [fixtures,setFixtures]=useState<Fixture[]>([]);
 const [error,setError]=useState("");
 const [search,setSearch]=useState("");
 const [selected,setSelected]=useState("");
 const [copied,setCopied]=useState(false);
 useEffect(()=>{let alive=true;Promise.all([
   fetch(base+"/current/2027.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Current ratings unavailable");return r.json()}),
   fetch(base+"/current/2027-games.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Current games unavailable");return r.json()}),
   fetch(base+"/current/upcoming.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Schedule unavailable");return r.json()}),
   fetch(base+"/current/elo-v3-teams.json",{cache:"no-store"}).then(r=>r.ok?r.json():null).catch(()=>null)
 ]).then(([r,g,f,v3])=>{if(!alive)return;
    if(r.season!==2027||r.mode!=="current"||!Array.isArray(r.teams)||!Array.isArray(g.games)||!Array.isArray(f.games))throw Error("Source contracts mismatched");
    const valid=v3&&v3.season===2027&&v3.model==="elo3"&&v3.retrievedAtUtc===r.retrievedAtUtc&&Array.isArray(v3.teams)
      &&v3.teams.length===r.teams.length
      &&new Set(v3.teams.map((t:{teamId:string})=>t.teamId)).size===r.teams.length
      &&r.teams.every((t:Team)=>v3.teams.some((v:{teamId:string})=>v.teamId===t.teamId));
    setData(r);setGames(g.games);setFixtures(f.games);setElo3(valid?v3:null);
    setError(valid?"":"Elo 3.0 data is temporarily out of sync. Showing verified previous-model rankings until the sources match.");
    const requested=new URLSearchParams(window.location.search).get("team");
    setSelected(r.teams.some((t:Team)=>t.teamId===requested)?requested:r.teams[0]?.teamId||"");
 }).catch(e=>{if(alive)setError(String(e.message||e))});return()=>{alive=false}},[]);
 const teams=useMemo(()=>{const index=new Map((elo3?.teams||[]).map(t=>[t.teamId,t]));return [...(data?.teams||[])].map(t=>({...t,rating:index.get(t.teamId)?.rating??t.rating,rank:index.get(t.teamId)?.rank??t.rank})).sort((a,b)=>a.rank-b.rank)},[data,elo3]);
 const team=teams.find(t=>t.teamId===selected);
 const elo3Detail=elo3?.teams.find(t=>t.teamId===selected)?.components;
 const relevant=useMemo(()=>team?games.filter(g=>g.home===team.name||g.away===team.name).slice(-10).reverse():[],[team,games]);
 const upcoming=useMemo(()=>fixtures.filter(f=>f.homeTeamId===selected||f.awayTeamId===selected)
  .filter(f=>Date.parse(f.scheduledStartUtc)>Date.now()).sort((a,b)=>a.scheduledStartUtc.localeCompare(b.scheduledStartUtc)).slice(0,8),[fixtures,selected]);
 const compare=useMemo(()=>teams.filter(t=>t.teamId!==selected).sort((a,b)=>team?Math.abs(a.rating-team.rating)-Math.abs(b.rating-team.rating):0).slice(0,3),[teams,selected,team]);
 function pick(id:string){setSelected(id);setCopied(false);const url=new URL(window.location.href);url.searchParams.set("view","teams");url.searchParams.set("team",id);window.history.replaceState(null,"",url.toString())}
 async function share(){if(!team)return;const url=new URL(window.location.href);url.searchParams.set("view","teams");url.searchParams.set("team",team.teamId);
  try{await navigator.clipboard.writeText(url.toString());setCopied(true)}catch{setCopied(false)}}
 return <section className="content-section v12-team" aria-label="Current team intelligence center">
   <div className="v12-head"><span className="section-kicker">2026–27 / ELO 3.0 RESEARCH POWER RANKINGS</span><h1>TEAM <em>INTELLIGENCE.</em></h1>
     <p>Elo 3.0 power rankings from accepted 2027 scores, with source-verified efficiency where available. Previous-season priors are neutral until team IDs are independently verified. Historical game-change charts below still describe the original Elo.</p></div>
   {data&&error&&<p className="premium-empty" role="status">{error}</p>}
   {!data?<p className="premium-empty" role={error?"alert":"status"}>{error||"Loading sourced team data…"}</p>:
   <div className="v12-team-layout">
    <aside className="v12-team-list"><label>FIND A PROGRAM<input aria-label="Search teams" placeholder="Search school..." value={search} onChange={e=>setSearch(e.target.value)}/></label>
     <div className="v12-team-scroll">{teams.filter(t=>t.name.toLowerCase().includes(search.toLowerCase())).map(t=><button key={t.teamId} className={selected===t.teamId?"selected":""} onClick={()=>pick(t.teamId)} aria-pressed={selected===t.teamId}><strong>{t.name}</strong><span>#{t.rank} · {t.wins}–{t.losses} · {t.rating.toFixed(0)} {elo3?"Elo 3.0":"Elo"}</span></button>)}</div>
    </aside>
    {team&&<article className="v12-team-detail">
     <div className="v12-team-title"><div><span className="feature-kicker">{team.conferenceVerified?team.conference:"CONFERENCE NOT VERIFIED"}</span><h2>{team.name}</h2><p>As of {data.retrievedAtUtc?new Date(data.retrievedAtUtc).toLocaleString("en-US",{timeZone:"America/New_York"}):"latest verified capture"} ET</p></div><button onClick={share}>{copied?"LINK COPIED ✓":"COPY TEAM LINK ↗"}</button></div>
     <div className="v12-stats">{[
       ["RECORD",team.wins+"–"+team.losses],
       [elo3?"ELO 3.0 POWER":"ORIGINAL ELO (FALLBACK)",team.rating.toFixed(0)],
       ["FORM / TREND",(team.trend>=0?"+":"")+team.trend.toFixed(1)],
       ["AVG OPPONENT ELO AT GAME",team.opponentAverageEloAtGame?.toFixed(0)||team.opponentAverageElo?.toFixed(0)||"—"],
       ["LAST GAME ELO Δ",team.eloLastGameChange==null?"—":(team.eloLastGameChange>=0?"+":"")+team.eloLastGameChange.toFixed(1)]
     ].map(([k,v])=><div key={k}><small>{k}</small><strong>{v}</strong></div>)}</div>
     {elo3Detail&&<div className="v12-card" aria-label="Elo 3.0 rating factor breakdown"><h3>WHY THIS TEAM IS RANKED HERE / ELO 3.0</h3>
       <p className="v12-subtle">The power rating combines reliability-adjusted current Elo, previous-opponent strength, recent form and verified box statistics. The original Elo trajectory below is separate.</p>
       <div className="v12-stats">{[
         ["RELIABILITY-ADJUSTED ELO",elo3Detail.reliableElo.toFixed(1)],
         ["SCHEDULE ADJUSTMENT",(elo3Detail.sos>=0?"+":"")+elo3Detail.sos.toFixed(1)],
         ["RECENT FORM",(elo3Detail.form>=0?"+":"")+elo3Detail.form.toFixed(1)],
         ["VERIFIED EFFICIENCY",(elo3Detail.efficiency>=0?"+":"")+elo3Detail.efficiency.toFixed(1)],
         ["VERIFIED FOUR FACTORS",(elo3Detail.fourFactors>=0?"+":"")+elo3Detail.fourFactors.toFixed(1)],
         ["GAME EVIDENCE",elo3Detail.games+" games / "+elo3Detail.boxGames+" paired boxes"]
       ].map(([k,v])=><div key={k}><small>{k}</small><strong>{v}</strong></div>)}</div>
       <p className="v12-subtle">Confidence weight: {(100*elo3Detail.reliability).toFixed(1)}%. Neutral 1500 preseason prior pending verified 2026→2027 team identity. Missing box stats contribute zero rather than an invented value.</p>
     </div>}
     <div className="v12-card"><h3>ORIGINAL ELO GAME-BY-GAME HISTORY</h3>
       <p className="v12-subtle">Every accepted score changes both teams' ratings. Updates use the opponent's rating before that game, designated home advantage and a capped score-margin multiplier. The classic Elo control is {team.classicElo?.toFixed(1)??"unavailable"}; the Elo 3.0 rating above is {team.rating.toFixed(1)}. Neither is an official NCAA ranking.</p>
       {(team.eloRecentChanges||[]).map(r=><div className="v12-result" key={r.contestId||r.date+r.opponent}><span>{r.date} · {r.result} vs {r.opponent} · {r.margin>0?"+":""}{r.margin} pts · Opp. pregame Elo {r.opponentEloBefore.toFixed(0)}</span><b>{r.eloChange>=0?"+":""}{r.eloChange.toFixed(2)} Elo</b></div>)}
       {!team.eloRecentChanges?.length&&<p className="v12-subtle">No rating updates have been sourced for this program.</p>}
       <p className="v12-subtle">Game-score source can be delayed and lacks authoritative neutral-site and injury details; ratings rebuild on scheduled publication, not instantly after the buzzer.</p>
     </div>
     <div className="v12-card"><h3>ORIGINAL ELO TRAJECTORY (REFERENCE)</h3><Trend values={team.history||[]}/><p className="v12-subtle">Recorded games drive this source-backed rating curve. Each calendar date is evaluated before that day's scores are used to update Elo; published historical forecasts remain unchanged.</p></div>
     <div className="v12-stats">{[
       ["ADJUSTED OFFENSE",team.adjOff100?.toFixed(1)??"—"],
       ["ADJUSTED DEFENSE",team.adjDef100?.toFixed(1)??"—"],
       ["ADJUSTED NET",team.adjNet100?.toFixed(1)??"—"],
       ["PACE",team.pacePossessions?.toFixed(1)??"—"]
     ].map(([k,v])=><div key={k}><small>{k}</small><strong>{v}</strong></div>)}</div>
     <p className="v12-subtle">Efficiency and pace appear only when source-linked possession data exists. Lower adjusted defensive points allowed is better.</p>
     <div className="v12-split"><div className="v12-card"><h3>RECENT VERIFIED RESULTS</h3>{relevant.map(g=>{const home=g.home===team.name;const scored=home?g.homeScore:g.awayScore;const against=home?g.awayScore:g.homeScore;return <div className="v12-result" key={g.id}><span>{g.date} · {home?"vs":"at"} {home?g.away:g.home}</span><b>{scored>against?"W":"L"} {scored}–{against}</b></div>})}{!relevant.length&&<p className="v12-subtle">No settled source results.</p>}</div>
     <div className="v12-card"><h3>UPCOMING SOURCE FIXTURES</h3>{upcoming.map(g=><div className="v12-result" key={g.eventId}><span>{new Date(g.scheduledStartUtc).toLocaleDateString("en-US",{timeZone:"America/New_York"})} · {g.away} at {g.home}</span><b>{g.homeWinProbability==null?"No verified odds":pct(g.homeTeamId===team.teamId?g.homeWinProbability:1-g.homeWinProbability)+" win"}</b></div>)}{!upcoming.length&&<p className="v12-subtle">No future source-matched fixtures currently published.</p>}</div></div>
     <div className="v12-card"><h3>SIMILAR ELO TEAMS</h3>{compare.map(t=><button className="v12-peer" key={t.teamId} onClick={()=>pick(t.teamId)}>{t.name} · {t.rating.toFixed(0)} Elo ↗</button>)}</div>
    </article>}
   </div>}
  </section>;
}
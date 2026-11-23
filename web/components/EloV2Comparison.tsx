"use client";

import {useEffect,useMemo,useState} from "react";

const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Scores={games:number;baselineBrier:number|null;challengerBrier:number|null;
  brierGain:number|null;baselineAccuracy:number|null;challengerAccuracy:number|null;
  baselineLogLoss?:number|null;challengerLogLoss?:number|null};
type Variant=Scores&{earlySeason?:Scores;seasonBlockBrierGain95?:number[]|null;
  positiveGainSeasons?:number};
type Year={season:number;games:number;priorSeason:number;priorMatchedTeams:number;
  variants:Record<string,Scores>};
type Historical={schemaVersion:number;type:string;status:string;
  holdoutSeasons:number;sourceCommit?:string;sourceSha256?:string;
  firstHeldOutYear?:number;lastHeldOutYear?:number;
  fixedHyperparameters?:Record<string,number|boolean>;variants:Record<string,Variant>;
  bySeason:Year[];reason?:string};
type Team={name:string;teamId:string;espnTeamId:string;elo2:number;elo2Rank:number;
  baselineElo:number;baselineRank:number;rankChangeFromBaseline:number;
  offseasonPrior:number;hasHistoricalMatch:boolean;
  opponentScheduleBonus:number;games:number};
type ApTeam={apRank:number;apTeam:string;baselineEloRankFrozen:number|null;
  elo2Rank:number|null;elo2:number|null;rankGap:number|null};
type Ap={pollKey:string;sourceWeekStart:string;eloGameCutoffDate:string;
  status:string;apMatchedElo2:number;baselineTop25OverlapFrozen:number|null;
  elo2Top25Overlap:number|null;baselineTop10OverlapFrozen:number|null;
  elo2Top10Overlap:number|null;teams:ApTeam[];warning:string};
type Current={schemaVersion:number;type:string;season:number;status:string;
  ratingRetrievedAtUtc:string;sourceGameDate:string;sourceGames:number;
  modelPromotionAllowed:boolean;historicalBenchmarkStatus:string;
  historicalHoldoutSeasons:number;
  priorCoverage:{matchedTeamNames:number;unmatchedTeamNames:number;
    snapshotSeason:number;snapshotThroughKaggleDay:number;identityWarning:string};
  currentRetrospective:Record<string,Scores>;
  teams:Team[];apComparisons:Ap[];promotionReason:string};
type Ratings={retrievedAtUtc:string};
const fmt=(v:number|null|undefined,d=4)=>v==null?"—":v.toFixed(d);
const percentage=(v:number|null|undefined)=>v==null?"—":(v*100).toFixed(1)+"%";
const tag=(v:string)=>new Date(v+"T12:00:00Z").toLocaleDateString("en-US",{
  month:"short",day:"numeric",year:"numeric",timeZone:"UTC"});
const names:Record<string,string>={
  carryover:"Historical carryover",
  scheduleOnly:"Schedule-adjusted",
  carryoverAndSchedule:"Combined Elo 2.0",
};
function ComparisonBars({baseline,challenger,label}:{baseline:number|null|undefined;
  challenger:number|null|undefined;label?:string}){
  if(baseline==null||challenger==null)return <p className="ev2-muted">Source-matched metrics unavailable.</p>;
  const max=Math.max(.01,baseline,challenger)*1.08;
  return <div className="ev2-bar-comparison" role="img" aria-label={(label||"Brier score")+
    ": original Elo "+fmt(baseline)+" versus challenger "+fmt(challenger)}>
    <div><span>ORIGINAL ELO</span><i><b style={{width:(baseline/max*100)+"%"}}/></i><strong>{fmt(baseline)}</strong></div>
    <div><span>ELO 2.0</span><i><b style={{width:(challenger/max*100)+"%"}}/></i><strong>{fmt(challenger)}</strong></div>
  </div>;
}
const fallback="Elo 2.0 is research only. Historical backtests and AP agreement do not justify replacing any published first-pick probability.";

export default function EloV2Comparison(){
  const [hist,setHist]=useState<Historical|null>(null);
  const [current,setCurrent]=useState<Current|null>(null);
  const [integrity,setIntegrity]=useState<"loading"|"ready"|"unavailable"|"stale">("loading");
  const [mode,setMode]=useState<"rankings"|"historical"|"ap">("rankings");
  const [variant,setVariant]=useState("carryoverAndSchedule");
  const [rankFilter,setRankFilter]=useState<"top25"|"movers"|"all">("top25");
  const [weekKey,setWeekKey]=useState("");
  const [revision,setRevision]=useState(0);

  useEffect(()=>{
    const timer=window.setInterval(()=>setRevision(n=>n+1),10*60_000);
    const visible=()=>{if(document.visibilityState==="visible")setRevision(n=>n+1)};
    document.addEventListener("visibilitychange",visible);
    return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",visible)};
  },[]);
  useEffect(()=>{
    let live=true;
    const get=async (p:string)=>{
      const response=await fetch(base+p,{cache:"no-store"});
      if(!response.ok)throw Error("Missing source-aligned Elo2 report");
      return response.json();
    };
    Promise.all([
      get("/research/elo-v2-historical.json") as Promise<Historical>,
      get("/current/elo-v2-research.json") as Promise<Current>,
      get("/current/2027.json") as Promise<Ratings>,
    ]).then(([historical,report,ratings])=>{
      if(!live)return;
      if(historical.schemaVersion!==1||historical.type!=="elo-v2-historical-year-holdout"||
         report.schemaVersion!==1||report.type!=="current-elo2-research"||
         report.season!==2027||!Array.isArray(report.teams)||
         !Array.isArray(report.apComparisons)){
        setIntegrity("unavailable");return;
      }
      setHist(historical);setCurrent(report);
      setIntegrity(report.ratingRetrievedAtUtc===ratings.retrievedAtUtc?"ready":"stale");
    }).catch(()=>{if(live)setIntegrity("unavailable")});
    return()=>{live=false};
  },[revision]);

  const rankings=useMemo(()=>{
    const all=current?.teams||[];
    if(rankFilter==="top25")return all.slice(0,25);
    if(rankFilter==="movers")return [...all].sort((a,b)=>
      Math.abs(b.rankChangeFromBaseline)-Math.abs(a.rankChangeFromBaseline)).slice(0,30);
    return all.slice(0,75);
  },[current,rankFilter]);
  const apWeeks=[...(current?.apComparisons||[])].reverse();
  const ap=apWeeks.find(w=>w.pollKey===weekKey)||apWeeks[0];
  const historical=hist?.variants[variant];
  const summary=hist?.variants["carryoverAndSchedule"];

  return <section className="ev2" id="elo-v2-comparison" aria-label="Original Elo versus Elo 2.0 research comparison">
    <div className="ev2-head">
      <div className="ev2-eyebrow"><span className="ev2-pulse"/> RESEARCH SERIES 02 / SOURCE-FROZEN EXPERIMENT</div>
      <div className="ev2-title-row">
        <div><h2>ELO <em>REIMAGINED.</em></h2>
          <p>Last season's strength. Who you actually played. One difficult question: does a smarter starting point beat the original Elo on <strong>games it never saw?</strong></p>
        </div>
        <div className="ev2-stamp"><small>ACTIVE PREDICTOR</small><strong>UNCHANGED</strong>
          <span>Challenger and AP comparison only</span></div>
      </div>
    </div>
    {integrity==="loading"?<p className="ev2-empty" role="status">Reading source-aligned Elo 2.0 research…</p>:
     integrity==="unavailable"?<p className="ev2-empty" role="alert">Elo 2.0 research data isn't available. The operating Elo forecasts are unchanged, and no performance numbers are invented.</p>:
     integrity==="stale"?<p className="ev2-empty" role="alert">Elo 2.0 research and the live Elo source are from different retrieval timestamps. Comparisons are withheld until the next verified rebuild.</p>:
     <>
       <div className="ev2-stat-strip">
         <div><small>HISTORICAL HELD-OUT GAMES</small><strong>{summary?.games?.toLocaleString()??"—"}</strong><span>{hist?.holdoutSeasons??0} independent held-out seasons</span></div>
         <div><small>COMBINED BRIER GAIN</small><strong className={(summary?.brierGain??0)>0?"ev2-positive":""}>{summary?.brierGain==null?"—":(summary.brierGain>0?"+":"")+fmt(summary.brierGain)}</strong><span>Positive = challenger better ↓</span></div>
         <div><small>FIRST 45 DAYS / BRIER GAIN</small><strong className={(summary?.earlySeason?.brierGain??0)>0?"ev2-positive":""}>{summary?.earlySeason?.brierGain==null?"—":(summary.earlySeason.brierGain>0?"+":"")+fmt(summary.earlySeason.brierGain)}</strong><span>Early-season prediction test</span></div>
         <div><small>2027 EXACT-NAME PRIOR LINKS</small><strong>{current?.priorCoverage.matchedTeamNames??"—"}</strong><span>Research only: historical 2026 data incomplete</span></div>
       </div>
       <div className="ev2-method-strip">
         <div><b>01 / CARRYOVER</b><span>55% retained prior strength, capped ±160 Elo</span></div>
         <div><b>02 / SCHEDULE</b><span>Prior opponents only, shrunken and capped ±35</span></div>
         <div><b>03 / SAME GAMES</b><span>Same pre-date fixtures and exact winner outcomes</span></div>
       </div>
       <div className="ev2-switch" role="group" aria-label="Choose Elo comparison view">
         <button type="button" onClick={()=>setMode("rankings")} aria-pressed={mode==="rankings"}>CURRENT RANKINGS</button>
         <button type="button" onClick={()=>setMode("historical")} aria-pressed={mode==="historical"}>HISTORICAL TESTS</button>
         <button type="button" onClick={()=>setMode("ap")} aria-pressed={mode==="ap"}>ELO 2.0 vs AP</button>
       </div>
       {mode==="rankings"&&<div className="ev2-content">
         <div className="ev2-section-top"><div><small>2026–27 / SOURCE-AUDITED TEAM COHORT</small>
           <h3>Two Elo lenses. <em>One season.</em></h3>
           <p>Compare the current source-aware Elo with provisional carryover-plus-schedule Elo. Rank positions are computed on the same verified Division I cohort.</p></div>
           <div className="ev2-filter" role="group" aria-label="Filter Elo team rankings">
             {(["top25","movers","all"] as const).map(v=><button key={v} type="button" aria-pressed={rankFilter===v} onClick={()=>setRankFilter(v)}>{v==="top25"?"Top 25":v==="movers"?"Biggest movers":"Top 75"}</button>)}
           </div>
         </div>
         <div className="ev2-table-scroll"><table className="ev2-table">
           <thead><tr><th>ELO2 #</th><th>PROGRAM</th><th>ORIGINAL #</th><th>ORIGINAL</th><th>ELO 2.0</th><th>PRIOR</th><th>RANK Δ</th></tr></thead>
           <tbody>{rankings.map(t=><tr key={t.espnTeamId}>
             <td><strong className="ev2-index">{t.elo2Rank}</strong></td>
             <td><b>{t.name}</b><small>{t.games} games · {t.hasHistoricalMatch?"Exact-name prior":"Neutral 1500 prior"}</small></td>
             <td>#{t.baselineRank}</td><td>{fmt(t.baselineElo,1)}</td>
             <td className="ev2-accent">{fmt(t.elo2,1)}</td>
             <td>{fmt(t.offseasonPrior,1)}</td>
             <td className={t.rankChangeFromBaseline>0?"ev2-positive":""}>{t.rankChangeFromBaseline>0?"+":""}{t.rankChangeFromBaseline}</td>
           </tr>)}</tbody>
         </table></div>
         <p className="ev2-footnote">A positive rank change means Elo 2.0 ranks that team higher than original Elo. The previous-season 2026 archive ends at Kaggle day 118, not the full season; exact school-name matches are provisional, so these rankings cannot become live predictions without stronger identity verification.</p>
       </div>}
       {mode==="historical"&&<div className="ev2-content">
         <div className="ev2-section-top"><div><small>PINNED KAGGLE COMPACT SCORES / NEVER FUTURE-GAME DATA</small>
           <h3>Prove it <em>on old seasons.</em></h3>
           <p>Fixed policy, same date-frozen games, genuine previous-season priors. Lower Brier is better; more complicated models are not assumed superior.</p></div>
           <label className="ev2-select">CHALLENGER VARIANT
             <select value={variant} aria-label="Choose Elo 2.0 historical variant" onChange={e=>setVariant(e.target.value)}>
               {Object.entries(names).map(([id,v])=><option value={id} key={id}>{v}</option>)}
             </select>
           </label>
         </div>
         {hist?.status!=="ready"?<p className="ev2-empty">Historical source unavailable or incomplete: {hist?.reason||"No comparable pinned seasons yet"}. No improvement claim is made.</p>:
          <>
           <div className="ev2-hist-grid">
             <div className="ev2-hist-feature">
               <small>FULL HELD-OUT REGULAR SEASONS</small><h4>{names[variant]}</h4>
               <ComparisonBars baseline={historical?.baselineBrier} challenger={historical?.challengerBrier} label="Full-season Brier"/>
               <div className="ev2-evidence"><span><small>WINNER ACCURACY / ORIGINAL</small><strong>{percentage(historical?.baselineAccuracy)}</strong></span>
                 <span><small>WINNER ACCURACY / CHALLENGER</small><strong>{percentage(historical?.challengerAccuracy)}</strong></span></div>
               <p>Season-block descriptive 95% Brier-gain interval: <strong>{historical?.seasonBlockBrierGain95?.map(v=>fmt(v)).join(" to ")||"not enough seasons"}</strong>. If this spans zero, the evidence does not establish improvement.</p>
             </div>
             <div className="ev2-hist-feature">
               <small>EARLY-SEASON / FIRST 45 GAME DAYS</small><h4>The cold-start test.</h4>
               <ComparisonBars baseline={historical?.earlySeason?.baselineBrier}
                 challenger={historical?.earlySeason?.challengerBrier} label="Early-season Brier"/>
               <div className="ev2-evidence"><span><small>EARLY GAMES</small><strong>{historical?.earlySeason?.games?.toLocaleString()??"—"}</strong></span>
                 <span><small>POSITIVE GAIN SEASONS</small><strong>{historical?.positiveGainSeasons??"—"} / {hist?.holdoutSeasons??0}</strong></span></div>
               <p>Parameters are fixed before evaluation, not tuned on these tested seasons. Scores come from the same source games, and the held-out year never supplies its own preseason prior.</p>
             </div>
           </div>
           <div className="ev2-table-scroll"><table className="ev2-table">
             <thead><tr><th>SEASON</th><th>PAIRED GAMES</th><th>ORIGINAL BRIER</th><th>CHALLENGER BRIER</th><th>GAIN ↓</th><th>PRIOR-YEAR TEAMS</th></tr></thead>
             <tbody>{(hist?.bySeason||[]).map(y=><tr key={y.season}>
               <td><b>{y.season}</b></td>
               <td>{y.variants[variant]?.games?.toLocaleString()??"—"}</td>
               <td>{fmt(y.variants[variant]?.baselineBrier)}</td>
               <td className="ev2-accent">{fmt(y.variants[variant]?.challengerBrier)}</td>
               <td className={(y.variants[variant]?.brierGain??0)>0?"ev2-positive":""}>{fmt(y.variants[variant]?.brierGain)}</td>
               <td>{y.priorMatchedTeams}</td>
             </tr>)}</tbody>
           </table></div>
           <p className="ev2-footnote">These are held-out historical regular-season game-date tests, not actual timestamped published 2027 pregame forecasts. Prior seasons only provide initial Elo; prior-date opponent ratings supply schedule adjustments. No AP poll information enters training. Model promotion remains disabled.</p>
          </>}
       </div>}
       {mode==="ap"&&<div className="ev2-content">
         <div className="ev2-section-top"><div><small>INDEPENDENT RANKINGS OPINION BENCHMARK</small>
           <h3>AP vs <em>both Elos.</em></h3>
           <p>Same AP source edition, original Elo's frozen historical comparison and Elo 2.0 reconstructed from games through the preceding Sunday. The two histories have different provenance—see footnote.</p></div>
           <label className="ev2-select">AP POLL WEEK
             <select aria-label="Select Elo 2.0 AP comparison week" value={ap?.pollKey||""} onChange={e=>setWeekKey(e.target.value)}>
               {apWeeks.map(w=><option key={w.pollKey} value={w.pollKey}>{tag(w.sourceWeekStart)}</option>)}
             </select>
           </label>
         </div>
         {!ap?<p className="ev2-empty">No real frozen AP poll editions are available. A weekly ranking comparison cannot be generated without its source poll.</p>:
         <>
           <div className="ev2-ap-metrics">
             <div><small>AP vs ORIGINAL ELO TOP 25</small><strong>{ap.baselineTop25OverlapFrozen??"—"}<em>/25</em></strong><span>Original archived week</span></div>
             <div><small>AP vs ELO 2.0 TOP 25</small><strong>{ap.elo2Top25Overlap??"—"}<em>/25</em></strong><span>Replayed through {tag(ap.eloGameCutoffDate)}</span></div>
             <div><small>ELO 2.0 AP IDENTITIES MATCHED</small><strong>{ap.apMatchedElo2}<em>/25</em></strong><span>{ap.status.replaceAll("-"," ")}</span></div>
           </div>
           <div className="ev2-table-scroll"><table className="ev2-table">
             <thead><tr><th>AP #</th><th>TEAM</th><th>ORIGINAL ELO #</th><th>ELO2 #</th><th>ELO2 STRENGTH</th><th>AP → ELO2 GAP</th></tr></thead>
             <tbody>{ap.teams.map((t,i)=><tr key={i}>
               <td><b>{t.apRank}</b></td><td>{t.apTeam}</td>
               <td>{t.baselineEloRankFrozen==null?"—":"#"+t.baselineEloRankFrozen}</td>
               <td className="ev2-accent">{t.elo2Rank==null?"—":"#"+t.elo2Rank}</td>
               <td>{fmt(t.elo2,1)}</td><td>{t.rankGap==null?"—":(t.rankGap>0?"+":"")+t.rankGap}</td>
             </tr>)}</tbody>
           </table></div>
           <p className="ev2-footnote">{ap.warning} AP voters are not ground-truth winners. Recreating Elo2 today from previously played games cannot prove precisely which scores had been available to the original AP vote. Do not optimize to match the poll or claim a better win predictor from rank agreement.</p>
         </>}
       </div>}
       <div className="ev2-integrity"><strong>MODEL SAFETY GATE / NO AUTOMATIC PROMOTION</strong>
         <p>{current?.promotionReason||fallback}</p>
         <span>SOURCE GAME DATE {current?.sourceGameDate||"unknown"} · {current?.sourceGames?.toLocaleString()||"—"} rated fixture(s) · same-retrieval snapshot</span>
       </div>
     </>}
  </section>;
}

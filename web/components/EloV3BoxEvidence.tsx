"use client";
import {useEffect,useState} from "react";

const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
const families=["scoreOnly","efficiency","fourFactors","extended"] as const;
const incremental=["efficiencyVsScoreOnly","fourFactorsVsEfficiency","extendedVsFourFactors"] as const;
type Increment=typeof incremental[number];
const incrementalLabels:Record<Increment,string>={
  efficiencyVsScoreOnly:"Estimated efficiency vs score-only",
  fourFactorsVsEfficiency:"Four Factors beyond efficiency",
  extendedVsFourFactors:"Other stats beyond Four Factors",
};
type Family=typeof families[number];
type Scores={games:number;brier:number|null;logLoss:number|null;accuracy:number|null;ece:number|null};
type Coverage={matched:number;sourceGames:number;
  possessionSource:string;identity:string;mismatches:Record<string,number>;
  coverageBySeason:Record<string,{sourceGames:number;matchedBoxGames:number;coverage:number|null}>};
type Year={season:number;eligiblePregameGames:number;pairedBoxGames:number;
  coverage:number;variants:Record<Family,Scores>;
  gains:Record<Family,number>};
type Report={schemaVersion:number;type:string;status:string;source:string;
  eligiblePairedGames:number;holdoutSeasons?:number[];
  sourceVerification?:string;boxSourceSha256?:string;
  sourceCoverage?:Coverage;variants?:Record<Family,Scores>;
  brierGainVsScoreOnly?:Record<Family,number|null>;
  incrementalBrierGain?:Record<Increment,number|null>;
  incrementalSeasonBlockGain95?:Partial<Record<Increment,number[]|null>>;
  incrementalPositiveSeasons?:Partial<Record<Increment,number>>;
  seasonBlockGain95?:Partial<Record<Family,number[]|null>>;
  positiveSeasons?:Partial<Record<Family,number>>;
  bySeason?:Year[];reason?:string;limitations?:string[]};
const fmt=(n:number|null|undefined,d=4)=>n==null?"—":n.toFixed(d);
const pct=(n:number|null|undefined)=>n==null?"—":(n*100).toFixed(1)+"%";
const labels:Record<Family,string>={
  scoreOnly:"Score-only Elo 3.0",
  efficiency:"Estimated-possession efficiency",
  fourFactors:"Efficiency + observed Four Factors",
  extended:"All prior box dimensions (experimental)",
};

export default function EloV3BoxEvidence(){
 const [report,setReport]=useState<Report|null>(null);
 const [ready,setReady]=useState(false);
 useEffect(()=>{
   let mounted=true;
   fetch(base+"/research/elo-v3-historical-box.json",{cache:"no-store"})
     .then(r=>r.ok?r.json():null)
     .then(v=>{if(mounted){setReport(v);setReady(true)}})
     .catch(()=>{if(mounted)setReady(true)});
   return()=>{mounted=false};
 },[]);
 const ok=report?.schemaVersion===1&&report.type==="elo3-historical-box-ablation"&&report.status==="ready";
 return <section className="ev2" id="elo3-historical-box-evidence" aria-label="Elo 3 historical box score ablation experiment">
   <div className="ev2-head">
    <div className="ev2-eyebrow">RESEARCH SERIES 04 / PINNED HISTORICAL BOX SCORES</div>
    <div className="ev2-title-row"><div>
     <h2>DO THE STATS <em>HELP?</em></h2>
     <p>Four identically replayed historical models isolate the additional predictive value of observed box-score statistics. Results use only box data from earlier games, never from the game being forecast.</p>
    </div><div className="ev2-stamp"><small>POSSESSIONS</small><strong>ESTIMATED</strong><span>Box counts observed; no play-by-play possession feed</span></div></div>
   </div>
   {!ready?<p className="ev2-empty" role="status">Checking independently pinned historical box source…</p>:
    !ok?<p className="ev2-empty" role="status">
      Historical detailed-box comparison is not yet independently validated: {report?.reason||
       (report?.status==="insufficient-verified-seasons"?
         "Fewer than five held-out seasons met the strict 90% source-match gate.":
         "No verified report published.")} No box-score accuracy gain is claimed.
    </p>:<>
     <div className="ev2-stat-strip">
       <div><small>IDENTICAL ELIGIBLE PREGAME EVENTS</small><strong>{report.eligiblePairedGames.toLocaleString()}</strong><span>{report.holdoutSeasons?.length??0} independent seasons</span></div>
       <div><small>VERIFIED HISTORICAL BOX MATCHES</small><strong>{report.sourceCoverage?.matched.toLocaleString()??"—"}</strong><span>Paired against compact results and final scores</span></div>
       <div><small>BASELINE ELO 3.0 BRIER</small><strong>{fmt(report.variants?.scoreOnly.brier)}</strong><span>Score-only same-game control</span></div>
       <div><small>FOUR FACTORS BRIER GAIN</small><strong>{fmt(report.brierGainVsScoreOnly?.fourFactors)}</strong><span>Positive = observed box stats improved Brier</span></div>
     </div>
     <div className="ev2-content">
       <div className="ev2-section-top"><div><small>FIXED REPLAY FAMILY / DATE-EMBARGOED</small>
         <h3>Incremental <em>evidence.</em></h3>
         <p>All four models receive identical earlier-year priors, outcomes, and prediction timestamps. Comparisons only use matches where both teams had at least three earlier detailed boxes.</p>
       </div></div>
       <div className="ev2-table-scroll"><table className="ev2-table">
        <thead><tr><th>MODEL CONFIGURATION</th><th>GAMES</th><th>BRIER ↓</th><th>LOG LOSS ↓</th><th>ACCURACY ↑</th><th>ECE ↓</th><th>GAIN VS SCORE ONLY</th></tr></thead>
        <tbody>{families.map(k=>{
          const m=report.variants?.[k];
          return <tr key={k}><td>{labels[k]}</td><td>{m?.games.toLocaleString()??"—"}</td>
            <td>{fmt(m?.brier)}</td><td>{fmt(m?.logLoss)}</td>
            <td>{pct(m?.accuracy)}</td><td>{fmt(m?.ece)}</td>
            <td className={(report.brierGainVsScoreOnly?.[k]??0)>0?"ev2-positive":""}>{fmt(report.brierGainVsScoreOnly?.[k])}</td></tr>;
        })}</tbody>
       </table></div>
       <div className="ev2-method-strip">
        {incremental.map(k=><div key={k}>
          <b>{incrementalLabels[k]}</b>
          <span>Incremental Brier gain: {fmt(report.incrementalBrierGain?.[k],6)}</span>
          <span>Season-bootstrap 95%: {report.incrementalSeasonBlockGain95?.[k]?.map(x=>fmt(x,6)).join(" to ")??"Insufficient independent seasons"}</span>
          <span>Positive seasons: {report.incrementalPositiveSeasons?.[k]??"—"} / {report.holdoutSeasons?.length??0}</span>
        </div>)}
       </div>
       <p className="ev2-footnote">Observed: FGM, FGA, 3PM, 3PA, FTM, FTA, offensive and defensive rebounds, turnovers, assists, steals, blocks and fouls. ESTIMATED: game possessions from FGA − ORB + TO + 0.475 × FTA, averaged across the two teams; offensive/defensive points per 100 use that estimate. Observed shooting does not imply observed possessions. No 2027 cross-source prior carryover or live prediction promotion.</p>
     </div>
     <div className="ev2-content"><div className="ev2-section-top"><div>
       <small>YEAR-BLOCK TEST RESULTS</small><h3>Does it <em>generalize?</em></h3>
       <p>Negative year-level improvements reveal where extra statistics hurt. Coverage excludes source-disagreeing or incomplete game boxes.</p>
     </div></div>
      <div className="ev2-table-scroll"><table className="ev2-table">
        <thead><tr><th>SEASON</th><th>ELIGIBLE GAMES</th><th>PAIRED COVERAGE</th><th>SCORE ONLY</th><th>EFFICIENCY</th><th>FOUR FACTORS</th><th>EXTENDED</th></tr></thead>
        <tbody>{(report.bySeason||[]).map(y=><tr key={y.season}>
          <td>{y.season}</td><td>{y.eligiblePregameGames.toLocaleString()}</td><td>{pct(y.coverage)}</td>
          {families.map(k=><td key={k}>{fmt(y.variants[k]?.brier)}</td>)}
        </tr>)}</tbody>
      </table></div>
      <p className="ev2-footnote">Historical source: <a href={report.source} target="_blank" rel="noreferrer">immutable pinned Kaggle detailed-score mirror</a>. Exact game/team/result/venue matches to the separately pinned compact archive, with SHA-256 and Git blob verification. A valid historical replay is not an original pretipoff forecast. Published prediction history is preserved.</p>
     </div>
    </>}
 </section>;
}

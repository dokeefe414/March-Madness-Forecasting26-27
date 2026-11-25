"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Comparison={model:string;pairedGames:number;pairedDays:number;
  eloBrier:number|null;candidateBrier:number|null;
  eloAccuracy:number|null;candidateAccuracy:number|null;
  brierGain:number|null;dateBlockGain95:number[]|null;
  reviewEligible:boolean;autoPromoted:boolean};
type SegmentKey="baselineStrength"|"disagreementSize"|"venue"|"tipoffLead"|"winnerAgreement";
type Segment={segment:string;firstFrozenPicks:number;unverifiedOrPending:number;games:number;gameDates:number;
  baselineBrier:number|null;elo3Brier:number|null;brierGain:number|null;
  baselineAccuracy:number|null;elo3Accuracy:number|null;status:string};
type Preview={eventId:string;home:string;away:string;scheduledStartUtc:string;
  baselineHomeWinProbability:number;elo3HomeWinProbability:number;
  differencePercentagePoints:number;differentWinner:boolean;neutralSite:boolean};
type Diagnostics={schemaVersion:number;type:string;status:string;launchCapturedAtUtc:string|null;
  allCapturedShadowPredictions:number;distinctShadowCapturedEvents:number;
  eligibleOriginalFirstPicks:number;eligibleOriginalFirstDates:number;
  afterLaunchOriginalFirstPicks:number;afterLaunchMissingShadow:number;
  afterLaunchCandidateCoverage:number|null;laterOnlyShadowEventsExcluded:number;
  verifiedPairedFinals:number;pendingOriginalFirstPicks:number;
  pendingByStatus:Record<string,number>;
  difference:{meanPercentagePoints:number|null;medianPercentagePoints:number|null;
    differentWinnerPicks:number;differenceAtLeast10pp:number};
  topUpcomingDisagreements:Preview[];
  segments:Record<SegmentKey,Segment[]>;
  calibration:{games:number;status:string;ece:number|null;bins:Array<{confidenceRange:string;games:number;meanConfidence:number|null;realizedCorrect:number|null}>};
};
const segmentLabels:Record<SegmentKey,string>={
  baselineStrength:"Matchup difficulty / baseline favorite",
  disagreementSize:"How different are the probabilities?",
  venue:"Neutral court vs listed home",
  tipoffLead:"How far ahead was the first pick?",
  winnerAgreement:"Do the models pick the same winner?",
};
type Prospective={status:string;modelVersion:string;firstFrozenPicks:number;
  firstFrozenDates:number;firstCaptureUtc:string|null;lastCaptureUtc:string|null;
  verifiedPairedFinals:number;pendingOriginalFirstPicks:number;
  pairedComparison:Comparison;onlyEarliestFirstPick:boolean;
  retrospectiveBackfill:boolean;activePredictorReplaced:boolean;note:string;diagnostics?:Diagnostics};
type Report={schemaVersion:number;mode:string;prospectiveElo3?:Prospective};
const num=(n:number|null|undefined,d=4)=>n==null?"—":n.toFixed(d);
const pct=(n:number|null|undefined)=>n==null?"—":(100*n).toFixed(1)+"%";
export default function EloV3ProspectiveEvidence(){
 const [report,setReport]=useState<Report|null>(null);
 const [loaded,setLoaded]=useState(false);
 const [segment,setSegment]=useState<SegmentKey>("baselineStrength");
 useEffect(()=>{let alive=true;
   fetch(base+"/current/accuracy-research.json",{cache:"no-store"})
     .then(r=>r.ok?r.json():null).then(x=>{if(alive){setReport(x);setLoaded(true)}})
     .catch(()=>{if(alive)setLoaded(true)});
   return()=>{alive=false};
 },[]);
 const p=report?.schemaVersion===1&&report.mode==="first-pick-forward-research"?
   report.prospectiveElo3:null;
 const c=p?.pairedComparison;
 const d=p?.diagnostics?.schemaVersion===1&&
   p.diagnostics.type==="elo3-original-first-pick-diagnostics"?p.diagnostics:null;
 return <section className="ev2" id="elo3-prospective-evidence" aria-label="Prospective original first-pick Elo 3.0 evidence">
  <div className="ev2-head">
   <div className="ev2-eyebrow">RESEARCH SERIES 05 / IMMUTABLE FIRST PICKS</div>
   <div className="ev2-title-row"><div>
     <h2>CAN ELO 3.0 <em>PROVE IT LIVE?</em></h2>
     <p>From this launch forward, Elo 3.0 is recorded before tipoff beside the existing Elo pick. Only the earliest saved forecast for each event can enter a verified, paired real-game accuracy comparison.</p>
    </div>
    <div className="ev2-stamp"><small>OPERATING FORECAST</small><strong>UNCHANGED</strong><span>Shadow model never auto-promoted</span></div>
   </div>
  </div>
  {!loaded?<p className="ev2-empty" role="status">Reading immutable first-pick verification…</p>:
   !p?<p className="ev2-empty" role="status">Elo 3.0 prospective tracking has not been published in the archived first-pick accuracy report yet. No prospective improvement is claimed.</p>:
   <>
    <div className="ev2-stat-strip">
     <div><small>FIRST-PUBLISHED ELO 3.0 PICKS</small><strong>{p.firstFrozenPicks.toLocaleString()}</strong><span>Across {p.firstFrozenDates} scheduled local dates</span></div>
     <div><small>VERIFIED PAIRED RESULTS</small><strong>{p.verifiedPairedFinals.toLocaleString()}</strong><span>Independent ESPN STATUS_FINAL + matching NCAA score</span></div>
     <div><small>AWAITING VERIFIED FINALS</small><strong>{p.pendingOriginalFirstPicks.toLocaleString()}</strong><span>Pending is never a prediction loss</span></div>
     <div><small>DATE-BLOCK BRIER GAIN</small><strong>{num(c?.brierGain,6)}</strong><span>Positive favors Elo 3.0, negative favors control</span></div>
    </div>
    {p.firstFrozenPicks===0?<p className="ev2-empty" role="status">The recording process has been configured, but no new earliest Elo 3.0 forecasts have been archived yet. Historical results cannot fill this gap.</p>:
    <div className="ev2-content">
      <div className="ev2-section-top"><div><small>EXACT SAME FIRST-FROZEN EVENT IDS</small>
       <h3>Game-day <em>scoreboard.</em></h3>
       <p>These figures remain limited until enough different dates and genuinely verified finals accumulate. Missing candidates and unverified games are excluded, not counted as misses.</p>
      </div></div>
      <div className="ev2-method-strip">
       <div><b>BASELINE BRIER</b><span>{num(c?.eloBrier,6)}</span></div>
       <div><b>FROZEN ELO 3.0 BRIER</b><span>{num(c?.candidateBrier,6)}</span></div>
       <div><b>BASELINE WIN ACCURACY</b><span>{pct(c?.eloAccuracy)}</span></div>
       <div><b>ELO 3.0 WIN ACCURACY</b><span>{pct(c?.candidateAccuracy)}</span></div>
      </div>
      <div className="ev2-method-strip">
       <div><b>INDEPENDENT RESULT DATES</b><span>{c?.pairedDays??0}</span></div>
       <div><b>DATE-BLOCK UNCERTAINTY</b><span>{c?.dateBlockGain95?.map(x=>num(x,6)).join(" to ")||"Not enough paired dates/games"}</span></div>
       <div><b>REVIEW GATE</b><span>{c?.reviewEligible?"Evidence meets conservative review threshold":"Collecting verified paired first picks"}</span></div>
      </div>

      {d&&<div className="ev2-content" aria-label="Original Elo 3 prospective cohort integrity and disagreements">
        <div className="ev2-section-top"><div><small>ORIGINAL FIRST PICK / NOT LATER REVISIONS</small>
          <h3>Where do models <em>disagree?</em></h3>
          <p>Forecast differences are recorded before tipoff. They are not wins or losses. The earliest eligible prediction for each ESPN event is the only one used for accuracy.</p>
        </div></div>
        <div className="ev2-method-strip">
          <div><b>ALL ELO 3.0 RECORDINGS</b><span>{d.allCapturedShadowPredictions.toLocaleString()} saved, including later revisions</span></div>
          <div><b>ELIGIBLE FIRST PICKS</b><span>{d.eligibleOriginalFirstPicks.toLocaleString()} eligible / {d.laterOnlyShadowEventsExcluded} later-only events excluded</span></div>
          <div><b>MEAN PROBABILITY GAP</b><span>{num(d.difference.meanPercentagePoints,2)} percentage points</span></div>
          <div><b>OPPOSITE WINNERS</b><span>{d.difference.differentWinnerPicks} first picks ({d.difference.differenceAtLeast10pp} gaps of at least 10 pp)</span></div>
        </div>
        <p className="ev2-footnote">Since shadow launch: {d.afterLaunchOriginalFirstPicks.toLocaleString()} original first picks observed, {d.afterLaunchMissingShadow.toLocaleString()} missing an Elo 3.0 candidate. Candidate coverage: {d.afterLaunchCandidateCoverage==null?"Not measurable yet":pct(d.afterLaunchCandidateCoverage)}. No previous archived pick has been backfilled.</p>
        {d.topUpcomingDisagreements.length>0?<>
          <div className="ev2-section-top"><div><small>UPCOMING AND UNSCORED / LARGEST FORECAST DIFFERENCES</small>
            <h3>Games to <em>watch.</em></h3>
            <p>Ordered by absolute probability disagreement, not predicted winner quality. Scheduled times are the original ESPN-listed start.</p>
          </div></div>
          <div className="ev2-table-scroll"><table className="ev2-table">
            <thead><tr><th>FIXTURE</th><th>SCHEDULED UTC</th><th>ELO BASELINE HOME WIN</th><th>ELO 3 HOME WIN</th><th>GAP</th><th>WINNER PICK</th></tr></thead>
            <tbody>{d.topUpcomingDisagreements.map(g=><tr key={g.eventId}>
              <td>{g.away} at {g.home}{g.neutralSite?" (neutral)":""}</td>
              <td>{g.scheduledStartUtc.replace("T"," ").replace("Z"," UTC")}</td>
              <td>{pct(g.baselineHomeWinProbability)}</td><td>{pct(g.elo3HomeWinProbability)}</td>
              <td>{num(g.differencePercentagePoints,2)} pp</td>
              <td>{g.differentWinner?"Opposite winners":"Same winner"}</td>
            </tr>)}</tbody>
          </table></div>
        </>:<p className="ev2-footnote">No eligible first-published Elo 3.0 matchups currently have a future scheduled start. Games already underway are never relabeled as upcoming.</p>}
      </div>}
      {d&&<div className="ev2-content" aria-label="Elo3 prospective performance segments">
        <div className="ev2-section-top"><div><small>PREDECLARED SEGMENTS / VERIFIED RESULTS ONLY</small>
          <h3>Where does Elo 3.0 <em>help or hurt?</em></h3>
          <p>Breakdowns share the exact same original first-pick event cohort. Small groups are descriptive, not proof of superiority.</p>
        </div></div>
        <div className="ev2-method-strip"><div><b>PERFORMANCE BREAKDOWN</b>
          <select aria-label="Elo 3.0 evaluation segment" value={segment}
             onChange={e=>setSegment(e.target.value as SegmentKey)}>
             {(Object.keys(segmentLabels) as SegmentKey[]).map(k=><option key={k} value={k}>{segmentLabels[k]}</option>)}
          </select>
        </div><div><b>VERIFIED RESULTS</b><span>{d.verifiedPairedFinals} / {d.eligibleOriginalFirstPicks} original first picks</span></div>
        <div><b>CALIBRATION ECE</b><span>{num(d.calibration.ece,5)} ({d.calibration.status.replaceAll("-"," ")})</span></div></div>
        <div className="ev2-table-scroll"><table className="ev2-table">
          <thead><tr><th>GROUP</th><th>ORIGINAL PICKS</th><th>VERIFIED / DAYS</th><th>BASELINE BRIER ↓</th><th>ELO 3 BRIER ↓</th><th>BRIER GAIN ↑</th><th>EVIDENCE STATUS</th></tr></thead>
          <tbody>{d.segments[segment].map(g=><tr key={g.segment}>
            <td>{g.segment}</td><td>{g.firstFrozenPicks}</td>
            <td>{g.games} / {g.gameDates}</td><td>{num(g.baselineBrier,5)}</td>
            <td>{num(g.elo3Brier,5)}</td><td className={(g.brierGain??0)>0?"ev2-positive":""}>{num(g.brierGain,5)}</td>
            <td>{g.status.replaceAll("-"," ")}</td>
          </tr>)}</tbody>
        </table></div>
        <p className="ev2-footnote">Each segment needs at least 30 independently verified games spanning six result dates before even descriptive review. The overall model promotion gate remains stricter: at least 100 verified paired games across 12 dates, Brier gain of 0.002, and a positive date-block uncertainty bound. It never promotes automatically.</p>
      </div>}
      <p className="ev2-footnote">Elo 3.0 learned from source-matched games and paired boxes strictly before each game date. It has no unverified 2026 school-name priors. First-published picks are never backfilled with later improved forecasts. Even passing the review gate does not promote Elo 3.0 automatically or rewrite the original archive.</p>
    </div>}
   </>}
 </section>;
}

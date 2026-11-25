"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Comparison={model:string;pairedGames:number;pairedDays:number;
  eloBrier:number|null;candidateBrier:number|null;
  eloAccuracy:number|null;candidateAccuracy:number|null;
  brierGain:number|null;dateBlockGain95:number[]|null;
  reviewEligible:boolean;autoPromoted:boolean};
type Prospective={status:string;modelVersion:string;firstFrozenPicks:number;
  firstFrozenDates:number;firstCaptureUtc:string|null;lastCaptureUtc:string|null;
  verifiedPairedFinals:number;pendingOriginalFirstPicks:number;
  pairedComparison:Comparison;onlyEarliestFirstPick:boolean;
  retrospectiveBackfill:boolean;activePredictorReplaced:boolean;note:string};
type Report={schemaVersion:number;mode:string;prospectiveElo3?:Prospective};
const num=(n:number|null|undefined,d=4)=>n==null?"—":n.toFixed(d);
const pct=(n:number|null|undefined)=>n==null?"—":(100*n).toFixed(1)+"%";
export default function EloV3ProspectiveEvidence(){
 const [report,setReport]=useState<Report|null>(null);
 const [loaded,setLoaded]=useState(false);
 useEffect(()=>{let alive=true;
   fetch(base+"/current/accuracy-research.json",{cache:"no-store"})
     .then(r=>r.ok?r.json():null).then(x=>{if(alive){setReport(x);setLoaded(true)}})
     .catch(()=>{if(alive)setLoaded(true)});
   return()=>{alive=false};
 },[]);
 const p=report?.schemaVersion===1&&report.mode==="first-pick-forward-research"?
   report.prospectiveElo3:null;
 const c=p?.pairedComparison;
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
      <p className="ev2-footnote">Elo 3.0 learned from source-matched games and paired boxes strictly before each game date. It has no unverified 2026 school-name priors. First-published picks are never backfilled with later improved forecasts. Even passing the review gate does not promote Elo 3.0 automatically or rewrite the original archive.</p>
    </div>}
   </>}
 </section>;
}

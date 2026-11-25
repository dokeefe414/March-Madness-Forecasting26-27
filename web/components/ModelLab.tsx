"use client";
import {useEffect,useMemo,useState} from "react";
import ModelEvidence from "./ModelEvidence";
import ResearchVisualization from "./ResearchVisualization";
import ScoreResearchEvidence from "./ScoreResearchEvidence";
import EnsembleEvidence from "./EnsembleEvidence";
import HistoricalEvidence from "./HistoricalEvidence";
import ProbabilisticResearch from "./ProbabilisticResearch";
import ModelChampionship from "./ModelChampionship";
import ForecastIntelligence from "./ForecastIntelligence";
import ApPollComparison from "./ApPollComparison";
import EloV2Comparison from "./EloV2Comparison";
import EloV3Evidence from "./EloV3Evidence";
import EloV3BoxEvidence from "./EloV3BoxEvidence";

const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Paired={pairedGames:number;pairedDates:number;baselineEloBrier:number|null;
  candidateBrier:number|null;baselineEloAccuracy:number|null;candidateAccuracy:number|null;
  candidateBrierGain:number|null;dateBlockGain95:number[]|null;claim?:string};
type Forward={settledUniqueGames:number;forecastedUniqueGames:number;
  pairedModelComparisons?:Record<string,Paired>};
type Index={uniqueGames?:Forward};
type Online={mode:"active"|"shadow"|"baseline";trainingGames:number;
  evaluationGames:number;evaluationDays:number;trainedThroughDate:string|null;
  chronologicalGatePassed?:boolean;reason:string;
  forwardValidation?:{pairedGames:number;promote:boolean;minPairedGames:number};
  walkForward?:{eloBrier:number|null;onlineLogisticBrier:number|null;modelBrierGain:number|null}|null};
type Opponent={retrievedAtUtc:string;mode:string;games:number;teamCount:number;
  chronological:{eloBrier:number|null;opponentAdjustedBrier:number|null;
    eloAccuracy:number|null;opponentAdjustedAccuracy:number|null;
    lastSevenDatesEloBrier:number|null;lastSevenDatesOpponentBrier:number|null;
    perDate:Array<{date:string;games:number;eloBrier:number|null;opponentBrier:number|null}>}};
type State={ratingRetrievedAtUtc:string;mode:string;evaluatedGames:number;
  brier:number|null;eloSameDayBrier:number|null;adaptiveBrier:number|null;
  adaptiveAccuracy:number|null;driftWatchTeams:number;
  recentSevenDatesBrier:{elo:number|null;fixedStateSpace:number|null;adaptiveStateSpace:number|null;games:number}};
type Challenger={mode:string;evaluatedGames:number;evaluatedDates:number;ratingRetrievedAtUtc:string;methods:Record<string,{games:number;brier:number|null;accuracy:number|null;logLoss:number|null}>;methodNotes:string[];policy:string};
type Drift={status:string;settledUniqueGames:number;windowGames:number;priorBrier:number|null;recentBrier:number|null;brierDelta:number|null;alert:boolean;reason:string};
type Health={status:string;archivedPredictions:number;lastArchiveUtc:string|null;
  ageHours:number|null;settledUniqueGames:number;message:string;sourceWarnings:string[]};
function brier(v:number|null|undefined){return v==null?"—":v.toFixed(4)}
function pct(v:number|null|undefined){return v==null?"—":(100*v).toFixed(1)+"%"}
const groups=[
 {name:"Online logistic challenger",label:"LEARNED ELO CORRECTION",why:"Learns how current form and team records change win odds, with L2 shrinkage and an independent forward evidence gate."},
 {name:"Opponent-aware research",label:"ADJUSTED FOR WHO THEY FACED",why:"A team's score margin is judged relative to its opponent's PREVIOUS-date Elo, not raw points or a current future rating."},
 {name:"Fixed state-space research",label:"UNCERTAINTY / CONTROL",why:"Latent Gaussian skill from source score margins and fixed process/observation noise; compared against same-date Elo."},
 {name:"Adaptive state-space research",label:"DRIFT-AWARE / EXPERIMENT",why:"Inflates future process variance only after repeated large, same-direction normalized innovations; a single upset alone does not cause a retune."},
];
function ProofBar({baseline,candidate}:{baseline:number|null|undefined;candidate:number|null|undefined}){
  if(baseline==null||candidate==null)return <p className="ml-empty">No comparable source observations yet.</p>;
  const ceiling=Math.max(.02,baseline,candidate)*1.1;
  return <div className="ml-proof-bars">
    <div><span>ELO BASELINE</span><div><i style={{width:(100*baseline/ceiling).toFixed(2)+"%"}}/></div><strong>{brier(baseline)}</strong></div>
    <div><span>CHALLENGER</span><div><i style={{width:(100*candidate/ceiling).toFixed(2)+"%"}}/></div><strong>{brier(candidate)}</strong></div>
  </div>;
}

export default function ModelLab({onOpenGames,onOpenAccuracy}:{onOpenGames?:()=>void;onOpenAccuracy?:()=>void}){
 const [index,setIndex]=useState<Index|null>(null);
 const [online,setOnline]=useState<Online|null>(null);
 const [opponent,setOpponent]=useState<Opponent|null>(null);
 const [state,setState]=useState<State|null>(null);
 const [health,setHealth]=useState<Health|null>(null);
 const [challengers,setChallengers]=useState<Challenger|null>(null);
 const [drift,setDrift]=useState<Drift|null>(null);
 const [loaded,setLoaded]=useState(false);
 const [focused,setFocused]=useState(groups[0].name);
 useEffect(()=>{
   let live=true;
   async function get(file:string){
     try{const r=await fetch(base+file);return r.ok?await r.json():null;}
     catch{return null;}
   }
   Promise.all([
     get("/forecasts/index.json"),get("/current/2027-online-model.json"),
     get("/current/2027-opponents.json"),get("/current/2027-state-space.json"),
     get("/current/archive-health.json"),get("/current/challengers.json"),get("/current/drift.json"),
   ]).then(([i,o,p,s,h,c,d])=>{
      if(!live)return;
      setIndex(i);setOnline(o);setOpponent(p);setState(s);setHealth(h);setChallengers(c);setDrift(d);setLoaded(true);
   });
   return()=>{live=false};
 },[]);
 const forward=index?.uniqueGames;
 const paired=forward?.pairedModelComparisons||{};
 const selected=groups.find(g=>g.name===focused)||groups[0];
 const info=paired[focused];
 const recent=useMemo(()=>opponent?.chronological?.perDate||[],[opponent]);
 const sourceMatch=opponent?.retrievedAtUtc&&state?.ratingRetrievedAtUtc ?
    opponent.retrievedAtUtc===state.ratingRetrievedAtUtc : null;
 return <section className="content-section ml" id="model-lab">
   <div className="ml-hero"><div><span className="section-kicker">MODEL LAB 2.2 / SOURCE-AWARE LEARNING</span>
      <h1>WHICH MODEL <em>EARNS THE PICK?</em></h1>
      <p>Historical stacks, verified efficiency signals and date-adaptive ensembles, one transparent standard: compare against Elo on the same games, never relabel historical replay as public pretipoff accuracy, and never chase a loss with hindsight.</p>
      <div className="ml-hero-ctas">
        <button onClick={onOpenGames} type="button">FIND A REAL GAME ↗</button>
        <button className="subtle" onClick={onOpenAccuracy} type="button">OPEN ACCURACY & PICKS ↗</button>
      </div></div>
      <aside className="ml-hero-status"><small>FORWARD EVIDENCE AVAILABLE</small>
        <strong>{forward?.settledUniqueGames??0}</strong><span>unique settled first-published game picks</span>
        <p>{health?.message||"Archive health unavailable — no false accuracy claim."}</p>
        <small>ARCHIVE {health?.status?.replaceAll("-"," ").toUpperCase()||"NOT VERIFIED"}</small>
      </aside></div>
   {!loaded?<p className="premium-empty" role="status">Reading source-linked experiment and archive reports…</p>:<>
   <ForecastIntelligence/>
   <EloV2Comparison/>
   <EloV3Evidence/>
   <EloV3BoxEvidence/>
   <ApPollComparison/>
   <div className="ml-metrics">
      <div><small>OPPONENT-AWARE RETROSPECTIVE GAMES</small><strong>{opponent?.games?.toLocaleString()??"—"}</strong><span>Same-day-frozen experiments</span></div>
      <div><small>KALMAN RETROSPECTIVE GAMES</small><strong>{state?.evaluatedGames?.toLocaleString()??"—"}</strong><span>Two Gaussian variants / identical fixtures</span></div>
      <div><small>LOGISTIC STATUS</small><strong>{online?.mode?.toUpperCase()??"—"}</strong><span>{online?.chronologicalGatePassed?"Date-block gate passed":"No validated model promotion claimed"}</span></div>
      <div><small>WATCHED DRIFT STATES</small><strong>{state?.driftWatchTeams??"—"}</strong><span>Heuristic watch only, not confirmed injuries</span></div>
   </div>
   {sourceMatch===false?<div className="ml-warning" role="alert">Research reports are from different source retrievals. Cross-model current-state comparisons are unavailable until the next verified build.</div>:null}
   <div className="ml-intro"><span className="section-kicker">01 / REAL PUBLIC RESULTS</span>
      <h2>Forward <em>scoreboard.</em></h2>
      <p>These numbers are from the same game IDs, using probabilities actually frozen before tipoff. Lower Brier is better. A model is not eligible simply for existing in the experiment.</p></div>
   <div className="ml-card-grid">
      {groups.map(g=>{
        const p=paired[g.name];
        return <button type="button" key={g.name} onClick={()=>setFocused(g.name)}
          aria-pressed={focused===g.name} className={"ml-model-card"+(focused===g.name?" is-focused":"")}>
          <span className="ml-pill">{g.label}</span><h3>{g.name}</h3>
          <strong>{p?.candidateBrier!=null?brier(p.candidateBrier):"—"}</strong>
          <span>Genuine paired Brier ↓ / {p?.pairedGames??0} settled games</span>
          <small>{g.name==="Online logistic challenger"?
            (online?.mode==="active"?"CONDITIONALLY ACTIVE":"SHADOW / ELO OPERATING"):"RESEARCH ONLY"}</small>
        </button>;
      })}
   </div>
   <div className="ml-focus" aria-live="polite">
     <div><span className="section-kicker">02 / SELECTED FORECASTER</span><h3>{selected.name}</h3>
       <p>{selected.why}</p>
       <p className="ml-proof-note">{info?.pairedGames?
         info.pairedGames+" actually settled, independently archived first-pick games across "+info.pairedDates+" calendar dates.":
         "No settled pretipoff paired evidence exists yet. These are not imaginary 0% or 100% accuracy scores."}</p>
       {info?.dateBlockGain95?<p className="ml-confidence">Date-block 95% descriptive Brier improvement interval: {info.dateBlockGain95.map(v=>v.toFixed(4)).join(" to ")}</p>:<p className="ml-confidence">Date-block confidence interval withheld until at least 40 games across five dates.</p>}
     </div>
     <div className="ml-stat-panel"><small>ON IDENTICAL GENUINE GAMES · LOWER IS BETTER</small>
       <ProofBar baseline={info?.baselineEloBrier} candidate={info?.candidateBrier}/>
       <div className="ml-paired">
          <div><small>ELO CORRECT WINNER</small><strong>{pct(info?.baselineEloAccuracy)}</strong></div>
          <div><small>CHALLENGER CORRECT WINNER</small><strong>{pct(info?.candidateAccuracy)}</strong></div>
          <div><small>BRIER IMPROVEMENT VS ELO</small><strong>{info?.candidateBrierGain==null?"—":(info.candidateBrierGain>0?"+":"")+info.candidateBrierGain.toFixed(4)}</strong></div>
       </div>
     </div>
   </div>
   <div className="ml-section-divider"/>
   <div className="ml-intro"><span className="section-kicker">03 / OUT-OF-DATE REPLAY — NOT FORWARD PICKS</span>
     <h2>Prior-date <em>experiments.</em></h2>
     <p>Each group below uses previous game dates only, but evaluation windows differ by method. Compare Elo and candidate **within each row**. Do not directly rank models trained on different samples.</p></div>
   <div className="ml-replay">
     <div><span>OPPONENT-AWARE / SHARED DATES</span>
        <h4>{opponent?.games??0} tested games</h4>
        <ProofBar baseline={opponent?.chronological.eloBrier}
          candidate={opponent?.chronological.opponentAdjustedBrier}/>
        <p>Previous-date margin surprise relative to the opponent's *previous-date Elo*; strength adjustment is bounded and shrunken for small samples.</p>
     </div>
     <div><span>GAUSSIAN STATE-SPACE / SHARED DATES</span>
        <h4>{state?.evaluatedGames??0} tested games</h4>
        <ProofBar baseline={state?.eloSameDayBrier} candidate={state?.brier}/>
        <p>Fixed process/observation noise, matched to Elo and dated observations.</p>
     </div>
     <div><span>ADAPTIVE STATE-SPACE / SHARED DATES</span>
        <h4>{state?.evaluatedGames??0} tested games</h4>
        <ProofBar baseline={state?.eloSameDayBrier} candidate={state?.adaptiveBrier}/>
        <p>Only persistent pregame innovation evidence raises *next* process variance; a drift-watch alert is not a proven player or roster change.</p>
     </div>
     <div><span>ONLINE LOGISTIC / WALK-FORWARD</span>
        <h4>{online?.evaluationGames??0} tested games</h4>
        <ProofBar baseline={online?.walkForward?.eloBrier}
          candidate={online?.walkForward?.onlineLogisticBrier}/>
        <p>{online?.reason??"Model artifact not yet published."} Separate live-pick activation also requires prior pretipoff paired evidence.</p>
     </div>
   </div>
   <section className="v11-research" aria-label="Additional independently evaluated model challengers">
      <div className="ml-intro"><span className="section-kicker">NEW / CAUSAL CHALLENGER BENCHMARK</span>
        <h2>Bayesian & <em>residual learning.</em></h2>
        <p>Strict previous-date replay. New challengers are research-only: this is not proof of better public pregame accuracy. All three probabilities below are scored on the same dated games.</p></div>
      {challengers&&challengers.ratingRetrievedAtUtc===opponent?.retrievedAtUtc?
        <div className="v11-model-grid">{([
          ["elo","ELO REFERENCE"],["bayesianShrinkage","BAYESIAN SHRINKAGE"],["onlineResidualStumps","ONLINE GRADIENT STUMPS"]
        ] as const).map(([key,label])=><div key={key}>
           <small>{label}</small><strong>{brier(challengers.methods[key]?.brier)}</strong>
           <span>{pct(challengers.methods[key]?.accuracy)} correct · {challengers.methods[key]?.games||0} identical games</span>
        </div>)}</div>:
        <p className="ml-warning">No complete matching-source Bayesian and residual challenger report is published yet.</p>}
      <p className="ml-footer">Shrinkage uses a 1500 Elo prior and attenuates uncertain early-season probabilities; residual stumps update only after their game's date. Neither can be automatically promoted. See the v1.1 validation documentation.</p>
   </section>
   <section className="v11-drift" aria-label="Prospective forecast drift review">
      <div><span className="section-kicker">LIVE FIRST-PICK ERROR WATCH / NO HINDSIGHT</span>
        <h2>Is the model <em>drifting?</em></h2>
        <p>{drift?.reason||"Awaiting sourced forward-drift report."}</p></div>
      <div className="v11-drift-data">
        <div><small>PRIOR 25-GAME BRIER</small><strong>{brier(drift?.priorBrier)}</strong></div>
        <div><small>LATEST 25-GAME BRIER</small><strong>{brier(drift?.recentBrier)}</strong></div>
        <div><small>CHANGE / HIGHER IS WORSE</small><strong>{drift?.brierDelta==null?"—":(drift.brierDelta>0?"+":"")+drift.brierDelta.toFixed(4)}</strong></div>
      </div>
      <p className="ml-footer">{drift?.status==="review"?"Review recommended; no automatic retuning.":"Review begins only after 50 actual independently settled first picks."} An error increase is descriptive, not automatically statistical evidence of distribution shift.</p>
   </section>
   <ModelEvidence/>
   <ResearchVisualization/>
   <ScoreResearchEvidence/>
   <EnsembleEvidence/>
   <HistoricalEvidence/>
   <ProbabilisticResearch/>
   <ModelChampionship/>
   <div className="ml-recent">
     <div><span className="section-kicker">04 / THE MOST RECENT OPPONENT EXPERIMENT</span>
       <h3>Game-day <em>performance.</em></h3>
       <p>Each plotted game date is evaluated before that date's outcomes change the model. Blue = Elo Brier; mint = opponent-aware Brier. Lower bars indicate better probabilities.</p></div>
     <div className="ml-day-plot">{recent.length?recent.slice(-18).map(r=>{
       const max=Math.max(.04,r.eloBrier??0,r.opponentBrier??0)*1.1;
       return <div className="ml-day-bar" key={r.date} title={r.date+" · "+r.games+" games"}>
         <div className="ml-day-pair"><i style={{height:(100*(r.eloBrier??0)/max).toFixed(2)+"%"}}/>
           <b style={{height:(100*(r.opponentBrier??0)/max).toFixed(2)+"%"}}/></div>
         <span>{r.date.slice(5)}</span></div>;
     }):<p>No previous-date sample has been published yet.</p>}</div>
   </div>
   <p className="ml-footer">Every candidate's forward result depends on the independent before-tipoff archive and later final-status verification. A lower historical Brier does not guarantee improvement on tomorrow's games. The date-ordered logistic gate and separate public forward gate can reject or demote a model automatically. <a href="https://github.com/dokeefe414/March-Madness-Forecasting26-27/blob/main/docs/v09-model-validation.md" target="_blank" rel="noreferrer">READ THE SOURCE AND MATH ↗</a></p>
   </>}
 </section>;
}

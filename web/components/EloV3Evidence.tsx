"use client";
import {useEffect,useState} from "react";
const base=process.env.NEXT_PUBLIC_BASE_PATH||"";
type Score={games:number;brier:number|null;logLoss:number|null;accuracy:number|null;ece:number|null};
type Year={season:number;games:number;elo2:Score;elo3:Score;elo3Multi:Score;gains:{elo3:number;elo3Multi:number}};
type Report={schemaVersion:number;type:string;status:string;games:number;
  holdoutSeasons:number[];elo2?:Score;elo3?:Score;elo3Multi?:Score;
  brierGain?:number|null;multiYearBrierGain?:number|null;
  seasonBlockGain95?:Record<string,number[]|null>;
  positiveGainSeasons?:Record<string,number>;bySeason?:Year[];reason?:string};
const four=(x:number|null|undefined)=>x==null?"—":x.toFixed(4);
const pct=(x:number|null|undefined)=>x==null?"—":(x*100).toFixed(1)+"%";
export default function EloV3Evidence(){
 const [data,setData]=useState<Report|null>(null);
 const [loaded,setLoaded]=useState(false);
 useEffect(()=>{let live=true;fetch(base+"/research/elo-v3-historical.json",{cache:"no-store"})
   .then(r=>r.ok?r.json():null).then(d=>{if(live){setData(d);setLoaded(true)}})
   .catch(()=>{if(live)setLoaded(true)});
   return()=>{live=false};
 },[]);
 const ready=data?.schemaVersion===2&&data.type==="elo3-versus-elo2-season-holdout"&&data.status==="ready";
 const interval=data?.seasonBlockGain95?.elo3;
 return <section className="ev2" id="elo3-benchmark" aria-label="Elo 3.0 historical benchmark against Elo 2.0">
   <div className="ev2-head"><div className="ev2-eyebrow">RESEARCH SERIES 03 / HISTORICAL HOLDOUTS</div>
     <div className="ev2-title-row"><div><h2>ELO 3.0 <em>UNDER TEST.</em></h2>
       <p>Same historical games, same prior-year identities, identical previous-date embargo. Tests whether extra statistical complexity genuinely improves win probabilities.</p></div>
       <div className="ev2-stamp"><small>PUBLIC PICKS</small><strong>UNCHANGED</strong><span>No automatic champion promotion</span></div>
     </div>
   </div>
   {!loaded?<p className="ev2-empty" role="status">Reading pinned historical research…</p>:
    !ready?<p className="ev2-empty" role="status">Historical Elo 3.0 comparison unavailable: {data?.reason||"verified complete-season results have not been published"}. No accuracy improvement is claimed.</p>:
    <>
     <div className="ev2-stat-strip">
       <div><small>PAIRED HELD-OUT GAMES</small><strong>{data.games.toLocaleString()}</strong><span>{data.holdoutSeasons.length} complete test seasons</span></div>
       <div><small>ELO 2.0 BRIER</small><strong>{four(data.elo2?.brier)}</strong><span>Lower is better</span></div>
       <div><small>ELO 3.0 BRIER</small><strong>{four(data.elo3?.brier)}</strong><span>One-year prior for fair matching</span></div>
       <div><small>ELO 3.0 / 3-YEAR BRIER</small><strong>{four(data.elo3Multi?.brier)}</strong><span>Only independently linked historical IDs</span></div>
     </div>
     <div className="ev2-method-strip">
       <div><b>PAIRED BRIER GAIN</b><span>{data.brierGain==null?"—":(data.brierGain>0?"+":"")+four(data.brierGain)} (positive favors Elo 3.0)</span></div>
       <div><b>WINNER ACCURACY</b><span>Elo2 {pct(data.elo2?.accuracy)} / Elo3 {pct(data.elo3?.accuracy)}</span></div>
       <div><b>LOG LOSS</b><span>Elo2 {four(data.elo2?.logLoss)} / Elo3 {four(data.elo3?.logLoss)}</span></div>
       <div><b>SEASON-BLOCK 95% CI</b><span>{interval?.map(x=>four(x)).join(" to ")||"Insufficient seasons"}</span></div>
     </div>
     <div className="ev2-content"><div className="ev2-section-top"><div><small>FIXED YEARS / 2016–2025</small>
       <h3>Results by <em>season.</em></h3>
       <p>Do not treat a low training error or an unpaired matchup as proof of better predictions. Negative gains mean Elo 3.0 was worse.</p></div></div>
       <div className="ev2-table-scroll"><table className="ev2-table">
        <thead><tr><th>SEASON</th><th>GAMES</th><th>ELO 2.0</th><th>ELO 3.0</th><th>3-YEAR PRIOR</th><th>BRIER GAIN</th></tr></thead>
        <tbody>{(data.bySeason||[]).map(y=><tr key={y.season}><td>{y.season}</td>
          <td>{y.games.toLocaleString()}</td><td>{four(y.elo2.brier)}</td>
          <td>{four(y.elo3.brier)}</td><td>{four(y.elo3Multi.brier)}</td>
          <td className={y.gains.elo3>0?"ev2-positive":""}>{y.gains.elo3>0?"+":""}{four(y.gains.elo3)}</td>
        </tr>)}</tbody>
       </table></div>
       <p className="ev2-footnote">The pinned historical compact source has no possessions or Four Factors. Those features are disabled in this test rather than fabricated. Current 2027 rankings have neutral preseason priors because the historical Kaggle and modern NCAA ID spaces have not been independently bridged. This is retrospective date-frozen evidence, not prospective first-published game-pick accuracy.</p>
     </div>
    </>}
 </section>;
}

import {expect, test} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function section(page: import("@playwright/test").Page, label:string) {
  // Primary navigation stays intentionally small; older deep links remain
  // reachable under the accessible More menu on desktop and mobile.
  if(["2027 Pulse","Field Watch","Matchups","Historical","Archive","Research","About"].includes(label)){
    const summary=page.locator(".mf-simple-nav:visible .mf-more summary").first();
    await expect(summary).toBeVisible();
    await summary.click();
  }
  const button=page.locator("button:visible").filter({hasText:new RegExp("^"+label+"$")}).first();
  await expect(button).toBeVisible();
  await button.click();
}

test("v0.9 games, real accuracy, models and historical workspaces navigate",async ({page},testInfo)=>{
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await section(page,"2027 Pulse");
  await expect(page.getByRole("heading",{name:/Current pulse/i})).toBeVisible();
  await section(page,"Field Watch");
  await expect(page.getByRole("heading",{name:/Field watchlist/i})).toBeVisible();
  await expect(page.getByText(/ZERO LOCKS YET/i)).toBeVisible();
  await section(page,"Accuracy & Picks");
  await expect(page.getByRole("heading",{name:/Prediction ledger/i})).toBeVisible();
  await expect(page.getByText(/NO HINDSIGHT/i)).toBeVisible();
  await section(page,"Model Lab");
  await expect(page.locator("#model-lab")).toBeVisible();
  await expect(page.getByRole("heading",{name:/WHICH MODEL EARNS THE PICK/i})).toBeVisible();
  await section(page,"Research");
  await expect(page.getByRole("heading",{name:/Research laboratory/i})).toBeVisible();
  await section(page,"Historical");
  await expect(page.getByRole("heading",{name:/Power rankings/i})).toBeVisible();
  await section(page,"Matchups");
  await expect(page.getByRole("heading",{name:/Matchup lab/i})).toBeVisible();
  await section(page,"Bracket");
  await expect(page.getByRole("heading",{name:/Bracket laboratory/i})).toBeVisible();
  await expect(page.getByRole("button",{name:/SIMULATE FULL FIELD/i})).toBeVisible({timeout:20000});
  await page.getByRole("button",{name:/SIMULATE FULL FIELD/i}).click();
  await expect(page.locator(".bracket-results")).toBeVisible({timeout:20000});
  await section(page,"Archive");
  await expect(page.getByRole("heading",{name:/Tournament archive/i})).toBeVisible();
  await page.screenshot({path:"test-results/"+testInfo.project.name+"-archive.png",fullPage:true});
});

test("at supported breakpoints, no viewport-wide horizontal overflow",async ({page},testInfo)=>{
  await page.goto("/");
  for (const name of ["Find a Game","2027 Pulse","Accuracy & Picks","Model Lab","Field Watch","Research","Historical","Bracket"]) {
    await section(page,name);
    await page.waitForTimeout(120);
    const size=await page.evaluate(()=>({
      content:document.documentElement.scrollWidth,
      viewport:document.documentElement.clientWidth,
    }));
    expect(size.content, name+" overflow").toBeLessThanOrEqual(size.viewport+3);
  }
  await page.screenshot({path:"test-results/"+testInfo.project.name+"-layout.png",fullPage:true});
});

test("core page has no critical WCAG violations",async ({page})=>{
  await page.goto("/");
  await section(page,"Find a Game");
  const result=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21a","wcag21aa"]).analyze();
  const severe=result.violations.filter(v=>v.impact==="critical");
  expect(severe.map(v=>v.id+": "+v.description)).toEqual([]);
});

test("game finder supports sourced fixture search, explanations and opponent evidence",async ({page},testInfo)=>{
  // Hermetic browser fixture: never rely on ESPN / NCAA network in CI.
  const fixture=new Date(Date.now()+3*24*60*60*1000).toISOString();
  const profile=(name:string,id:string,elo:number)=>({
    name,teamId:id,rating:elo,trend:3,wins:7,losses:3,
    conference:"Example conference",opponentAverageElo:1502,
    pointsForPerGame:id==="ncaa-home"?82:74,pointsAgainstPerGame:id==="ncaa-home"?72:77,
    recentGames:[{id:"old",date:"2027-01-10",opponent:"Example University",
      home:true,for:80,against:71,outcome:"W"}],ratingHistory:[1500,elo]
  });
  const away=profile("Example Away","ncaa-away",1510);
  const home=profile("Example Home","ncaa-home",1540);
  await page.route("**/current/2027.json",route=>route.fulfill({
    contentType:"application/json",body:JSON.stringify({mode:"current",season:2027,
      retrievedAtUtc:"2027-01-15T12:00:00Z",lastGameDate:"2027-01-14",
      teams:[{...away,rank:2,projectedRating:1513},{...home,rank:1,projectedRating:1543}]}),
  }));
  await page.route("**/current/upcoming.json",route=>route.fulfill({
    contentType:"application/json",body:JSON.stringify({schemaVersion:1,
      generatedAtUtc:"2027-01-15T12:00:00Z",ratingRetrievedAtUtc:"2027-01-15T12:00:00Z",
      lastIncludedGameDate:"2027-01-14",
      coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
      games:[{eventId:"test-fixture-1",scheduledStartUtc:fixture,scheduledEasternDate:fixture.slice(0,10),
        neutralSite:false,home:"Example Home",away:"Example Away",homeTeamId:"ncaa-home",awayTeamId:"ncaa-away",homeWinProbability:.69,
        baselineHomeWinProbability:.65,status:"ready",model:"as-of regular-season Elo",
        homeProfile:home,awayProfile:away,
        factors:[{title:"Strength gap",value:30,detail:"Earlier results influence Elo."},
                 {title:"Venue adjustment",value:65,detail:"Home-court assumption."}],
        commonOpponents:[{opponent:"Example University",homeResultDate:"2027-01-10",
          awayResultDate:"2027-01-11",homeMargin:9,awayMargin:2}],
        headToHead:[]}]})
  }));
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await expect(page.getByLabel("Search upcoming games")).toBeVisible();
  await expect(page.locator(".gc-fixture")).toHaveCount(1);
  await page.locator(".gc-fixture").first().click();
  await expect(page.locator(".gc-detail")).toContainText("69.0%");
  await expect(page.locator(".gc-detail")).toContainText("Example University");
  await expect(page.getByRole("region",{name:"Experimental game score and spread projection"})).toContainText("79.5");
  await expect(page.getByRole("region",{name:"Experimental game score and spread projection"})).toContainText("73.0");
  await expect(page.getByRole("region",{name:"Experimental game score and spread projection"})).toContainText("−6.5");
  await expect(page.getByLabel("Hypothetical team A")).toBeVisible();
  await expect(page.getByLabel("Hypothetical team B")).toBeVisible();
  await page.screenshot({path:"test-results/"+testInfo.project.name+"-game-intelligence.png",fullPage:true});
});

test("v0.9 model lab has deep link, source-honest unavailable forward evidence and one-click game exit",async ({page})=>{
  await page.goto("/?view=models");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.locator("#model-lab")).toBeVisible();
  await expect(page.getByRole("heading",{name:/WHICH MODEL EARNS THE PICK/i})).toBeVisible();
  await expect(page.getByRole("button",{name:/Opponent-aware research/i})).toBeVisible();
  await page.getByRole("button",{name:/Opponent-aware research/i}).click();
  await expect(page.locator(".ml-focus")).toContainText("PREVIOUS-date Elo");
  await page.getByRole("button",{name:/FIND A REAL GAME/i}).click();
  await expect(page.getByRole("heading",{name:/GAME INTELLIGENCE/i})).toBeVisible();
});

test("v0.9 real archived event snapshots render before-tipoff timeline and verifiable missed-game receipt",async ({page})=>{
  const tipoff=new Date(Date.now()+2*24*60*60*1000).toISOString();
  const fixtureData={schemaVersion:1,
    generatedAtUtc:new Date(Date.now()-60*60*1000).toISOString(),
    ratingRetrievedAtUtc:new Date(Date.now()-90*60*1000).toISOString(),
    coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
    games:[{
      eventId:"upcoming-test",scheduledStartUtc:tipoff,scheduledEasternDate:tipoff.slice(0,10),
      neutralSite:false,status:"ready",home:"Example Home",away:"Example Away",
      homeTeamId:"h",awayTeamId:"a",homeWinProbability:.7,baselineHomeWinProbability:.68,
      model:"as-of regular-season Elo",homeProfile:{name:"Example Home",teamId:"h",
        rating:1550,trend:2,wins:7,losses:3,recentGames:[],ratingHistory:[1500,1550]},
      awayProfile:{name:"Example Away",teamId:"a",rating:1510,trend:1,wins:6,losses:4,
        recentGames:[],ratingHistory:[1500,1510]},factors:[],headToHead:[],commonOpponents:[],
    }]
  };
  const first=new Date(Date.now()-36*60*60*1000).toISOString();
  const second=new Date(Date.now()-12*60*60*1000).toISOString();
  const index={uniqueGames:{settledUniqueGames:1,forecastedUniqueGames:2,
      score:{accuracy:0,games:1,brier:.64}},
    snapshots:[
      {id:"snap-earliest",generatedAtUtc:first,count:1,
        predictions:[{eventId:"upcoming-test",homeWinProbability:.60,model:"Elo"}]},
      {id:"snap-next",generatedAtUtc:second,count:1,
        predictions:[{eventId:"upcoming-test",homeWinProbability:.70,model:"Elo"}]},
      {id:"snap-old",generatedAtUtc:"2026-11-06T11:00:00Z",count:1,
        predictions:[{eventId:"finished-test",homeWinProbability:.8,model:"Elo"}]},
    ],
    settlements:[{eventId:"finished-test",predictionKey:"snap-old:finished-test",
      actualResultDate:"2026-11-07",home:"Example Home",away:"Example Away",
      homeScore:60,awayScore:72,predictedHome:.8,observedHome:0,brier:.64,
      winnerCorrect:0,forecastAtUtc:"2026-11-06T11:00:00Z",
      scheduledStartUtc:"2026-11-07T23:00:00Z",espnFinalVerified:true}]
  };
  await page.route("**/current/upcoming.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify(fixtureData)}));
  await page.route("**/current/2027.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
    mode:"current",season:2027,teams:[{name:"Example Home",teamId:"h",rating:1550,wins:7,losses:3},
      {name:"Example Away",teamId:"a",rating:1510,wins:6,losses:4}]
  })}));
  await page.route("**/forecasts/index.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify(index)}));
  await page.route("**/current/archive-health.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
    status:"current",message:"Source-verified archive available",lastArchiveUtc:second})}));
  await page.goto("/?game=upcoming-test");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/GAME INTELLIGENCE/i})).toBeVisible();
  await expect(page.locator(".ga-history")).toContainText("2 originally published captures");
  await expect(page.locator(".ga-probability")).toContainText("60.0%");
  await expect(page.locator(".ga-probability")).toContainText("70.0%");
  await page.locator(".gc-recent-settled button").first().click();
  await expect(page.locator(".ga-postgame")).toContainText("MISSED");
  await expect(page.locator(".ga-postgame")).toContainText("FINAL");
  await expect(page).toHaveURL(/game=finished-test/);
});

test("v1.1 daily shortcuts and empty-source navigation remain keyboard accessible",async ({page})=>{
  await page.goto("/");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("navigation",{name:"Explore March Forecast"})).toBeVisible();
  await expect(page.getByRole("link",{name:/TODAY'S GAMES/i})).toBeVisible();
  await page.getByRole("navigation",{name:"Explore March Forecast"}).getByRole("button",{name:/ROAD TO MARCH/i}).click();
  await expect(page.getByRole("heading",{name:/Field watchlist/i})).toBeVisible();
  await section(page,"Find a Game");
  await expect(page.getByRole("heading",{name:/Game intelligence/i})).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator("body")).toBeVisible();
});
test("v1.1 model lab labels new challengers as retrospective, not public picks",async ({page})=>{
  await page.goto("/?view=models");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  await expect(page.getByRole("heading",{name:/Bayesian & residual learning/i})).toBeVisible();
  await expect(page.getByRole("heading",{name:/Is the model drifting/i})).toBeVisible();
  await expect(page.getByText(/Strict previous-date replay/i)).toBeVisible();
});

test("v1.2 team intelligence deep links and game evidence page exist",async ({page})=>{
 // Hermetic source-backed mock: the repository does not commit generated
 // /current artifacts (they are built by the Pages publication workflow).
 const team=(id:string,name:string,rating:number)=>({teamId:id,name,rank:1,rating,projectedRating:rating,trend:4,wins:6,losses:2,history:[1500,rating],conference:"Example League",conferenceVerified:true,
   opponentAverageElo:1490,adjOff100:109,adjDef100:97,pacePossessions:67});
 const retrievedAtUtc="2026-11-17T12:00:00Z";
 await page.route("**/current/2027.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   season:2027,mode:"current",retrievedAtUtc,teams:[team("ncaa-duke","Duke",1550),team("ncaa-unc","North Carolina",1510)]})}));
 await page.route("**/current/2027-games.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   season:2027,retrievedAtUtc,games:[{id:"game-1",date:"2026-11-16",home:"Duke",away:"North Carolina",homeScore:78,awayScore:72}]})}));
 await page.route("**/current/upcoming.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   games:[{eventId:"next-1",homeTeamId:"ncaa-duke",awayTeamId:"ncaa-unc",home:"Duke",away:"North Carolina",scheduledStartUtc:new Date(Date.now()+3*86400000).toISOString(),homeWinProbability:.6}]})}));
 await page.goto("/?view=teams");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 await expect(page.getByRole("heading",{name:/TEAM INTELLIGENCE/i})).toBeVisible();
 await expect(page.getByRole("textbox",{name:"Search teams"})).toBeVisible();
 await expect(page.locator(".v12-team-detail")).toBeVisible({timeout:20000});
 await page.getByRole("textbox",{name:"Search teams"}).fill("Duke");
 await expect(page.locator(".v12-team-scroll button").first()).toBeVisible();
});
test("v1.2 bracket pick-em has rounds, chooser and reset",async ({page})=>{
 await page.goto("/?view=bracket");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 await expect(page.getByRole("button",{name:/SIMULATE FULL FIELD/i})).toBeVisible({timeout:20000});
 await expect(page.getByRole("heading",{name:/Build your own bracket/i})).toBeVisible();
 await expect(page.getByRole("group",{name:"Tournament round"})).toBeVisible();
 await page.getByRole("group",{name:"Tournament round"}).getByRole("button",{name:"ROUND OF 64"}).click();
 await expect(page.locator(".v12-match").first()).toBeVisible();
 await page.locator(".v12-match button:enabled").first().click();
 await expect(page.getByText(/available games picked/)).toBeVisible();
 await page.getByRole("button",{name:"RESET PICKS"}).click();
 await expect(page.getByText(/Bracket picks reset/)).toBeVisible();
});
test("v1.2 installable manifest and settlement diagnostic shell load",async ({page})=>{
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 await expect(page.getByRole("heading",{name:/Prediction ledger/i})).toBeVisible();
 await expect(page.getByRole("heading",{name:/What happened after the pick/i})).toBeVisible();
 const manifest=await page.request.get("/manifest.webmanifest");
 expect(manifest.status()).toBe(200);
 const json=await manifest.json();
 expect(json.name).toMatch(/March Forecast/);
});

test("v1.3 two independent bracket players can disagree on identical matchups",async ({page})=>{
 await page.goto("/?view=bracket");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const duel=page.getByRole("region",{name:"Two-player bracket competition"});
 await expect(duel.getByRole("heading",{name:/TWO PLAYERS/i})).toBeVisible({timeout:20000});
 await duel.getByRole("group",{name:"Duel round"}).getByRole("button",{name:"ROUND OF 64"}).click();
 // A historical play-in seed can leave one entrant pending in some first-round
 // matches. Pick an actual two-entrant fixture rather than clicking a disabled
 // legitimate "winner pending" placeholder.
 const game=duel.locator(".v13-duel-match").filter({has:page.locator("button:last-of-type:not([disabled])")}).first();
 await expect(game.getByRole("button")).toHaveCount(2);
 await expect(game.getByRole("button").last()).toBeEnabled();
 await game.getByRole("button").first().click();
 await duel.getByRole("group",{name:"Active bracket competitor"}).getByRole("button",{name:"PLAYER B"}).click();
 await game.getByRole("button").last().click();
 await expect(duel.getByRole("heading",{name:/HEAD-TO-HEAD DIFFERENCES/i})).toBeVisible();
 await expect(duel.getByText(/A: .* B:/)).toBeVisible();
});
test("v1.3 operations checklist exposes verifiable source evidence",async ({page})=>{
 await page.route("**/current/operations.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  state:"review",archiveStatus:"current",checkedAtUtc:"2026-11-17T17:30:00Z",lastSuccessfulCaptureUtc:"2026-11-17T15:08:46Z",
  captureAgeHours:2.4,checkedSourceEvents:175,unmatchedSourceEvents:33,uniqueArchivedEvents:142,
  repeatSnapshots:0,uniqueSettledEvents:0,delayedSnapshotEntries:1,sourceWarnings:[],
  checks:[{name:"Verified-final backlog",state:"review",detail:"1 source final awaiting independent validation"}],
  delayedExamples:[{eventId:"123",home:"Duke",away:"UNC",hoursSinceListedStart:53}]
 })}));
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Public forecast operations and source quality"});
 await expect(panel.getByRole("heading",{name:/Can we trust the feed/i})).toBeVisible({timeout:15000});
 await expect(panel.getByText(/ARCHIVE REVIEW/i)).toBeVisible();
 await expect(panel.getByText("Verified-final backlog")).toBeVisible();
});
test("v1.3 Model Lab differentiates fitted research from prospectively verified picks",async ({page})=>{
 await page.route("**/current/advanced-models.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  mode:"research-only",retrievedAtUtc:"2026-11-17T15:00:00Z",evaluatedGames:80,
  methods:{elo:{games:80,brier:.228,accuracy:.56,logLoss:.67},
   bayesianGaussian:{games:80,brier:.221,accuracy:.58,logLoss:.65},
   gradientBoostedTrees:{games:80,brier:.23,accuracy:.54,logLoss:.68}},
  perDate:[{date:"2026-11-13",games:20,eloBrier:.22,bayesianBrier:.21,gradientBoostedBrier:.23},
           {date:"2026-11-14",games:20,eloBrier:.23,bayesianBrier:.22,gradientBoostedBrier:.24}]
 })}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Interactive prediction research visualizations"});
 await expect(panel.getByRole("heading",{name:/Explore the evidence/i})).toBeVisible({timeout:15000});
 await expect(panel.getByText("Gradient-boosted CART")).toBeVisible();
 await expect(panel.getByText(/No truly settled first picks|Only earliest archived pregame predictions/i)).toBeVisible();
});

test("verified first-pick results show correct and missed without counting duplicate captures",async ({page})=>{
 const first="2026-11-16T13:00:00Z";
 const after="2026-11-17T17:00:00Z";
 const rows=[
  {eventId:"f1",date:"2026-11-17",scheduledStartUtc:"2026-11-17T23:00:00Z",forecastAtUtc:first,
   home:"Example Home",away:"Example Away",homeScore:68,awayScore:71,predictedHome:.8,observedHome:0,
   predictedWinner:"Example Home",actualWinner:"Example Away",correct:false,brier:.64,model:"Elo"},
  {eventId:"f2",date:"2026-11-17",scheduledStartUtc:"2026-11-17T23:00:00Z",forecastAtUtc:first,
   home:"Example Two",away:"Example Three",homeScore:81,awayScore:75,predictedHome:.7,observedHome:1,
   predictedWinner:"Example Two",actualWinner:"Example Two",correct:true,brier:.09,model:"Elo"}
 ];
 const index={
   schemaVersion:1,generatedAtUtc:after,
   snapshots:[{id:"a",generatedAtUtc:first,count:2,predictions:[]},
              {id:"b",generatedAtUtc:after,count:1,predictions:[]}],
   settlements:[],scores:{settledPredictions:3,brier:.3,logLoss:.6,winnerAccuracy:.67},
   uniqueGames:{forecastedUniqueGames:2,settledUniqueGames:2,verifiedOutcomes:rows,
     score:{games:2,accuracy:.5,brier:.365,logLoss:.6},
     byModel:{Elo:{games:2,accuracy:.5,brier:.365}},
     reference:{pairedGames:2,eloBrier:.365,actualModelBrier:.365},
     shadowComparison:{pairedGames:0,eloBrier:null,challengerBrier:null,challengerBrierGain:null},
     trajectory:[],calibration:[],recentMisses:[]},
 };
 await page.route("**/forecasts/index.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify(index)}));
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const outcomes=page.getByRole("region",{name:"Correct and missed original before-tipoff predictions"});
 await expect(outcomes.locator(".v14-outcome")).toHaveCount(2);
 await expect(outcomes.getByText("CORRECT FAVORITES")).toBeVisible();
 await expect(outcomes.locator(".v14-result-metrics")).toContainText("1");
 await expect(outcomes.locator(".v14-outcome.is-right")).toContainText("Example Two");
 await expect(outcomes.locator(".v14-outcome.is-wrong")).toContainText("Example Away");
 await outcomes.getByRole("button",{name:"MISSED"}).click();
 await expect(outcomes.locator(".v14-outcome")).toHaveCount(1);
 await expect(outcomes.locator(".v14-outcome")).toContainText("MISSED PICK");
 await outcomes.getByRole("button",{name:"CORRECT"}).click();
 await expect(outcomes.locator(".v14-outcome")).toHaveCount(1);
 await expect(outcomes.locator(".v14-outcome")).toContainText("CORRECT PICK");
});

test("score predictor declines unavailable per-game points rather than inventing a spread",async ({page})=>{
 const fixture=new Date(Date.now()+4*86400000).toISOString();
 const baseTeam=(name:string,teamId:string)=>({
  teamId,name,rank:1,rating:1500,projectedRating:1500,trend:0,wins:3,losses:1,history:[1500]});
 const away=baseTeam("Away","a"),home=baseTeam("Home","h");
 await page.route("**/current/2027.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
  mode:"current",season:2027,teams:[home,away]})}));
 await page.route("**/current/upcoming.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
   games:[{eventId:"score-test",scheduledStartUtc:fixture,scheduledEasternDate:fixture.slice(0,10),
    neutralSite:true,status:"ready",home:"Home",away:"Away",homeTeamId:"h",awayTeamId:"a",
    homeWinProbability:.55,baselineHomeWinProbability:.55,
    homeProfile:{...home,conference:"Test",recentGames:[],ratingHistory:[1500]},
    awayProfile:{...away,conference:"Test",recentGames:[],ratingHistory:[1500]},factors:[]}]
 })}));
 await page.goto("/");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const score=page.getByRole("region",{name:"Experimental game score and spread projection"});
 await expect(score).toContainText("NOT ENOUGH VERIFIED SCORING DATA");
 await expect(score).not.toContainText("PROJECTED SPREAD");
});

test("verified possession rates produce distinct adjusted score scenarios",async ({page})=>{
 const scheduled=new Date(Date.now()+4*86400000).toISOString();
 const team=(id:string,name:string,off:number,def:number)=>({
  teamId:id,name,rank:1,rating:1500,projectedRating:1500,trend:0,
  wins:9,losses:2,history:[1500],pointsForPerGame:78,pointsAgainstPerGame:73,
  adjOff100:off,adjDef100:def,offRating100:off,defRating100:def,
  pacePossessions:id==="h"?68:72,possessionGames:9});
 const home=team("h","Home School",118,101),away=team("a","Away School",108,106);
 await page.route("**/current/2027.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  mode:"current",season:2027,teams:[home,away],retrievedAtUtc:"2026-11-17T14:00:00Z"})}));
 await page.route("**/current/upcoming.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  schemaVersion:1,generatedAtUtc:"2026-11-17T14:00:00Z",
  coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
  games:[{eventId:"adj-test",scheduledStartUtc:scheduled,scheduledEasternDate:scheduled.slice(0,10),
   neutralSite:true,status:"ready",home:home.name,away:away.name,homeTeamId:home.teamId,awayTeamId:away.teamId,
   homeWinProbability:.72,baselineHomeWinProbability:.72,model:"Elo",
   homeProfile:{...home,conference:"Example",recentGames:[],ratingHistory:[1500]},
   awayProfile:{...away,conference:"Example",recentGames:[],ratingHistory:[1500]},
   factors:[],commonOpponents:[],headToHead:[]}]} )}));
 await page.goto("/?view=games");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Experimental game score and spread projection"});
 await expect(panel).toContainText("OPPONENT-ADJUSTED POSSESSION MODEL");
 await expect(panel).toContainText("70.0");
 await expect(panel).toContainText("PROJECTED SPREAD");
 await expect(panel).toContainText("9 source-linked possession games");
});
test("scoring research evidence does not pretend it is a live pregame record",async ({page})=>{
 await page.route("**/current/score-research.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  schemaVersion:1,season:2027,mode:"research-only",retrievedAtUtc:"2026-11-17T14:00:00Z",
  sourceGames:80,evaluatedGames:10,evaluatedDays:4,excluded:{},
  methods:{opponentAdjusted:{games:10,marginMAE:8.1,totalMAE:12.4,brier:.22},
   rawScoringMeans:{games:10,marginMAE:9.6,totalMAE:14,brier:.24},
   elo:{games:10,brier:.21}},
  perDate:[{date:"2026-11-09",games:5,adjustedMarginMAE:7,rawMarginMAE:9,adjustedBrier:.22,rawBrier:.25,eloBrier:.2}],
  modelVersion:"regularized-additive-margin-v1",policy:"research only" })}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const section=page.getByRole("region",{name:"Chronological score and margin forecasting benchmark"});
 await expect(section.getByRole("heading",{name:/PROVE THE SCORING EDGE/i})).toBeVisible();
 await expect(section).toContainText("8.10");
 await expect(section).toContainText("not timestamped prospective first-pick evidence");
});

test("v1.6 independent portfolio evidence never claims retrospective recombination is a real pregame win",async ({page})=>{
 await page.route("**/current/forward-ensemble.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
  schemaVersion:1,season:2027,mode:"shadow",sourceRetrievedAtUtc:"2026-11-17T18:00:00Z",
  pairedSettledGames:75,pairedSettledDates:8,trainingGames:55,trainingDates:6,
  untouchedHoldoutGames:20,untouchedHoldoutDates:2,
  weight:.25,eloHoldoutBrier:.22,ensembleHoldoutBrier:.21,holdoutBrierGain:.01,
  dateBlockBrierGain95:null,archivedPortfolioGames:0,archivedPortfolioDates:0,
  archivedPortfolioEloBrier:null,archivedPortfolioBrier:null,archivedPortfolioBrierGain:null,
  archivedPortfolioDateBlockGain95:null,prospectiveGatePassed:false,
  scientificReviewEligible:false,promoteAutomatically:false,policy:"No automatic promotion",
 })}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Prospective ensemble holdout and promotion evidence"});
 await expect(panel.getByRole("heading",{name:/DOES THE ENSEMBLE WIN/i})).toBeVisible();
 await expect(panel.getByText("ACTUALLY PUBLISHED BEFORE TIPOFF")).toBeVisible();
 await expect(panel).toContainText("SHADOW RESEARCH — ELO REMAINS ACTIVE");
 await expect(panel).toContainText("RETROSPECTIVE RECOMBINATION");
 await expect(panel).toContainText("The retrospective recombination above is not the prospective performance");
});

test("historical model lab separates source-verified old-season evaluation from current first picks",async ({page})=>{
 const source="pinned-historical-source";
 await page.route("**/research/historical-data-manifest.json",route=>route.fulfill({
  contentType:"application/json",body:JSON.stringify({
   sourceCommit:source,historicalIndexSha256:"test-index-hash",
   includedSeasons:39,includedGames:2560,omittedMissingRatedTeams:2,
   excludedSeasons:[2020,2026],featureAsOf:"season day 132",perSeason:[]})}));
 await page.route("**/research/historical-evaluation.json",route=>route.fulfill({
  contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,sourceCommit:source,datasetIndexSha256:"test-index-hash",
   testedGames:2230,firstTestSeason:1990,lastTestSeason:2025,evaluatedSeasons:34,
   nestedBrierGainVsElo:.004,nestedGainSeasonBlock95:[-.001,.008],
   activePublicModelChanged:false,
   metrics:{elo:{games:2230,brier:.233,logLoss:.668,accuracy:.65},
    calibratedTrendElo:{games:2230,brier:.229,logLoss:.656,accuracy:.66},
    nestedSelected:{games:2230,brier:.229,logLoss:.657,accuracy:.66}},
   yearByYear:[{season:2025,trainingThrough:2024,selectedByEarlierOos:"elo",
    evaluatedGames:67,elo:{brier:.21},nestedSelected:{brier:.21}}],
   limitations:[]})}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Audited historical training and out-of-time model evaluation"});
 await expect(panel).toContainText("PROVE IT");
 await expect(panel).toContainText("2,230");
 await expect(panel).toContainText("0.2330");
 await expect(panel).toContainText("0.2290");
 await panel.getByText("View year-by-year held-out results and audit exclusions").click();
 await expect(panel).toContainText("2020, 2026");
 await expect(panel).toContainText("2025");
});

test("v1.8 five primary tabs and More preserve every original deep link",async ({page})=>{
 await page.goto("/");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const nav=page.locator(".mf-simple-nav:visible").first();
 await expect(nav).toBeVisible();
 await expect(nav.locator(":scope > button")).toHaveCount(5);
 await expect(nav.locator(".mf-more summary")).toBeVisible();
 await section(page,"Archive");
 await expect(page).toHaveURL(/view=history/);
 await expect(page.getByRole("heading",{name:/Tournament archive/i})).toBeVisible();
 await section(page,"Model Lab");
 await expect(page).toHaveURL(/view=models/);
 await section(page,"Research");
 await expect(page).toHaveURL(/view=research/);
 await page.goBack();
 await expect(page).toHaveURL(/view=models/);
 await expect(page.locator("#model-lab")).toBeVisible();
 await page.goto("/?view=compare");
 await expect(page.getByRole("heading",{name:/Matchup lab/i})).toBeVisible();
 await expect(page.locator(".mf-location")).toContainText("Matchups");
 await page.locator(".mf-location button").click();
 await expect(page).toHaveURL(/view=games/);
});
test("v1.8 historical probabilistic study displays calibrated models and empirical interval coverage",async ({page})=>{
 await page.route("**/research/historical-data-manifest.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
  sourceCommit:"pinned",historicalIndexSha256:"index",includedSeasons:40,
  includedGames:2585,excludedSeasons:[2020,2026],omittedMissingRatedTeams:0,perSeason:[]})}));
 const score={games:2270,marginMAE:8.23,totalMAE:14.12,marginRMSE:10.1,totalRMSE:17.8,
   margin80Coverage:.785,total80Coverage:.814,margin80MeanWidth:32.2,total80MeanWidth:44.1};
 const m=(brier:number)=>({games:2270,brier,accuracy:.653,logLoss:.65});
 const bin=(x:number)=>({lower:x/10,upper:(x+1)/10,games:227,averageProbability:.25,realizedFrequency:.27});
 const cal={ece:.022,bins:Array.from({length:10},(_,i)=>bin(i))};
 await page.route("**/research/historical-probabilistic.json",r=>r.fulfill({contentType:"application/json",body:JSON.stringify({
  schemaVersion:1,mode:"historical-research-only",sourceCommit:"pinned",datasetIndexSha256:"index",
  evaluatedYears:35,heldOutGames:2270,trainingData:"pre-tournament only",
  metrics:{elo:m(.2225),calibratedElo:m(.2218),scoringProbability:m(.2201),
           nestedEnsemble:m(.2197),projectedScores:score},
  calibration:{elo:cal,scoring:cal,ensemble:cal},ensembleBrierGainVsElo:.0028,
  seasonBlockGain95:[-.002,.006],
  yearByYear:[{season:2025,trainingThrough:2024,modelWeight:.25,scoreProbabilityScale:1.15,
    elo:m(.21),scoreProbability:m(.20),ensemble:m(.205),scoreIntervals:score}],
  policy:{liveForecastsChanged:false,noAutomaticPromotion:true},
  limitations:[]})}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const study=page.getByRole("region",{name:"Historical probabilistic scoring and calibration research"});
 await expect(study).toContainText("MORE THAN");
 await expect(study).toContainText("2,270");
 await expect(study).toContainText("78.5%");
 await expect(study).toContainText("0.2197");
 await study.getByRole("button",{name:"Score model"}).click();
 await expect(study.getByText("Expected calibration error:")).toBeVisible();
 await study.getByText("See yearly forecasts, learned weights, and scoring error").click();
 await expect(study).toContainText("2025");
});

test("v1.9 source-verified forward accuracy dashboard with honestly pending games and paired Brier",async ({page})=>{
 const rows=[
  {model:"Frozen ensemble",pairedGames:0,pairedDays:0,eloBrier:null,candidateBrier:null,
   eloAccuracy:null,candidateAccuracy:null,brierGain:null,dateBlockGain95:null,reviewEligible:false,autoPromoted:false},
  {model:"Online logistic challenger",pairedGames:0,pairedDays:0,eloBrier:null,candidateBrier:null,
   eloAccuracy:null,candidateAccuracy:null,brierGain:null,dateBlockGain95:null,reviewEligible:false,autoPromoted:false}
 ];
 await page.route("**/current/accuracy-research.json",route=>route.fulfill({
  contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,mode:"first-pick-forward-research",generatedAtUtc:"2026-11-17T20:00:00Z",
   archiveGeneratedAtUtc:"2026-11-17T19:00:00Z",
   immutableFirstPicks:142,verifiedUniqueFinals:0,pendingUniqueGames:142,
   pendingByStatus:{"upcoming":139,"recent-start":3,"awaiting-final":0,"delayed-review":0},
   pendingReview:[],overall:{games:0,brier:null,accuracy:null,logLoss:null},
   daily:[],weekly:[],pairedComparisons:rows,
   frozenScoreResults:{games:0,marginMAE:null,totalMAE:null,homeScoreMAE:null,awayScoreMAE:null,byMethod:[]},
   verification:{independentESPNFinalRequired:true,matchingNCAAScoreRequired:true,
     esponFinalsInspectedInLastArchive:0,sourceWarnings:[],observedScheduleChanges:[]},
   reviewOnly:true,autoPromoted:false})}));
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Verified real-game prediction performance center"});
 await expect(panel).toContainText("142");
 await expect(panel).toContainText("No source-verified finals have settled yet");
 await expect(panel).toContainText("Frozen ensemble");
 await expect(panel).toContainText("No original pregame-frozen score projection");
 await panel.getByRole("button",{name:"Weekly"}).click();
 await expect(panel.getByRole("button",{name:"Weekly"})).toHaveAttribute("aria-pressed","true");
 await panel.getByText("Source verification and delayed-game review").click();
 await expect(panel).toContainText("No original unmatched games currently exceed");
});
test("v1.9 verified daily records and frozen score error remain separate from research backtests",async ({page})=>{
 await page.route("**/current/accuracy-research.json",route=>route.fulfill({
  contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,mode:"first-pick-forward-research",generatedAtUtc:"2026-11-19T18:00:00Z",
   archiveGeneratedAtUtc:"2026-11-19T17:00:00Z",
   immutableFirstPicks:10,verifiedUniqueFinals:3,pendingUniqueGames:7,
   pendingByStatus:{"upcoming":2,"recent-start":1,"awaiting-final":4,"delayed-review":0},
   pendingReview:[],overall:{games:3,brier:.19,accuracy:2/3,logLoss:.55},
   daily:[{period:"2026-11-18",games:3,brier:.19,accuracy:2/3,logLoss:.55,upsets:1}],
   weekly:[{period:"2026-W47",games:3,brier:.19,accuracy:2/3,logLoss:.55,upsets:1}],
   pairedComparisons:[{model:"Frozen ensemble",pairedGames:2,pairedDays:1,eloBrier:.19,candidateBrier:.17,
     eloAccuracy:.5,candidateAccuracy:1,brierGain:.02,dateBlockGain95:null,reviewEligible:false,autoPromoted:false}],
   frozenScoreResults:{games:1,marginMAE:6.4,totalMAE:14.3,homeScoreMAE:3,awayScoreMAE:4.1,byMethod:[]},
   verification:{independentESPNFinalRequired:true,matchingNCAAScoreRequired:true,
      esponFinalsInspectedInLastArchive:8,sourceWarnings:[],observedScheduleChanges:[]},
   reviewOnly:true,autoPromoted:false})}));
 await page.goto("/?view=predictions");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Verified real-game prediction performance center"});
 await expect(panel).toContainText("66.7%");
 await expect(panel).toContainText("2026-11-18");
 await expect(panel).toContainText("0.1700");
 await expect(panel).toContainText("6.40");
 await expect(panel).toContainText("14.30");
});

test("v2.0 saves followed teams only in this browser and surfaces their future source-listed games",async ({page})=>{
 const tipoff=new Date(Date.now()+4*86400000).toISOString();
 const t=(id:string,name:string)=>({teamId:id,name,rank:1,rating:1520,
  projectedRating:1520,trend:0,wins:8,losses:3,history:[1500,1520],
  pointsForPerGame:77,pointsAgainstPerGame:69,
  recentGames:[],ratingHistory:[1500,1520]});
 const home=t("test-h","Home School"),away=t("test-a","Away School");
 await page.route("**/current/2027.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   mode:"current",season:2027,teams:[home,away],retrievedAtUtc:new Date().toISOString()})}));
 await page.route("**/current/upcoming.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,generatedAtUtc:new Date().toISOString(),
   coverage:{futureScheduled:1,eligibleForecasts:1,unmatchedOrAmbiguous:0},
   games:[{eventId:"watch-1",scheduledStartUtc:tipoff,scheduledEasternDate:tipoff.slice(0,10),
    neutralSite:true,status:"ready",home:home.name,away:away.name,
    homeTeamId:home.teamId,awayTeamId:away.teamId,homeWinProbability:.63,
    baselineHomeWinProbability:.63,model:"Elo",homeProfile:home,awayProfile:away,
    factors:[],commonOpponents:[],headToHead:[]}]})}));
 await page.goto("/?view=games");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Your favorite teams and upcoming games"});
 await expect(panel).toContainText("No teams followed yet");
 await panel.getByRole("combobox",{name:"Choose a team to follow"}).selectOption("test-h");
 await panel.getByRole("button",{name:/Follow team/i}).click();
 await expect(panel).toContainText("UP NEXT FOR YOUR TEAMS");
 await expect(panel.getByRole("button",{name:/Away School at Home School/})).toBeVisible();
 await panel.getByRole("button",{name:"Only my teams"}).click();
 await expect(panel.getByRole("button",{name:"Only my teams"})).toHaveAttribute("aria-pressed","true");
 await page.reload();
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const restored=page.getByRole("region",{name:"Your favorite teams and upcoming games"});
 await expect(restored.getByRole("button",{name:"Unfollow Home School"})).toBeVisible();
 await restored.getByRole("button",{name:"Unfollow Home School"}).click();
 await expect(restored).toContainText("No teams followed yet");
});

test("v2.0 model championship distinguishes genuine box coverage and held-out ML evidence",async ({page})=>{
 const m=(brier:number)=>({games:2270,brier,logLoss:.63,accuracy:.67});
 const names=["elo","logistic","boosted","calibratedTrendElo","scoreDistribution","priorShrinkage"];
 const models=Object.fromEntries(names.map((name,i)=>[name,m(.225-i*.002)]));
 await page.route("**/research/historical-data-manifest.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   sourceCommit:"pinned-source-test",historicalIndexSha256:"hash",includedSeasons:40,
   includedGames:2585,missingSeasons:[],excludedSeasons:[],perSeason:[]})}));
 await page.route("**/research/model-championship.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   schemaVersion:1,mode:"historical-only",sourceCommit:"pinned-source-test",indexSha256:"hash",
   evaluatedSeasons:35,heldOutGames:2270,models,nestedChampion:m(.214),
   nestedGainVsElo:.011,nestedGainYearBlock95:[-.002,.02],
   modelGainYearBlock95:{boosted:[-.001,.009],logistic:[-.002,.008]},
   matchupTiers:[],
   yearByYear:[{season:2025,trainedThroughSeason:2024,championSelectedBeforeResults:"elo",
     modelScores:models,nestedChampion:m(.22)}],
   modelSelection:{noAutomaticProductionPromotion:true},
   safety:{livePredictionsModified:false}})}));
 await page.route("**/research/historical-box-coverage.json",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({
   sourceCommit:"pinned-source-test",available:false,sourceGames:0,teamSeasons:0,
   missingBoxSeasons:[2023,2024,2025],sourceSha256:null,limitations:[]})}));
 await page.goto("/?view=models");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const panel=page.getByRole("region",{name:"Multi-model historical tournament championship"});
 await expect(panel).toContainText("2,270");
 await expect(panel).toContainText("THE MODELS");
 await expect(panel).toContainText("0.2140");
 await expect(panel).toContainText("Not supplied.");
 await panel.getByRole("button",{name:"Regularized logistic"}).click();
 await expect(panel).toContainText("Prior");
 await panel.getByText("Year-by-year champion selection and test results").click();
 await expect(panel).toContainText("2025");
});

test("v2.0 simulated bracket shows expected wins, Monte Carlo interval and only resolved seed upsets",async ({page})=>{
 await page.goto("/?view=bracket");
 await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
 const button=page.getByRole("button",{name:/SIMULATE FULL FIELD/i});
 await expect(button).toBeVisible({timeout:20000});
 await page.locator(".sim-controls select").selectOption("1000");
 await button.click();
 await expect(page.getByText("EXPECTED TOURNAMENT WINS")).toBeVisible();
 await expect(page.getByText("MC TITLE SAMPLING BAND (95%)")).toBeVisible();
 const summary=page.getByText(/First-round upset watch/i);
 await summary.click();
 await expect(page.locator(".v20-upset-item").first()).toBeVisible();
});


test("v2.2 source-aligned Forecast Studio switches real research evidence and remains mobile readable",async ({page})=>{
  // Hermetic test fixtures demonstrate UI contracts, not public real scores.
  const retrieved="2026-11-18T15:00:00Z";
  const json=(o:unknown)=>({contentType:"application/json",body:JSON.stringify(o)});
  await page.route("**/current/2027.json",r=>r.fulfill(json({
    mode:"current",season:2027,retrievedAtUtc:retrieved,lastGameDate:"2026-11-17",
    regularSeasonGames:200,teams:[],
  })));
  await page.route("**/current/efficiency-research.json",r=>r.fulfill(json({
    mode:"research-only",season:2027,retrievedAtUtc:retrieved,
    boxStatus:"matched",acceptedPriorDateGames:200,pairedPriorDateBoxGames:120,
    fourFactorSourceGames:0,eligibleWithPriorStats:90,evaluatedGames:60,evaluatedDates:8,
    metrics:{elo:{games:60,brier:.231,accuracy:.65},
      efficiencyResidual:{games:60,brier:.225,accuracy:.66},
      brierGainVsElo:.006,dateBlockGain95:[-.01,.022]},
    featureNames:["intercept"],auditPerDate:[],
  })));
  await page.route("**/current/forward-ensemble.json",r=>r.fulfill(json({
    mode:"shadow",sourceRetrievedAtUtc:retrieved,pairedSettledGames:140,
    archivedPortfolioGames:140,archivedPortfolioBrierGain:.01,
    prequentialAdaptive:{evaluatedGames:56,evaluatedDates:8,eloBrier:.24,
      adaptiveBrier:.23,brierGain:.01,gainDateBlock95:[-.02,.03],
      latestPastWeight:.2,weightChanges:[]},
  })));
  await page.route("**/research/model-championship.json",r=>r.fulfill(json({
    mode:"historical-only",evaluatedSeasons:34,heldOutGames:2000,
    models:{elo:{games:2000,brier:.21}},nestedChampion:{games:2000,brier:.208},
    priorYearStack:{games:2000,brier:.209},priorYearStackGainVsElo:.001,
    priorYearStackGain95:[-.006,.009],yearByYear:[],
  })));
  await page.route("**/current/accuracy-research.json",r=>r.fulfill(json({
    immutableFirstPicks:65,verifiedUniqueFinals:60,
    overall:{games:60,brier:.21,accuracy:.683333},
    calibrationDiagnostics:{status:"observing",games:60,
      expectedCalibrationError:.05,bins:[
       {confidenceRange:"50-60%",games:14,meanPredicted:.55,realizedCorrect:.58},
       {confidenceRange:"60-70%",games:13,meanPredicted:.65,realizedCorrect:.64},
       {confidenceRange:"70-80%",games:12,meanPredicted:.75,realizedCorrect:.72},
       {confidenceRange:"80-90%",games:12,meanPredicted:.85,realizedCorrect:.83},
       {confidenceRange:"90-100%",games:9,meanPredicted:.93,realizedCorrect:.89}]},
    byRatingVersion:[{version:"source-aware-game-elo-v1",games:30,
      brier:.205,accuracy:.7,latestGameDate:"2026-11-17"}],
  })));
  await page.goto("/?view=models");
  const workbench=page.locator(".fi-workbench");
  await expect(workbench).toBeVisible();
  await expect(page.locator(".fi-signal")).toHaveCount(4);
  await expect(page.locator(".fi")).toContainText("BETTER SIGNALS.");
  await expect(page.locator(".fi")).toContainText("60");
  await expect(workbench).toContainText("Efficiency learner");
  await expect(workbench).toContainText("+0.0060");
  await page.getByRole("button",{name:"Adaptive ensemble"}).click();
  await expect(workbench).toContainText("Adaptive research mix");
  await expect(workbench).toContainText("56");
  await page.getByRole("button",{name:"Historical stack"}).click();
  await expect(workbench).toContainText("Historical stack");
  await expect(workbench).toContainText("2,000");
  await expect(page.locator(".fi-calibration-row")).toHaveCount(5);
  await expect(page.locator(".fi-monitor")).toContainText("0.0500");
  const widths=await page.evaluate(()=>({
    outer:document.documentElement.scrollWidth,viewport:document.documentElement.clientWidth,
  }));
  expect(widths.outer,"new workbench causes horizontal overflow").toBeLessThanOrEqual(widths.viewport+3);
});


test("v2.4 ESPN finals update even while NCAA Elo lags, including a manual refresh",async ({page})=>{
  // Browser fixtures are hermetic; no assertion here depends on a live game.
  const captured="2026-11-20T02:20:00Z";
  const json=(value:unknown)=>({contentType:"application/json",body:JSON.stringify(value)});
  const team=(teamId:string,name:string)=>({
    rank:1,teamId,name,rating:1510,projectedRating:1510,trend:0,
    wins:3,losses:1,history:[1500,1510],recentGames:[],ratingHistory:[1500,1510],
  });
  await page.route("**/current/2027.json",r=>r.fulfill(json({
    mode:"current",season:2027,retrievedAtUtc:captured,
    lastGameDate:"2026-11-19",
    sourceReconciliation:{mode:"daily-multi-source-Elo",ncaaAcceptedGames:953,
      ratedEspnOnlyFinals:1,totalRatedGames:954,
      ncaaLastGameDate:"2026-11-18",espnOnlyLastGameDate:"2026-11-19",
      espnFinalsObservedThisRun:2,persistedEspnFinalReceipts:1,
      rejectedOrReconciled:{}},
    teams:[team("ncaa-h","Home U"),team("ncaa-a","Away U")],
  })));
  await page.route("**/current/upcoming.json",r=>r.fulfill(json({
    schemaVersion:1,generatedAtUtc:captured,ratingRetrievedAtUtc:captured,
    lastIncludedGameDate:"2026-11-18",
    coverage:{futureScheduled:0,eligibleForecasts:0,unmatchedOrAmbiguous:0},
    games:[],
  })));
  const makeFinal=(id:string,awayScore:number)=>({
    eventId:id,date:"2026-11-19",scheduledStartUtc:"2026-11-20T00:15:00Z",
    home:"Home U",away:"Away U",homeScore:85,awayScore,
    winner:"Home U",status:"ESPN-final",ncaaRatingInputConfirmed:false,
    eloRatingInputConfirmed:id==="401-first",
    ncaaIdentityMatchConfirmed:true,
  });
  let requests=0;
  await page.route("**/current/recent-finals.json",r=>{
    requests++;
    const finals=[makeFinal("401-first",72),...(requests>1?[makeFinal("401-next",71)]:[])];
    return r.fulfill(json({
      schemaVersion:1,season:2027,type:"ESPN-recent-final-scoreboard",
      status:"source-ready",ratingRetrievedAtUtc:captured,generatedAtUtc:captured,
      ncaaResultsThroughDate:"2026-11-18",
      mostRecentEspnFinalDate:"2026-11-19",
      confirmedFinalCount:finals.length,ncaaRatingInputMatched:0,
      boardDaysRetrieved:4,lookbackDays:4,sourceWarnings:[],games:finals,
    }));
  });
  await page.goto("/?view=games");
  await expect(page.locator('main[data-hydrated="yes"]')).toBeVisible();
  const finals=page.getByRole("region",{name:"Recent ESPN-confirmed basketball final scores"});
  await expect(finals).toBeVisible();
  await expect(finals).toContainText("ESPN ID-VERIFIED FINAL · INCLUDED IN ELO (NCAA PENDING)");
  await expect(finals).toContainText("ESPN results are ahead of the NCAA score file");
  await expect(finals).toContainText("1 ESPN-only game(s) currently in Elo");
  await expect(finals.locator(".gc-final-card")).toHaveCount(1);
  await expect(finals).toContainText("85");
  await expect(finals).toContainText("72");
  await finals.getByRole("button",{name:/CHECK FOR UPDATES/}).click();
  await expect(finals.locator(".gc-final-card")).toHaveCount(2);
  await expect(finals).toContainText("ID / SOURCE VERIFICATION PENDING, NOT IN ELO");
  const width=await page.evaluate(()=>({
    actual:document.documentElement.scrollWidth,
    viewport:document.documentElement.clientWidth,
  }));
  expect(width.actual,"daily finals layout exceeds viewport").toBeLessThanOrEqual(width.viewport+3);
});


test("weekly AP poll study shows frozen 2027 poll, weekly trend, precise missing schools and disagreement filter",async ({page})=>{
  const json=(value:unknown)=>({contentType:"application/json",body:JSON.stringify(value)});
  const makeWeek=(day:string,common:number)=>{
    const teams=Array.from({length:25},(_,i)=>({
      apRank:i+1,apName:"Basketball School "+(i+1),espnTeamId:String(100+i),
      eloRank:i<common?i+1:(i+1===25?null:i+40),
      elo:i<common?1670-i*3:(i+1===25?null:1510-i),
      eloTeamName:i+1===25?null:"Basketball School "+(i+1),
      eloGames:i+1===25?null:7,
      rankGap:i<common?0:(i+1===25?null:39),
      eloTop25:i<common,
    }));
    return {pollKey:"AP-2027-"+day,sourceWeekStart:day,
      sourceWeekNumber:day==="2026-11-16"?3:2,
      capturedAtUtc:day+"T23:30:00Z",
      eloGameCutoffDate:day==="2026-11-16"?"2026-11-15":"2026-11-08",
      eloModelVersion:"source-aware-game-elo-v2-espn-final",
      status:"ready",matchedApTeams:24,missingApTeams:1,
      top25Overlap:common,top10Overlap:10,
      meanAbsoluteRankGap:day==="2026-11-16"?4.2:6.4,
      spearmanWithinMatched:.71,divisionIRatedProgramsAtCutoff:300,
      ncaaPlusEspnRatedGamesThroughCutoff:950,teams,
      eloTop25:Array.from({length:25},(_,i)=>({
        eloRank:i+1,team:i<common?"Basketball School "+(i+1):"Different School "+i,
        espnTeamId:String(i<common?100+i:800+i),elo:1680-i*4,
      })),
    };
  };
  await page.route("**/research/ap-poll-history.json",r=>r.fulfill(json({
    schemaVersion:1,season:2027,mode:"weekly-AP-vs-Elo-independent-research",
    pollSourceUrl:"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/rankings?groups=50",
    sourceLandingUrl:"https://www.espn.com/mens-college-basketball/rankings",
    weeks:[makeWeek("2026-11-09",18),makeWeek("2026-11-16",21)],
  })));
  await page.goto("/?view=models");
  const panel=page.getByRole("region",{name:"Weekly AP Top 25 versus Elo rankings"});
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("THE POLL");
  await expect(panel).toContainText("21/25");
  await expect(panel.locator(".ap-lab-table tbody tr")).toHaveCount(25);
  await expect(panel).toContainText("NO PRE-WEEK ELO MATCH");
  await panel.getByLabel("Select AP poll comparison week").selectOption("AP-2027-2026-11-09");
  await expect(panel).toContainText("18/25");
  await panel.getByText("BIG GAPS ONLY").click();
  await expect(panel.locator(".ap-lab-table tbody tr")).toHaveCount(7);
  const size=await page.evaluate(()=>({width:document.documentElement.scrollWidth,
    viewport:document.documentElement.clientWidth}));
  expect(size.width,"AP study introduces viewport overflow").toBeLessThanOrEqual(size.viewport+3);
});

test("weekly AP study fails gracefully when no source poll has been captured yet",async ({page})=>{
  await page.route("**/research/ap-poll-history.json",r=>r.fulfill({
    contentType:"application/json",
    body:JSON.stringify({schemaVersion:1,season:2027,
      mode:"weekly-AP-vs-Elo-independent-research",weeks:[]}),
  }));
  await page.goto("/?view=models");
  const panel=page.getByRole("region",{name:"Weekly AP Top 25 versus Elo rankings"});
  await expect(panel).toContainText("First weekly comparison pending");
  await expect(panel.locator(".ap-lab-table tbody tr")).toHaveCount(0);
});


test("v2.7 Elo2 displays source-aligned three-way ranks and honest held-out evidence",async ({page})=>{
  const json=(d:unknown)=>({contentType:"application/json",body:JSON.stringify(d)});
  const sourceAt="2026-11-23T14:30:00Z";
  const entries=Array.from({length:28},(_,i)=>({
    name:"School "+(i+1),teamId:"ncaa-"+i,espnTeamId:String(800+i),
    elo2:1570-i*2,elo2Rank:i+1,baselineElo:1540-i,
    baselineRank:28-i,rankChangeFromBaseline:27-2*i,
    offseasonPrior:i%2?1500:1550,hasHistoricalMatch:i%2===0,
    opponentScheduleBonus:3.1,games:6,
  }));
  const scores=(gain:number)=>({
    games:800,baselineBrier:.232,challengerBrier:.232-gain,
    brierGain:gain,baselineAccuracy:.57,challengerAccuracy:.59,
    baselineECE:.087,challengerECE:.07,
    baselineLogLoss:.665,challengerLogLoss:.64,
  });
  const bySeason=[2019,2020,2021,2022,2023,2024,2025].map(season=>({
    season,games:900,priorSeason:season-1,priorMatchedTeams:340,
    variants:{carryover:scores(.004),scheduleOnly:scores(-.001),carryoverAndSchedule:scores(.006)},
  }));
  await page.route("**/research/elo-v2-historical.json",r=>r.fulfill(json({
    schemaVersion:1,type:"elo-v2-historical-year-holdout",status:"ready",
    holdoutSeasons:7,firstHeldOutYear:2019,lastHeldOutYear:2025,
    variants:{
      carryover:{...scores(.004),earlySeason:scores(.008),
        seasonBlockBrierGain95:[-.002,.011],positiveGainSeasons:5},
      scheduleOnly:{...scores(-.001),earlySeason:scores(0),
        seasonBlockBrierGain95:[-.01,.008],positiveGainSeasons:3},
      carryoverAndSchedule:{...scores(.006),earlySeason:scores(.01),
        seasonBlockBrierGain95:[.001,.012],positiveGainSeasons:6},
    },
    bySeason,
  })));
  await page.route("**/current/elo-v2-research.json",r=>r.fulfill(json({
    schemaVersion:1,type:"current-elo2-research",season:2027,status:"research-only",
    ratingRetrievedAtUtc:sourceAt,sourceGameDate:"2026-11-22",sourceGames:1250,
    historicalBenchmarkStatus:"ready",historicalHoldoutSeasons:7,
    modelPromotionAllowed:false,
    promotionReason:"2026 prior is incomplete; exact name matching is research only.",
    priorCoverage:{matchedTeamNames:28,unmatchedTeamNames:0,
      snapshotSeason:2026,snapshotThroughKaggleDay:118,
      identityWarning:"Names alone do not verify team identity."},
    currentRetrospective:{carryover:scores(.004),scheduleOnly:scores(-.001),carryoverAndSchedule:scores(.006)},
    teams:entries,
    apComparisons:[{
      pollKey:"AP-2027-2026-11-16",sourceWeekStart:"2026-11-16",
      eloGameCutoffDate:"2026-11-15",status:"retrospective-comparable",
      apMatchedElo2:25,baselineTop25OverlapFrozen:7,elo2Top25Overlap:12,
      baselineTop10OverlapFrozen:1,elo2Top10Overlap:5,
      teams:entries.slice(0,25).map((t,i)=>({apRank:i+1,
        apTeam:t.name,baselineEloRankFrozen:t.baselineRank,
        elo2Rank:t.elo2Rank,elo2:t.elo2,rankGap:i-1})),
      warning:"Retrospectively reconstructed today. Original week is frozen.",
    }],
  })));
  await page.route("**/current/2027.json",r=>r.fulfill(json({
    mode:"current",season:2027,retrievedAtUtc:sourceAt,
    lastGameDate:"2026-11-22",teams:entries.map(t=>({
      teamId:t.teamId,name:t.name,rating:t.baselineElo,
      rank:t.baselineRank,wins:3,losses:3,
    })),
  })));
  await page.goto("/?view=models");
  const studio=page.getByRole("region",{name:"Original Elo versus Elo 2.0 research comparison"});
  await expect(studio).toBeVisible();
  await expect(studio).toContainText("ACTIVE PREDICTOR");
  await expect(studio).toContainText("UNCHANGED");
  await expect(studio.locator(".ev2-table tbody tr")).toHaveCount(25);
  await studio.getByRole("button",{name:"Biggest movers"}).click();
  await expect(studio.locator(".ev2-table tbody tr")).toHaveCount(28);
  await studio.getByRole("button",{name:"HISTORICAL TESTS"}).click();
  await expect(studio).toContainText("Season-block descriptive 95%");
  await expect(studio).toContainText("calibration ECE");
  await studio.getByLabel("Choose Elo 2.0 historical variant").selectOption("scheduleOnly");
  await expect(studio).toContainText("Schedule-adjusted");
  await studio.getByRole("button",{name:"ELO 2.0 vs AP"}).click();
  await expect(studio).toContainText("12");
  await expect(studio).toContainText("Retrospectively reconstructed today");
  await expect(studio.locator(".ev2-table tbody tr")).toHaveCount(25);
  const size=await page.evaluate(()=>({
    actual:document.documentElement.scrollWidth,
    viewport:document.documentElement.clientWidth,
  }));
  expect(size.actual,"Elo2 source-comparison leaked horizontal overflow").toBeLessThanOrEqual(size.viewport+3);
});

test("v2.7 Elo2 refuses mismatched research timestamps instead of misleading ratings",async ({page})=>{
  const json=(d:unknown)=>({contentType:"application/json",body:JSON.stringify(d)});
  await page.route("**/research/elo-v2-historical.json",r=>r.fulfill(json({
    schemaVersion:1,type:"elo-v2-historical-year-holdout",
    status:"unavailable",holdoutSeasons:0,variants:{},bySeason:[],
  })));
  await page.route("**/current/elo-v2-research.json",r=>r.fulfill(json({
    schemaVersion:1,type:"current-elo2-research",season:2027,
    status:"research-only",ratingRetrievedAtUtc:"2026-11-21T02:00:00Z",
    teams:[],apComparisons:[],
  })));
  await page.route("**/current/2027.json",r=>r.fulfill(json({
    retrievedAtUtc:"2026-11-23T14:00:00Z",season:2027,mode:"current",teams:[],
  })));
  await page.goto("/?view=models");
  const studio=page.getByRole("region",{name:"Original Elo versus Elo 2.0 research comparison"});
  await expect(studio).toContainText("different retrieval timestamps");
  await expect(studio.locator(".ev2-table tbody tr")).toHaveCount(0);
});

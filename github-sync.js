/* GitHub-only synchronizace. Token je uložen pouze v tomto prohlížeči. */
window.GitHubSync=(()=>{
'use strict';
const owner='jerry00769',repo='jidelnicky',file='spolecna_data.json';
const tokenKey='jidelnicky_github_token_v1',pendingKey='jidelnicky_github_pending_v3',baselineKey='jidelnicky_github_baseline_v3';
let token=localStorage.getItem(tokenKey)||'',sha=null,baseline=null,app=null,busy=false,dirty=localStorage.getItem(pendingKey)==='1',timer=null,connected=false,conflicted=false;
const $=id=>document.getElementById(id);
const json=x=>JSON.stringify(x);
const status=(msg,err=false)=>{
 const b=$('githubIndicator');
 if(b){
  const message=String(msg).replace(/^GitHub:\s*/i,'');
  const pending=/čeká|načítám|odesíl|změny uloženy místně|kontrol|připojov/i.test(message);
  const failed=err||/nepřipojeno|odpojeno|konflikt|chybí|chyba|nelze|rozdílné|nevyřešen/i.test(message);
  const kind=failed?'error':pending?'info':'ok';
  b.textContent=(kind==='ok'?'✓ ':kind==='error'?'⚠ ':'↻ ')+message;
  b.classList.toggle('synced',kind==='ok');
  b.classList.toggle('local-change',kind==='info');
  b.classList.toggle('error',kind==='error');
  b.title='GitHub: '+message;
 }
 if(err)app?.notice(msg,true);
};
function markPending(v){dirty=v;if(v)localStorage.setItem(pendingKey,'1');else localStorage.removeItem(pendingKey)}
function setBaseline(s){baseline=json(s);localStorage.setItem(baselineKey,baseline)}
function backup(s){const blob=new Blob([JSON.stringify(s,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='jidelnicky_zaloha_konflikt_'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
function controls(){ $('ghConnect').hidden=connected||conflicted;$('ghRefresh').hidden=!connected;$('ghDisconnect').hidden=!connected;const resolve=$('ghResolve');if(resolve)resolve.hidden=!conflicted }
const endpoint=`https://api.github.com/repos/${owner}/${repo}/contents/${file}`;
async function request(method,body){const r=await fetch(endpoint+(method==='GET'?'?t='+Date.now():''),{method,headers:{'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'X-GitHub-Api-Version':'2022-11-28',...(body?{'Content-Type':'application/json'}:{})},cache:'no-store',body:body?JSON.stringify(body):undefined});if(r.status===404&&method==='GET'&&!token)return null;let data;try{data=await r.json()}catch{data={}}if(!r.ok){const e=new Error(`GitHub ${r.status}: ${data.message||'chyba přístupu'}`);e.status=r.status;throw e}return data}
function decode(s){const bin=atob(s.replace(/\s/g,''));return new TextDecoder().decode(Uint8Array.from(bin,c=>c.charCodeAt(0)))}
function encode(s){const bytes=new TextEncoder().encode(s);let bin='';for(let i=0;i<bytes.length;i+=8192)bin+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(bin)}
function valid(s){return !!(s?.catalog?.main&&s?.catalog?.soup&&Array.isArray(s?.history)&&s?.week?.days?.length===5)}
async function remote(){const item=await request('GET');if(!item)return null;if(item.type!=='file'||!item.content)throw Error('GitHub nevrátil obsah souboru.');const obj=JSON.parse(decode(item.content));if(obj.format!=='jidelnicky-shared-v1'||!valid(obj.state))throw Error('Společný soubor nemá správný formát.');return {sha:item.sha,state:obj.state}}
async function put(s,expected){const content=encode(JSON.stringify({format:'jidelnicky-shared-v1',state:s},null,2));return request('PUT',{message:'Jídelníčky: synchronizace společných dat',content,...(expected?{sha:expected}:{})})}
async function connect(){
 if(busy)return;busy=true;status('GitHub: čeká na synchronizaci…');
 try{
  const r=await remote();
  if(!r){
   if(dirty){conflicted=true;controls();status('GitHub: soubor chybí, místní změny zachovány.',true);return}
   if(!confirm('Společná databáze neexistuje. Vytvořit ji z tohoto zařízení? Doporučujeme nejprve Export JSON.')){status('GitHub: nepřipojeno');return}
   const local=app.getState(),serial=json(local),saved=await put(local,null);
   sha=saved.content.sha;setBaseline(local);markPending(json(app.getState())!==serial);connected=true;conflicted=false;controls();status('GitHub: společná data vytvořena');return;
  }
  const local=app.getState(),localJson=json(local),remoteJson=json(r.state),storedBaseline=localStorage.getItem(baselineKey);
   // Stejný obsah není konflikt ani při starém příznaku dirty či novém SHA.
   if(localJson===remoteJson){sha=r.sha;setBaseline(r.state);markPending(false);connected=true;conflicted=false;controls();status('GitHub: data synchronizována');return;}
   // Pokud se lokálně nic fakticky nezměnilo, starý dirty příznak lze zrušit.
   if(dirty&&storedBaseline===localJson)markPending(false);
  // Bezpečné obnovení offline zápisu: server se od poslední synchronizace nezměnil.
  if(dirty&&storedBaseline===remoteJson){
   sha=r.sha;baseline=storedBaseline;connected=true;conflicted=false;controls();
   status('GitHub: čeká na synchronizaci offline změn…');
   setTimeout(flush,0);return;
  }
   // Offline změny a vzdálená změna: nejprve bezpečný pokus o sloučení.
   if(dirty&&storedBaseline&&storedBaseline!==remoteJson){
    const original=localJson;
    if(await mergeAndPut(local,original,r.state,r.sha))return;
   }
   // Nové zařízení: uživatel musí potvrdit první převzetí vzdálených dat.
  // Při neodeslaných úpravách se nikdy nepřepisuje automaticky.
  if(localJson!==remoteJson){
   if(dirty||storedBaseline&&localJson!==storedBaseline){
    conflicted=true;controls();status('GitHub: rozdílné změny! Místní data zachována.',true);
    if(confirm('Na zařízení jsou místní změny odlišné od GitHubu.\n\nOK = stáhnout zálohu místních dat (doporučeno).\nZrušit = zatím nic neměnit.'))backup(local);
    return;
   }
   // Běžné znovupřipojení čistého zařízení proběhne bez dialogu.
   // Při úplně prvním připojení (bez známé výchozí verze) zůstává jednorázová ochrana dat.
   if(!storedBaseline&&!confirm('První připojení: převzít společná data z GitHubu?\n\nMístní data tohoto zařízení se nahradí. Předem lze použít Export JSON.')){status('GitHub: čeká na první potvrzení připojení');return}
   status('GitHub: načítám změny z druhého zařízení…');
   if(json(app.getState())!==localJson||dirty){markPending(true);conflicted=true;controls();status('GitHub: místní změny během načítání zachovány.',true);return}
   app.applyState(r.state);
  }
  sha=r.sha;setBaseline(app.getState());markPending(false);connected=true;conflicted=false;controls();status('GitHub: data synchronizována');
 }catch(e){connected=false;controls();status('GitHub: '+e.message,true)}finally{busy=false}
}
async function resolveConflict(){
 if(busy||!conflicted)return;
 if(!confirm('Na tomto zařízení jsou neodeslané změny.\n\nPřevzít data z GitHubu? Před nahrazením místních dat se automaticky stáhne jejich záloha JSON.\n\nZrušit = ponechat místní data beze změny.'))return;
 backup(app.getState());
 busy=true;
 try{
  const r=await remote();if(!r)throw Error('Na GitHubu chybí společná data.');
  app.applyState(r.state);sha=r.sha;setBaseline(app.getState());markPending(false);conflicted=false;connected=true;controls();status('GitHub: konflikt vyřešen převzetím serverových dat');
 }catch(e){status('GitHub: konflikt nevyřešen ('+e.message+')',true)}finally{busy=false}
}
// Konzervativní třícestné sloučení: jen přidání jídel do existujících kategorií.
// Ostatní změny (mazání, přejmenování, historie, pravidla, návrh týdne) vyžadují rozhodnutí.
function mergeIndependentAdds(base,local,server){
 if(!base||!valid(base)||!valid(local)||!valid(server))return null;
 const withoutCatalog=x=>{const y=structuredClone(x);delete y.catalog;return JSON.stringify(y)};
 const common=withoutCatalog(base);
 if(withoutCatalog(local)!==common||withoutCatalog(server)!==common)return null;
 const merged=structuredClone(server);
 for(const kind of ['main','soup']){
  const baseCats=base.catalog[kind],localCats=local.catalog[kind],serverCats=server.catalog[kind];
  if(!baseCats||!localCats||!serverCats)return null;
  const keys=Object.keys(baseCats).sort();
  if(JSON.stringify(Object.keys(localCats).sort())!==JSON.stringify(keys)||JSON.stringify(Object.keys(serverCats).sort())!==JSON.stringify(keys))return null;
  for(const cat of keys){
   const old=baseCats[cat],mine=localCats[cat],theirs=serverCats[cat];
   if(![old,mine,theirs].every(Array.isArray))return null;
   const original=new Set(old);
   if(original.size!==old.length||old.some(x=>!mine.includes(x)||!theirs.includes(x)))return null;
   if(new Set(mine).size!==mine.length||new Set(theirs).size!==theirs.length)return null;
   const additions=mine.filter(x=>!original.has(x));
   const result=[...theirs];
   for(const name of additions){
    if(result.some(x=>x.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()===name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase())){
     if(!result.includes(name))return null;
    }else result.push(name);
   }
   merged.catalog[kind][cat]=result.sort((a,b)=>a.localeCompare(b,'cs'));
  }
 }
 return merged;
}
async function mergeAndPut(local,serial,remoteState,remoteSha){
 let original;try{original=JSON.parse(localStorage.getItem(baselineKey)||'null')}catch{return false}
 const merged=mergeIndependentAdds(original,local,remoteState);
 if(!merged)return false;
 // Když mezitím uživatel provedl další změnu, neodesílat starý stav.
 if(json(app.getState())!==serial)return false;
 const saved=await put(merged,remoteSha);
 if(json(app.getState())!==serial){conflicted=true;connected=false;controls();status('GitHub: během sloučení vznikly další změny. Místní data zachována.',true);return true}
 app.applyState(merged);sha=saved.content.sha;setBaseline(app.getState());markPending(false);
 conflicted=false;connected=true;controls();status('GitHub: nezávislá přidání jídel bezpečně sloučena');
 return true;
}
async function flush(){
 if(!connected||busy||!dirty||conflicted)return;
 busy=true;
 try{
  const current=app.getState(),serial=json(current);
  if(serial===baseline){if(json(app.getState())===serial){markPending(false);status('GitHub: data synchronizována')}else{markPending(true);status('GitHub: další místní změny čekají na odeslání…')}return}
  const r=await remote();
  if(r&&json(r.state)===serial){sha=r.sha;setBaseline(r.state);if(json(app.getState())===serial){markPending(false);status('GitHub: data synchronizována')}return;}
  if(r&&json(r.state)===baseline){sha=r.sha;}
  if(!r||r.sha!==sha){
   if(r&&await mergeAndPut(current,serial,r.state,r.sha))return;
   conflicted=true;connected=false;controls();status('GitHub: konflikt úprav – je potřeba rozhodnout v Nastavení. Místní data zachována.',true);return;
  }
  if(json(app.getState())!==serial){markPending(true);status('GitHub: další místní změny čekají na odeslání');return}
  const saved=await put(current,sha);
  sha=saved.content.sha;setBaseline(current);
  if(json(app.getState())===serial){markPending(false);status('GitHub: data synchronizována')}
  else{markPending(true);status('GitHub: čeká na synchronizaci dalších změn…');clearTimeout(timer);timer=setTimeout(flush,1200)}
 }catch(e){
  if(e.status===409||e.status===422){conflicted=true;connected=false;controls();status('GitHub: konflikt souběžných změn! Místní data zachována.',true)}
  else status('GitHub: offline nebo chyba zápisu. Změny zůstaly v zařízení a čekají na odeslání.',true)
 }finally{busy=false;if(connected&&dirty&&!conflicted){clearTimeout(timer);timer=setTimeout(flush,1200)}}
}
function changed(){
 // I při offline práci a při ztrátě připojení evidujeme neodeslané změny.
 markPending(true);
 if(!token)return;
 if(!connected){status('GitHub: změny uloženy místně, čekají na připojení',true);return}
 status('GitHub: čeká na synchronizaci změn…');clearTimeout(timer);timer=setTimeout(flush,1200)
}
async function refresh(){
 if(!connected||busy||conflicted)return;
 if(dirty){await flush();if(dirty||!connected)return}
 busy=true;
 try{
  const r=await remote();if(!r)throw Error('Společná data chybí.');
  if(r.sha!==sha){
   const local=app.getState();
   if(json(local)===json(r.state)){sha=r.sha;setBaseline(r.state);markPending(false);status('GitHub: data synchronizována');return;}
   if(dirty||json(local)!==baseline){
    markPending(true);conflicted=true;connected=false;controls();status('GitHub: konflikt místních změn. Data nebyla přepsána.',true);return;
   }
   // Před aplikací dat ověřujeme, že stav se od začátku kontroly nezměnil.
   if(dirty||json(app.getState())!==json(local)){markPending(true);conflicted=true;connected=false;controls();status('GitHub: během načítání vznikly místní změny. Data zachována.',true);return}
   app.applyState(r.state);sha=r.sha;setBaseline(r.state);status('GitHub: data synchronizována');
  }else if(json(app.getState())!==baseline){markPending(true);status('GitHub: místní změny čekají na odeslání…');clearTimeout(timer);timer=setTimeout(flush,1200)}
  else status('GitHub: data synchronizována');
 }catch(e){status('GitHub: nelze zkontrolovat spojení; místní data zachována ('+e.message+')',true)}
 finally{busy=false}
}
function disconnect(){
 if(dirty&&!confirm('Na zařízení jsou neodeslané změny. Před odpojením si stáhni Export JSON. Opravdu odpojit?'))return;
 connected=false;conflicted=false;sha=null;baseline=null;token='';localStorage.removeItem(tokenKey);controls();status('GitHub: odpojeno. Místní data zůstala zachována')
}
function start(a){
 app=a;
 $('ghConnect').onclick=()=>{
  if(!token){const t=prompt('Vlož GitHub fine-grained token pro repozitář jerry00769/jidelnicky.\nToken nikomu neposílej.');if(!t)return;token=t.trim();localStorage.setItem(tokenKey,token)}
  connect()
 };
 $('ghRefresh').onclick=refresh;$('ghDisconnect').onclick=disconnect;const resolver=$('ghResolve');if(resolver)resolver.onclick=resolveConflict;
 controls();const initialSync=token?connect():Promise.resolve();
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&connected){if(dirty)flush();else refresh()}});
 window.addEventListener('online',()=>{if(connected){if(dirty)flush();else refresh()}else if(token&&!busy&&!conflicted)connect()});
 // Automatická kontrola při otevřené stránce; vyhneme se zbytečným API voláním na pozadí.
 setInterval(()=>{if(connected&&!document.hidden&&!busy){if(dirty)flush();else refresh()}},15000);
 window.addEventListener('focus',()=>{if(connected&&!busy){if(dirty)flush();else refresh()}});
 return initialSync;
}
return {start,changed};
})();

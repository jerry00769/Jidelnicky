/* GitHub-only synchronizace. Token je uložen pouze v tomto prohlížeči. */
window.GitHubSync=(()=>{
'use strict';
const owner='jerry00769',repo='jidelnicky',file='spolecna_data.json';
const tokenKey='jidelnicky_github_token_v1',pendingKey='jidelnicky_github_pending_v3',baselineKey='jidelnicky_github_baseline_v3';
let token=localStorage.getItem(tokenKey)||'',sha=null,baseline=null,app=null,busy=false,dirty=localStorage.getItem(pendingKey)==='1',timer=null,connected=false,conflicted=false;
const $=id=>document.getElementById(id);
const json=x=>JSON.stringify(x);
const status=(msg,err=false)=>{const b=$('savedBadge');if(b)b.textContent=msg; if(err)app?.notice(msg,true)};
function markPending(v){dirty=v;if(v)localStorage.setItem(pendingKey,'1');else localStorage.removeItem(pendingKey)}
function setBaseline(s){baseline=json(s);localStorage.setItem(baselineKey,baseline)}
function backup(s){const blob=new Blob([JSON.stringify(s,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='jidelnicky_zaloha_konflikt_'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
function controls(){ $('ghConnect').hidden=connected;$('ghRefresh').hidden=!connected;$('ghDisconnect').hidden=!connected;const resolve=$('ghResolve');if(resolve)resolve.hidden=!conflicted }
const endpoint=`https://api.github.com/repos/${owner}/${repo}/contents/${file}`;
async function request(method,body){const r=await fetch(endpoint+(method==='GET'?'?t='+Date.now():''),{method,headers:{'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'X-GitHub-Api-Version':'2022-11-28',...(body?{'Content-Type':'application/json'}:{})},cache:'no-store',body:body?JSON.stringify(body):undefined});if(r.status===404&&method==='GET')return null;let data;try{data=await r.json()}catch{data={}}if(!r.ok){const e=new Error(`GitHub ${r.status}: ${data.message||'chyba přístupu'}`);e.status=r.status;throw e}return data}
function decode(s){const bin=atob(s.replace(/\s/g,''));return new TextDecoder().decode(Uint8Array.from(bin,c=>c.charCodeAt(0)))}
function encode(s){const bytes=new TextEncoder().encode(s);let bin='';for(let i=0;i<bytes.length;i+=8192)bin+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(bin)}
function valid(s){return !!(s?.catalog?.main&&s?.catalog?.soup&&Array.isArray(s?.history)&&s?.week?.days?.length===5)}
async function remote(){const item=await request('GET');if(!item)return null;if(item.type!=='file'||!item.content)throw Error('GitHub nevrátil obsah souboru.');const obj=JSON.parse(decode(item.content));if(obj.format!=='jidelnicky-shared-v1'||!valid(obj.state))throw Error('Společný soubor nemá správný formát.');return {sha:item.sha,state:obj.state}}
async function put(s,expected){const content=encode(JSON.stringify({format:'jidelnicky-shared-v1',state:s},null,2));return request('PUT',{message:'Jídelníčky: synchronizace společných dat',content,...(expected?{sha:expected}:{})})}
async function connect(){
 if(busy)return;busy=true;status('GitHub: připojuji…');
 try{
  const r=await remote();
  if(!r){
   if(!confirm('Společná databáze neexistuje. Vytvořit ji z tohoto zařízení? Doporučujeme nejprve Export JSON.')){status('GitHub: nepřipojeno');return}
   const local=app.getState(),saved=await put(local,null);
   sha=saved.content.sha;setBaseline(local);markPending(false);connected=true;conflicted=false;controls();status('GitHub: společná data vytvořena');return;
  }
  const local=app.getState(),localJson=json(local),remoteJson=json(r.state),storedBaseline=localStorage.getItem(baselineKey);
  // Bezpečné obnovení offline zápisu: server se od poslední synchronizace nezměnil.
  if(dirty&&storedBaseline===remoteJson){
   sha=r.sha;baseline=storedBaseline;connected=true;conflicted=false;controls();
   status('GitHub: odesílám změny uložené offline…');
   setTimeout(flush,0);return;
  }
  // Nové zařízení: uživatel musí potvrdit první převzetí vzdálených dat.
  // Při neodeslaných úpravách se nikdy nepřepisuje automaticky.
  if(localJson!==remoteJson){
   if(dirty||storedBaseline&&localJson!==storedBaseline){
    conflicted=true;controls();status('GitHub: rozdílné změny! Místní data zachována.',true);
    if(confirm('Na zařízení jsou místní změny odlišné od GitHubu.\n\nOK = stáhnout zálohu místních dat (doporučeno).\nZrušit = zatím nic neměnit.'))backup(local);
    return;
   }
   if(!confirm('Na GitHubu jsou společná data.\n\nOK = převzít společná data do tohoto zařízení.\nZrušit = ponechat místní data beze změny.\n\nPřed převzetím doporučujeme Export JSON.')){status('GitHub: místní data zachována, nepřipojeno');return}
   app.applyState(r.state);
  }
  sha=r.sha;setBaseline(app.getState());markPending(false);connected=true;conflicted=false;controls();status('GitHub: synchronizováno');
 }catch(e){connected=false;controls();status('GitHub: '+e.message,true)}finally{busy=false}
}
async function resolveConflict(){
 if(busy||!conflicted)return;
 if(!confirm('Konflikt GitHubu. Nejprve se automaticky stáhne záloha aktuálních místních dat.\n\nOK = stáhnout zálohu a pokračovat k potvrzení načtení serverových dat.\nZrušit = ponechat vše beze změny.'))return;
 backup(app.getState());
 if(!confirm('Záloha místních dat byla nabídnuta ke stažení.\n\nOpravdu nyní převzít data z GitHubu? Neodeslané místní změny se nahradí serverovými.\nZrušit = místní data zachovat.'))return;
 busy=true;
 try{
  const r=await remote();if(!r)throw Error('Na GitHubu chybí společná data.');
  app.applyState(r.state);sha=r.sha;setBaseline(app.getState());markPending(false);conflicted=false;connected=true;controls();status('GitHub: konflikt vyřešen převzetím serverových dat');
 }catch(e){status('GitHub: konflikt nevyřešen ('+e.message+')',true)}finally{busy=false}
}
async function flush(){
 if(!connected||busy||!dirty||conflicted)return;
 busy=true;
 try{
  const current=app.getState(),serial=json(current);
  if(serial===baseline){markPending(false);status('GitHub: synchronizováno');return}
  const r=await remote();
  if(!r||r.sha!==sha){
   conflicted=true;connected=false;controls();status('GitHub: konflikt! Místní data zachována. Otevři Nastavení a vytvoř zálohu.',true);return;
  }
  const saved=await put(current,sha);
  sha=saved.content.sha;setBaseline(current);
  if(json(app.getState())===serial){markPending(false);status('GitHub: synchronizováno')}
  else{markPending(true);status('GitHub: odesílám další změny…')}
 }catch(e){
  if(e.status===409||e.status===422){conflicted=true;connected=false;controls();status('GitHub: konflikt souběžných změn! Místní data zachována.',true)}
  else status('GitHub: offline nebo chyba zápisu. Změny zůstaly v zařízení a čekají na odeslání.',true)
 }finally{busy=false;if(connected&&dirty&&!conflicted){clearTimeout(timer);timer=setTimeout(flush,15000)}}
}
function changed(){
 // I při offline práci a při ztrátě připojení evidujeme neodeslané změny.
 if(!token)return;
 markPending(true);
 if(!connected){status('GitHub: změny uloženy místně, čekají na připojení',true);return}
 status('GitHub: ukládám změny…');clearTimeout(timer);timer=setTimeout(flush,1200)
}
async function refresh(){
 if(!connected||busy||conflicted)return;
 if(dirty){await flush();if(dirty||!connected)return}
 busy=true;
 try{
  const r=await remote();if(!r)throw Error('Společná data chybí.');
  if(r.sha!==sha){
   const local=app.getState();
   if(dirty||json(local)!==baseline){
    markPending(true);conflicted=true;connected=false;controls();status('GitHub: konflikt místních změn. Data nebyla přepsána.',true);return;
   }
   // Před aplikací dat ověřujeme, že stav se od začátku kontroly nezměnil.
   app.applyState(r.state);sha=r.sha;setBaseline(r.state);status('GitHub: nové změny načteny');
  }else status('GitHub: synchronizováno');
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
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&connected)refresh()});
 window.addEventListener('online',()=>{if(connected)refresh();else if(token&&!busy&&!conflicted)connect()});
 // Automatická kontrola při otevřené stránce; vyhneme se zbytečným API voláním na pozadí.
 setInterval(()=>{if(connected&&!document.hidden&&!busy)refresh()},15000);
 window.addEventListener('focus',()=>{if(connected&&!busy)refresh()});
 return initialSync;
}
return {start,changed};
})();

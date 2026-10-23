/* GitHub-only synchronizace. Token je uložen pouze v tomto prohlížeči. */
window.GitHubSync=(()=>{
'use strict';
const owner='jerry00769',repo='jidelnicky',file='spolecna_data.json';
const tokenKey='jidelnicky_github_token_v1';
let token=localStorage.getItem(tokenKey)||'',sha=null,baseline=null,app=null,busy=false,dirty=false,timer=null,connected=false;
const $=id=>document.getElementById(id);
const json=x=>JSON.stringify(x);
const status=(msg,err=false)=>{const b=$('savedBadge');if(b)b.textContent=msg; if(err)app?.notice(msg,true)};
function controls(){ $('ghConnect').hidden=connected;$('ghRefresh').hidden=!connected;$('ghDisconnect').hidden=!connected }
const endpoint=`https://api.github.com/repos/${owner}/${repo}/contents/${file}`;
async function request(method,body){const r=await fetch(endpoint+(method==='GET'?'?t='+Date.now():''),{method,headers:{'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'X-GitHub-Api-Version':'2022-11-28',...(body?{'Content-Type':'application/json'}:{})},cache:'no-store',body:body?JSON.stringify(body):undefined});if(r.status===404&&method==='GET')return null;let data;try{data=await r.json()}catch{data={}}if(!r.ok){const e=new Error(`GitHub ${r.status}: ${data.message||'chyba přístupu'}`);e.status=r.status;throw e}return data}
function decode(s){const bin=atob(s.replace(/\s/g,''));return new TextDecoder().decode(Uint8Array.from(bin,c=>c.charCodeAt(0)))}
function encode(s){const bytes=new TextEncoder().encode(s);let bin='';for(let i=0;i<bytes.length;i+=8192)bin+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(bin)}
function valid(s){return !!(s?.catalog?.main&&s?.catalog?.soup&&Array.isArray(s?.history)&&s?.week?.days?.length===5)}
async function remote(){const item=await request('GET');if(!item)return null;if(item.type!=='file'||!item.content)throw Error('GitHub nevrátil obsah souboru.');const obj=JSON.parse(decode(item.content));if(obj.format!=='jidelnicky-shared-v1'||!valid(obj.state))throw Error('Společný soubor nemá správný formát.');return {sha:item.sha,state:obj.state}}
async function put(s,expected){const content=encode(JSON.stringify({format:'jidelnicky-shared-v1',state:s},null,2));return request('PUT',{message:'Jídelníčky: synchronizace společných dat',content,...(expected?{sha:expected}:{})})}
async function connect(){if(busy)return;busy=true;status('GitHub: připojuji…');try{
 const r=await remote();connected=true;controls();
 if(!r){if(!confirm('Na GitHubu zatím není společná databáze. Vytvořit ji z dat tohoto zařízení? Před pokračováním doporučuji Export JSON.')){connected=false;controls();status('GitHub: nepřipojeno');return}const local=app.getState();const result=await put(local,null);sha=result.content.sha;baseline=json(local);dirty=false;status('GitHub: společná data vytvořena');return}
 sha=r.sha;const local=app.getState();
 if(json(local)!==json(r.state)){
  const useRemote=confirm('Na GitHubu už jsou společná data.\n\nOK = načíst společná data z GitHubu (místní stav bude nahrazen).\nZrušit = ponechat místní data, zatím NEZAPISOVAT na GitHub.\n\nPřed nahrazením doporučuji Export JSON.');
  if(!useRemote){connected=false;controls();sha=null;status('GitHub: nepřipojeno, místní data zachována');return}
  app.applyState(r.state)
 }
 baseline=json(app.getState());dirty=false;status('GitHub: synchronizováno');
 }catch(e){connected=false;controls();status('GitHub: '+e.message,true)}finally{busy=false}}
async function flush(){if(!connected||busy||!dirty)return;busy=true;try{
 const current=app.getState(),serial=json(current);
 if(serial===baseline){dirty=false;status('GitHub: synchronizováno');return}
 // Compare-and-swap: pokud někdo zapsal změnu mezitím, nikdy ji nepřepíšeme.
 const r=await remote();if(!r||r.sha!==sha){connected=false;controls();status('GitHub: jiná změna na serveru! Místní data zachována. Exportuj zálohu a znovu připoj.',true);return}
 const saved=await put(current,sha);sha=saved.content.sha;baseline=serial;dirty=json(app.getState())!==serial;status(dirty?'GitHub: čekají další změny':'GitHub: uloženo');
 }catch(e){if(e.status===409||e.status===422){connected=false;controls();status('GitHub: konflikt souběžného zápisu. Místní data zachována. Exportuj zálohu.',true)}else status('GitHub: zápis selhal ('+e.message+'). Místní data zachována.',true)}finally{busy=false;if(connected&&dirty){clearTimeout(timer);timer=setTimeout(flush,5000)}}}
function changed(){if(!connected)return;dirty=true;status('GitHub: ukládám změny…');clearTimeout(timer);timer=setTimeout(flush,1100)}
async function refresh(){if(!connected||busy)return;
 if(dirty){await flush();if(dirty||!connected)return}
 busy=true;
 try{const r=await remote();if(!r)throw Error('Společná data chybí.');
 if(r.sha!==sha){
  if(dirty||json(app.getState())!==baseline){status('GitHub: místní změny čekají, nic nepřepsáno.',true);return}
  app.applyState(r.state);sha=r.sha;baseline=json(r.state);status('GitHub: nové změny načteny');
 }else status('GitHub: synchronizováno');
 }catch(e){status('GitHub: kontrola selhala ('+e.message+'). Místní data zachována.',true)}finally{busy=false}}

function disconnect(){if(dirty&&!confirm('Neodeslané změny zůstanou pouze v tomto prohlížeči. Odpojit?'))return;connected=false;dirty=false;sha=null;baseline=null;token='';localStorage.removeItem(tokenKey);controls();status('GitHub: odpojeno')}
function start(a){app=a;$('ghConnect').onclick=()=>{if(!token){const t=prompt('Vlož GitHub fine-grained token s oprávněním Contents: Read and write pouze pro repozitář jerry00769/jidelnicky.\n\nToken se uloží do tohoto prohlížeče.');if(!t)return;token=t.trim();localStorage.setItem(tokenKey,token)}connect()};$('ghRefresh').onclick=refresh;$('ghDisconnect').onclick=disconnect;controls();if(token)connect();document.addEventListener('visibilitychange',()=>{if(!document.hidden&&connected)refresh()});window.addEventListener('online',()=>{if(connected)refresh()});
 setInterval(()=>{if(connected&&!document.hidden&&!busy)refresh()},60000);
}
return {start,changed};
})();

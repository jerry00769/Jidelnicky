(()=>{'use strict';
const $=id=>document.getElementById(id),clone=x=>structuredClone(x),storeKey='jidelnicky_static_v1';
const defaults={fish:1,legumes:1,meatless:1,sweetMax:1,avoidLegumePair:true,avoidFishPair:true};
const weekdays=['Pondělí','Úterý','Středa','Čtvrtek','Pátek'];
const today=new Date(),iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const parseDate=s=>{let [y,m,d]=s.split('-').map(Number);return new Date(y,m-1,d,12)};
const monday=s=>{let d=parseDate(s);if(Number.isNaN(d.getTime()))throw Error('Neplatné datum');d.setDate(d.getDate()-(d.getDay()+6)%7);return iso(d)};
const dateAt=(s,i)=>{let d=parseDate(s);d.setDate(d.getDate()+i);return d};
const format=d=>d.toLocaleDateString('cs-CZ',{day:'numeric',month:'numeric',year:'numeric'});
const freshDay=()=>({closed:false,soup:'',main:'',category:'',main2:'',category2:''});
const freshWeek=s=>({week:monday(s),days:Array.from({length:5},freshDay)});

let state;try{state=JSON.parse(localStorage.getItem(storeKey)||'null')}catch{};
if(!state||!state.catalog||!state.week||!Array.isArray(state.week.days)||state.week.days.length!==5)state={catalog:clone(window.INITIAL_CATALOG),week:freshWeek(iso(today)),history:[],rules:clone(defaults),txt:'',count:1,lockMain:8,lockSoup:3};
state.history??=[];state.rules={...defaults,...state.rules};state.txt??='';state.count=[1,2].includes(+state.count)?+state.count:1;

const undo=[],redo=[];const save=()=>{try{localStorage.setItem(storeKey,JSON.stringify(state))}catch(e){notice('Uložení selhalo. Prohlížeč může mít plné úložiště.',true)}};
const snapshot=()=>{undo.push(clone(state));if(undo.length>60)undo.shift();redo.length=0};
let statusTimer;function notice(message,error=false){const el=$('status');el.textContent=message;el.className=error?'error':'';el.style.display='block';clearTimeout(statusTimer);statusTimer=setTimeout(()=>el.style.display='none',6500)}
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const starts=(cat,p)=>cat.startsWith(p);
const all=(kind)=>Object.entries(state.catalog[kind]||{}).flatMap(([cat,items])=>items.map(name=>({cat,name})));

function txtRules(){
    const t={ban_main:[],ban_soup:[],ban_pair:[],require_main:[],require_soup:[],require_pair:[]};
    const names={ZAKAZ_HLAVNI:'ban_main',ZAKAZ_POLEVKA:'ban_soup',ZAKAZ_KOMBINACE:'ban_pair',VYZADUJ_HLAVNI:'require_main',VYZADUJ_POLEVKA:'require_soup',VYZADUJ_KOMBINACE:'require_pair'};
    for(const [i,raw] of state.txt.split(/\r?\n/).entries()){
        const line=raw.trim();if(!line||line.startsWith('#'))continue;
        const pos=line.indexOf('=');if(pos<0)throw Error(`TXT pravidla, řádek ${i+1}: chybí =`);
        const key=line.slice(0,pos).trim().toUpperCase(),value=line.slice(pos+1).trim();
        if(!names[key]||!value)throw Error(`TXT pravidla, řádek ${i+1}: neznámý příkaz nebo prázdná hodnota`);
        let item=value;if(key.includes('KOMBINACE')){item=value.split('|').map(x=>x.trim());if(item.length!==2||item.some(x=>!x))throw Error(`TXT pravidla, řádek ${i+1}: použij polévka | hlavní jídlo`)}
        t[names[key]].push(item)
    }
    return t;
}

const contains=(name,term)=>norm(name).includes(norm(term));
function mondayCat(week){const last=state.history.filter(h=>h.week<week&&!h.days?.[0]?.closed&&['RYBY','LUŠTĚNINOVÁ'].some(p=>starts(h.days?.[0]?.category||'',p))).sort((a,b)=>b.week.localeCompare(a.week))[0];return starts(last?.days?.[0]?.category||'','LUŠTĚNINOVÁ')?'RYBY':'LUŠTĚNINOVÁ'}

function validate(w=state.week){
    const e=[],r=state.rules,t=txtRules(),active=w.days.filter(d=>!d.closed),usedMain=[],usedSoup=[],cats=[];
    if(!active.length)return ['Není vybrán žádný den vaření.'];
    for(const d of active){
        if(!d.soup||!d.main||(state.count===2&&!d.main2))e.push('Některému dni chybí polévka nebo oběd.');
        usedSoup.push(d.soup);
        for(const key of state.count===2?['main','main2']:['main']){
            const m=d[key],cat=d[key==='main'?'category':'category2'];
            usedMain.push(m);cats.push(cat);
            if(t.ban_main.some(x=>contains(m,x))||t.ban_pair.some(([a,b])=>contains(d.soup,a)&&contains(m,b)))e.push('Zakázané hlavní jídlo nebo kombinace.');
        }
        if(t.ban_soup.some(x=>contains(d.soup,x)))e.push('Zakázaná polévka.');
        const sc=all('soup').find(x=>x.name===d.soup)?.cat||'';
        if(r.avoidLegumePair&&starts(d.category,'LUŠTĚNINOVÁ')&&contains(sc,'LUŠTĚNINOVÉ'))e.push('Luštěninová polévka s luštěninovým hlavním jídlem.');
        if(r.avoidFishPair&&starts(d.category,'RYBY')&&contains(d.soup,'rybi'))e.push('Rybí polévka s rybím hlavním jídlem.');
    }
    if(new Set(usedMain).size!==usedMain.length||new Set(usedSoup).size!==usedSoup.length)e.push('Opakování jídel nebo polévek v týdnu.');
    for(const [k,p] of [['fish','RYBY'],['legumes','LUŠTĚNINOVÁ'],['meatless','BEZMASÁ']])
        if(cats.filter(c=>starts(c,p)).length<r[k])e.push('Nedostatek jídel v kategorii '+p);
    if(cats.filter(c=>starts(c,'SLADKÁ')).length>r.sweetMax)e.push('Příliš mnoho sladkých jídel.');
    if(!w.days[0].closed&&!starts(w.days[0].category,mondayCat(w.week)))e.push('Pondělní Oběd 1 nesplňuje střídání ryb a luštěnin.');
    if(state.count===2&&!w.days[0].closed&&w.days[0].category===w.days[0].category2)e.push('Pondělní obědy musí být různých kategorií.');
    for(const term of t.require_main)if(!active.some(d=>contains(d.main,term)||(state.count===2&&contains(d.main2,term))))e.push('Chybí požadované hlavní jídlo: '+term);
    for(const term of t.require_soup)if(!active.some(d=>contains(d.soup,term)))e.push('Chybí požadovaná polévka: '+term);
    for(const [s,m] of t.require_pair)if(!active.some(d=>contains(d.soup,s)&&(contains(d.main,m)||(state.count===2&&contains(d.main2,m)))))e.push('Chybí požadovaná kombinace: '+s+' | '+m);
    return [...new Set(e)]
}

const rand=a=>a[Math.floor(Math.random()*a.length)];
const shuffle=a=>{for(let i=a.length-1;i>0;i--){let j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a};

function generate(){
    const week=monday($('date').value),active=state.week.days.map((d,i)=>d.closed?-1:i).filter(i=>i>=0);
    if(!active.length)throw Error('Není vybrán den vaření.');
    const cats=Object.keys(state.catalog.main),find=p=>cats.find(c=>starts(c,p)),fish=find('RYBY'),leg=find('LUŠTĚNINOVÁ'),meatless=find('BEZMASÁ');
    if(!fish||!leg||!meatless)throw Error('V katalogu chybí povinné kategorie.');
    const t=txtRules(),r=state.rules,required=[];
    for(const [k,c] of [['fish',fish],['legumes',leg],['meatless',meatless]])for(let i=0;i<r[k];i++)required.push(c);
    const mon=mondayCat(week),monName=mon==='RYBY'?fish:leg;
    if(active.includes(0)&&!required.includes(monName))required.push(monName);
    if(required.length>active.length)throw Error('Povinných kategorií je více než dní vaření.');
    const blockedMain=new Set(),blockedSoup=new Set();
    for(const h of state.history){
        const delta=(parseDate(week)-parseDate(h.week))/604800000;
        if(delta<=0)continue;
        for(const d of h.days||[]){
            if(d.closed)continue;
            if(delta<state.lockMain){if(d.main)blockedMain.add(d.main);if(d.main2)blockedMain.add(d.main2)}
            if(delta<state.lockSoup&&d.soup)blockedSoup.add(d.soup)
        }
    }
    let lastErrors=[];
    for(let attempt=0;attempt<500;attempt++){
        const days=Array.from({length:5},(_,i)=>({...freshDay(),closed:!active.includes(i)})),target=[...required],pool=cats.filter(c=>!starts(c,'SLADKÁ'));
        if(r.sweetMax>0&&target.length<active.length&&Math.random()<.5&&find('SLADKÁ'))target.push(find('SLADKÁ'));
        while(target.length<active.length)target.push(rand(pool));
        shuffle(target);
        if(active.includes(0)){const pos=target.indexOf(monName);if(pos>=0)[target[0],target[pos]]=[target[pos],target[0]]}
        const usedM=new Set(),usedS=new Set();let failed=false;
        for(const [index,day] of active.entries()){
            const cat=target[index],mains=shuffle((state.catalog.main[cat]||[]).filter(m=>!usedM.has(m)&&!blockedMain.has(m)&&!t.ban_main.some(x=>contains(m,x)))),soups=shuffle(all('soup').filter(({cat:sc,name:s})=>!usedS.has(s)&&!blockedSoup.has(s)&&!t.ban_soup.some(x=>contains(s,x))&&!(r.avoidLegumePair&&starts(cat,'LUŠTĚNINOVÁ')&&contains(sc,'LUŠTĚNINOVÉ'))&&!(r.avoidFishPair&&starts(cat,'RYBY')&&contains(s,'rybi'))).map(x=>x.name));
            let pair;
            for(const m of mains){const s=soups.find(s=>!t.ban_pair.some(([a,b])=>contains(s,a)&&contains(m,b)));if(s){pair={s,m};break}}
            if(!pair){failed=true;break}
            const d=days[day];d.closed=false;d.soup=pair.s;d.main=pair.m;d.category=cat;usedM.add(pair.m);usedS.add(pair.s);
            if(state.count===2){
                const options=all('main').filter(x=>x.cat!==cat&&!usedM.has(x.name)&&!blockedMain.has(x.name)&&!t.ban_main.some(b=>contains(x.name,b))&&!t.ban_pair.some(([a,b])=>contains(pair.s,a)&&contains(x.name,b))&&!(r.avoidFishPair&&starts(x.cat,'RYBY')&&contains(pair.s,'rybi')));
                if(!options.length){failed=true;break}
                const second=rand(options);d.main2=second.name;d.category2=second.cat;usedM.add(second.name)
            }
        }
        if(failed)continue;
        const w={week,days},errors=validate(w);
        if(!errors.length)return w;
        lastErrors=errors
    }
    throw Error('Nelze sestavit platný týden. '+lastErrors.slice(0,3).join(' '))
}

function render(){
    const w=state.week;
    $('date').value=w.week;$('count').value=state.count;$('lockMain').value=state.lockMain;$('lockSoup').value=state.lockSoup;
    $('range').textContent=`${format(dateAt(w.week,0))} – ${format(dateAt(w.week,4))}`;
    $('days').replaceChildren();
    for(let i=0;i<5;i++){
        const d=w.days[i],section=document.createElement('section');section.className='day';
        const title=document.createElement('div');title.className='daytitle';title.textContent=`${weekdays[i]} ${format(dateAt(w.week,i))}`;
        section.append(title);
        if(d.closed){
            const note=document.createElement('div');note.className='closed';note.textContent='(nevaří se)';section.append(note)
        }else{
            const meal=(label,key)=>{
                const row=document.createElement('div');row.className='meal';
                const lab=document.createElement('strong');lab.textContent=label;
                const btn=document.createElement('button');btn.textContent=d[key]||'Vybrat jídlo…';
                btn.addEventListener('click',()=>openPicker(i,key));
                row.append(lab,btn);section.append(row)
            };
            meal('Polévka','soup');meal('Oběd 1','main');
            if(state.count===2)meal('Oběd 2','main2')
        }
        $('days').append(section);
        const checkbox=document.querySelector(`[data-day="${i}"]`);
        if(checkbox)checkbox.checked=!d.closed
    }
    renderHistory();renderCategories();renderRules();
    $('txtRules').value=state.txt;save();
    if($('days').children.length!==5)notice('Chyba vykreslení pěti dnů.',true)
}

function renderHistory(){
    const el=$('history');el.replaceChildren();
    if(!state.history.length){el.textContent='Zatím žádné schválené týdny.';return}
    for(const h of [...state.history].sort((a,b)=>b.week.localeCompare(a.week)).slice(0,6)){
        const row=document.createElement('div');row.className='entry';
        const label=document.createElement('strong');label.textContent=`${format(dateAt(h.week,0))} – ${format(dateAt(h.week,4))}`;
        const open=document.createElement('button');open.className='alt';open.textContent='Náhled';open.onclick=()=>showHistory(h.week);
        row.append(label,open);el.append(row)
    }
    if(state.history.length>6){
        const more=document.createElement('p');more.className='muted';more.textContent=`Dalších ${state.history.length-6} týdnů najdeš ve správci historie.`;
        el.append(more)
    }
}

let selectedHistory=null;
function historyRows(){
    const target=$('historyList');target.replaceChildren();
    const items=[...state.history].sort((a,b)=>b.week.localeCompare(a.week));
    for(const h of items){
        const b=document.createElement('button');b.className='history-item'+(selectedHistory===h.week?' selected':'');
        b.textContent=`${format(dateAt(h.week,0))} – ${format(dateAt(h.week,4))}`;
        b.onclick=()=>{selectedHistory=h.week;historyRows();historyDetail()};
        target.append(b)
    }
    if(!items.length)target.textContent='Historie je zatím prázdná.'
}

function historyDetail(){
    const h=state.history.find(x=>x.week===selectedHistory);
    const el=$('historyPreview');el.replaceChildren();
    $('historyTitle').textContent=h?`Jídelníček ${format(dateAt(h.week,0))} – ${format(dateAt(h.week,4))}`:'Vyber uložený týden';
    for(const id of ['historyLoad','historyCopy','historyPrint','historyDelete'])$(id).disabled=!h;
    if(!h)return;
    for(let i=0;i<5;i++){
        const d=h.days[i]||{};const day=document.createElement('section');day.className='history-day';
        const name=document.createElement('strong');name.textContent=`${weekdays[i]} ${format(dateAt(h.week,i))}`;
        day.append(name);
        const content=document.createElement('div');
        content.textContent=d.closed||(!d.soup&&!d.main)?'(nevaří se)':`Polévka: ${d.soup||'—'}\nOběd 1: ${d.main||'—'}${d.main2?'\nOběd 2: '+d.main2:''}`;
        content.style.whiteSpace='pre-line';day.append(content);el.append(day)
    }
}

function showHistory(week){
    selectedHistory=week||[...state.history].sort((a,b)=>b.week.localeCompare(a.week))[0]?.week||null;
    historyRows();historyDetail();
    $('historyDialog').showModal(); $('historyDialog').scrollTop=0
}

function chosenHistory(){return state.history.find(h=>h.week===selectedHistory)}

$('openHistory').onclick=$('historyManager').onclick=()=>showHistory();
$('closeHistory').onclick=()=>$('historyDialog').close();
$('historyLoad').onclick=()=>safe(()=>{const h=chosenHistory();if(!h)return;snapshot();state.week=clone(h);state.count=h.days.some(d=>d.main2)?2:1;$('historyDialog').close();render();notice('Načtena pracovní kopie. Schválená historie se nezměnila.')});
$('historyCopy').onclick=()=>safe(()=>{const h=chosenHistory();if(!h)return;const target=prompt('Zadej datum nového týdne (RRRR-MM-DD):',iso(today));if(target===null)return;if(!/^\d{4}-\d{2}-\d{2}$/.test(target)||Number.isNaN(parseDate(target).getTime())||iso(parseDate(target))!==target)throw Error('Datum zadej jako RRRR-MM-DD.');snapshot();state.week=clone(h);state.week.week=monday(target);state.count=h.days.some(d=>d.main2)?2:1;$('historyDialog').close();render();notice('Týden zkopírován jako pracovní návrh. Historie se nepřepsala.')});
$('historyDelete').onclick=()=>safe(()=>{const h=chosenHistory();if(!h)return;if(!confirm('Opravdu smazat schválený týden '+format(dateAt(h.week,0))+'? Změnu lze vrátit tlačítkem Zpět.'))return;snapshot();state.history=state.history.filter(x=>x.week!==h.week);selectedHistory=null;render();historyRows();historyDetail();notice('Týden smazán z historie. Lze vrátit tlačítkem Zpět.')});
$('historyPrint').onclick=()=>safe(()=>{const h=chosenHistory();if(!h)return;const previous=clone(state.week),count=state.count;state.week=clone(h);state.count=h.days.some(d=>d.main2)?2:1;render();$('historyDialog').close();window.print();state.week=previous;state.count=count;render();notice('Připraven tisk vybraného týdne.')});

// Původní plně funkční import historie přes tlačítko
$('importHistory').onchange=async e=>{
    const f=e.target.files[0];if(!f)return;
    try{
        const data=JSON.parse(await f.text());
        if(!Array.isArray(data)||!data.every(h=>typeof h.week==='string'&&Array.isArray(h.days)&&h.days.length===5))throw Error('Soubor neobsahuje historii jídelníčků ve formátu Python JSON.');
        if(!confirm(`Importovat ${data.length} týdnů? Existující týdny se stejným datem budou zachovány.`))return;
        snapshot();
        const seen=new Set(state.history.map(h=>h.week));let added=0;
        for(const h of data){
            if(seen.has(h.week))continue;
            const copy=clone(h);
            copy.days=copy.days.map(d=>({...freshDay(),...d,closed:!!d.closed||(!d.soup&&!d.main)}));
            state.history.push(copy);seen.add(h.week);added++
        }
        render();notice(`Importováno ${added} nových týdnů. Původní historie zachována.`)
    }catch(err){
        notice(err.message,true)
    }finally{
        e.target.value=''
    }
};

const ruleNames={fish:'Ryby – minimálně',legumes:'Luštěniny – minimálně',meatless:'Bezmasá – minimálně',sweetMax:'Sladká – maximálně',avoidLegumePair:'Ne kombinace luštěnina + luštěnina',avoidFishPair:'Ne kombinace ryba + rybí polévka'};
function renderRules(){
    const el=$('rules');el.replaceChildren();
    for(const [key,label] of Object.entries(ruleNames)){
        const row=document.createElement('label');row.className='rule';
        const span=document.createElement('span');span.textContent=label;
        const input=document.createElement('input');input.dataset.rule=key;
        if(typeof defaults[key]==='boolean'){input.type='checkbox';input.checked=!!state.rules[key]}
        else{input.type='number';input.min='0';input.max='5';input.value=state.rules[key]}
        row.append(span,input);el.append(row)
    }
}

function renderCategories(){
    const kind=$('kind').value,sel=$('category'),prev=sel.value;
    sel.replaceChildren();
    for(const cat of Object.keys(state.catalog[kind]||{})){
        const option=document.createElement('option');option.value=cat;option.textContent=cat;sel.append(option)
    }
    if(Object.hasOwn(state.catalog[kind],prev))sel.value=prev;
    renderCatalogList();
}

let picking=null;
function openPicker(day,key){
    picking={day,key};
    $('pickerTitle').textContent=`${weekdays[day]} – ${key==='soup'?'Polévka':key==='main'?'Oběd 1':'Oběd 2'}`;
    $('search').value='';renderChoices();$('picker').showModal();$('search').focus()
}

function renderChoices(){
    const kind=picking.key==='soup'?'soup':'main',q=norm($('search').value),el=$('choices');el.replaceChildren();
    const current=state.week.days[picking.day];
    const options=all(kind).filter(x=>contains(x.name,q)||contains(x.cat,q)).filter(x=>picking.key==='soup'||(picking.key==='main'?x.name!==current.main2:x.name!==current.main));
    options.sort((a,b)=>a.name.localeCompare(b.name,'cs'));
    for(const item of options){
        const btn=document.createElement('button');btn.className='choice';btn.textContent=item.name;
        const sub=document.createElement('small');sub.textContent=item.cat;btn.append(sub);
        btn.onclick=()=>{
            snapshot();const d=state.week.days[picking.day];
            d[picking.key]=item.name;
            if(kind==='main')d[picking.key==='main'?'category':'category2']=item.cat;
            $('picker').close();render();notice('Jídlo upraveno.')
        };
        el.append(btn)
    }
    if(!options.length){const empty=document.createElement('p');empty.className='empty';empty.textContent='Žádné odpovídající jídlo.';el.append(empty)}
}

function csv(){
    const rows=[['Den','Datum','Polévka','Oběd 1','Oběd 2']];
    state.week.days.forEach((d,i)=>rows.push([weekdays[i],format(dateAt(state.week.week,i)),d.closed?'(nevaří se)':d.soup,d.closed?'':d.main,d.closed?'':state.count===2?d.main2:'']));
    const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';
    download('jidelnicek_'+state.week.week+'.csv','\ufeff'+rows.map(r=>r.map(quote).join(';')).join('\r\n'),'text/csv;charset=utf-8')
}

function safe(fn){try{fn()}catch(e){console.error(e);notice(e.message||'Nastala chyba.',true)}}

$('generate').onclick=()=>safe(()=>{snapshot();state.week=generate();render();notice('Vygenerováno pět dnů jídelníčku.')});
$('approve').onclick=()=>safe(()=>{const errors=validate();if(errors.length)throw Error(errors.join(' · '));if(state.history.some(h=>h.week===state.week.week)&&!confirm('Tento týden už je v historii. Opravdu přepsat schválenou verzi?'))return;snapshot();state.history=state.history.filter(h=>h.week!==state.week.week);state.history.push(clone(state.week));render();notice('Jídelníček schválen a uložen do historie.')});
$('validate').onclick=()=>safe(()=>{const e=validate();notice(e.length?e.join(' · '):'Jídelníček splňuje nastavená pravidla.',!!e.length)});
$('new').onclick=()=>safe(()=>{snapshot();const closed=state.week.days.map(d=>d.closed);state.week=freshWeek($('date').value);state.week.days.forEach((d,i)=>d.closed=closed[i]);render();notice('Prázdný týden připraven.')});
$('undo').onclick=()=>{if(!undo.length)return notice('Není co vrátit.');redo.push(clone(state));state=undo.pop();render();notice('Změna vrácena.')};
$('redo').onclick=()=>{~redo.length||notice('Není co zopakovat.');if(!redo.length)return;undo.push(clone(state));state=redo.pop();render();notice('Změna zopakována.')};
$('date').onchange=()=>safe(()=>{snapshot();state.week=freshWeek($('date').value);render()});
$('count').onchange=()=>safe(()=>{snapshot();state.count=+$('count').value;render()});
for(const key of ['lockMain','lockSoup'])$(key).onchange=()=>{snapshot();state[key]=Math.max(0,Math.min(key==='lockMain'?30:20,Number($(key).value)||0));render()};
document.querySelectorAll('[data-day]').forEach(input=>input.onchange=()=>{snapshot();const d=state.week.days[+input.dataset.day];d.closed=!input.checked;if(d.closed){d.soup='';d.main='';d.category='';d.main2='';d.category2=''}render()});
$('saveRules').onclick=()=>safe(()=>{const rules={};for(const input of document.querySelectorAll('[data-rule]'))rules[input.dataset.rule]=input.type==='checkbox'?input.checked:Math.max(0,Math.min(5,Number(input.value)||0));const txt=$('txtRules').value;const previous=state.txt;state.txt=txt;try{txtRules()}catch(e){state.txt=previous;throw e}snapshot();state.rules=rules;render();notice('Pravidla uložena.')});
$('kind').onchange=()=>{renderCategories();renderCatalogList()};
$('category').onchange=renderCatalogList;

let selectedCatalogMeal='';
function renderCatalogList(){
 const kind=$('kind').value,cat=$('category').value,items=(state.catalog[kind]?.[cat]||[]).slice().sort((a,b)=>a.localeCompare(b,'cs'));
 const query=norm($('catalogSearch').value),list=$('catalogList');list.replaceChildren();
 const total=Object.values(state.catalog[kind]||{}).reduce((n,a)=>n+a.length,0);
 $('catalogCount').textContent=`Kategorie: ${items.length} jídel · Celkem ${total} (${kind==='soup'?'polévky':'hlavní jídla'})`;
 let found=0;
 for(const name of items){if(!norm(name).includes(query))continue;found++;
  const b=document.createElement('button');b.type='button';b.className='catalog-item'+(name===selectedCatalogMeal?' selected':'');b.textContent=name;
  b.onclick=()=>{selectedCatalogMeal=name;$('mealName').value=name;renderCatalogList()};list.append(b)
 }
 if(!found){const e=document.createElement('p');e.className='empty';e.textContent='Žádná odpovídající jídla.';list.append(e)}
}
function editCatalog(operation){safe(()=>{
 const kind=$('kind').value,cat=$('category').value,name=$('mealName').value.trim(),items=state.catalog[kind]?.[cat];
 if(!items)throw Error('Nejdříve vyber kategorii.');
 if(operation==='add'){
  if(name.length<2)throw Error('Zadej název nového jídla.');
  if(items.some(x=>norm(x)===norm(name)))throw Error('Jídlo už v kategorii existuje.');
  snapshot();items.push(name);selectedCatalogMeal=name;
 }else{
  if(!selectedCatalogMeal||!items.includes(selectedCatalogMeal))throw Error('Nejdříve vyber jídlo ze seznamu.');
  if(operation==='rename'){
   if(name.length<2)throw Error('Zadej nový název.');
   if(items.some(x=>x!==selectedCatalogMeal&&norm(x)===norm(name)))throw Error('Jídlo už existuje.');
   if(name===selectedCatalogMeal)return notice('Název se nezměnil.');
   snapshot();items[items.indexOf(selectedCatalogMeal)]=name;selectedCatalogMeal=name;
  }else{
   if(!confirm(`Opravdu smazat jídlo „${selectedCatalogMeal}“?`))return;
   snapshot();items.splice(items.indexOf(selectedCatalogMeal),1);selectedCatalogMeal='';$('mealName').value='';
  }
 }
 items.sort((a,b)=>a.localeCompare(b,'cs'));render();renderCatalogList();notice(operation==='add'?'Jídlo přidáno.':operation==='rename'?'Jídlo přejmenováno.':'Jídlo smazáno.');
})}
$('add').onclick=()=>editCatalog('add');
$('rename').onclick=()=>editCatalog('rename');
$('remove').onclick=()=>editCatalog('remove');
$('catalogSearch').oninput=renderCatalogList;
$('kind').addEventListener('change',()=>{selectedCatalogMeal='';$('mealName').value='';$('catalogSearch').value=''});
$('category').addEventListener('change',()=>{selectedCatalogMeal='';$('mealName').value=''});
$('search').oninput=renderChoices;
$('closePicker').onclick=()=>$('picker').close();
$('csv').onclick=csv;
$('print').onclick=()=>window.print();
$('backup').onclick=()=>download('jidelnicky_zaloha_'+iso(today)+'.json',JSON.stringify({format:'jidelnicky-static-v1',state},null,2),'application/json;charset=utf-8');
$('restore').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    try{
        const imported=JSON.parse(await file.text());const next=imported.state;
        if(imported.format!=='jidelnicky-static-v1'||!next?.catalog?.main||!next?.catalog?.soup||!Array.isArray(next?.history)||next?.week?.days?.length!==5)throw Error('Neplatná záloha jídelníčků.');
        if(!confirm('Import přepíše aktuální data v tomto prohlížeči. Pokračovat?'))return;
        snapshot();state=next;state.rules={...defaults,...state.rules};render();notice('Záloha načtena.')
    }catch(err){notice(err.message,true)}finally{e.target.value=''}
};

// Funkce pro parsování TXT katalogu (skolni_obedy.txt) do struktury state.catalog
async function loadTxtCatalogIntoState() {
    try {
        let res = await fetch('skolni_obedy.txt');
        if (res.ok) {
            let text = await res.text();
            let parsed = { soup: {}, main: {} };
            let currentKind = null;
            let currentCat = null;
            for (let line of text.split(/\r?\n/)) {
                line = line.trim();
                if (!line) continue;
                let match = line.match(/^(POLÉVKY|HLAVNÍ JÍDLA)\s*[–-]\s*(.+?)\s*\(\d+\)\s*$/i);
                if (match) {
                    currentKind = match[1].toUpperCase().startsWith('POLÉVKY') ? 'soup' : 'main';
                    currentCat = match[2].trim().toUpperCase();
                    if (!parsed[currentKind][currentCat]) parsed[currentKind][currentCat] = [];
                    continue;
                }
                if (line.startsWith('-') && currentKind && currentCat) {
                    let mealName = line.replace(/^-\s*/, '').trim();
                    if (mealName && !parsed[currentKind][currentCat].includes(mealName)) {
                        parsed[currentKind][currentCat].push(mealName);
                    }
                }
            }
            if (Object.keys(parsed.main).length > 0) {
                for(const kind of ['soup','main']) for(const [category,items] of Object.entries(parsed[kind])) { const existing=state.catalog[kind][category]||[]; state.catalog[kind][category]=[...new Set([...existing,...items])].sort((a,b)=>a.localeCompare(b,'cs')); }
            }
        }
    } catch (e) {
        console.log('TXT katalog nebyl načten přes fetch (spuštěno lokálně přes file://), používá se výchozí katalog.');
    }
}


// Spuštění aplikace – načtení katalogu, historie a prvního jídelníčku
window.addEventListener('DOMContentLoaded', async () => {
    await loadTxtCatalogIntoState();

    try {
        const resHist = await fetch('historie_jidelnicku.json');

        if (resHist.ok) {
            const jsonHistory = await resHist.json();

            if (Array.isArray(jsonHistory) && jsonHistory.length > 0) {
                const seen = new Set(state.history.map(h => h.week));

                for (const h of jsonHistory) {
                    if (!seen.has(h.week)) {
                        state.history.push(h);
                        seen.add(h.week);
                    }
                }
            }
        }
    } catch (e) {
        console.log('Automatické načtení historie nebylo možné.', e);
    }

    // Automatické generování pouze při prvním spuštění.
    // Existující pracovní jídelníček se nikdy nepřepisuje.
    const hasMeals = state.week.days.some(d =>
        d.soup || d.main || d.main2
    );

    // Nový uživatel má prázdný pracovní týden.
    // Pokud již má uložený stav, ponecháme jej beze změny.
    const isFirstStart =
        localStorage.getItem(storeKey) === null;

    if (isFirstStart && !hasMeals) {
        try {
            // Generátor používá datum z formuláře.
            $('date').value = state.week.week;

            state.week = generate();
            console.log('První jídelníček byl automaticky vygenerován.');
        } catch (e) {
            console.error('Automatické generování se nezdařilo:', e);
            notice('První jídelníček se nepodařilo vygenerovat: ' +
                   e.message, true);
        }
    }

    render();
});
})();

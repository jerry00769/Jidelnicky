# -*- coding: utf-8 -*-
"""Offline návrhář školních jídelníčků. NENÍ kontrolou spotřebního koše."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, random, re, csv, datetime, unicodedata, configparser, sys, calendar, webbrowser, copy
from pathlib import Path

ROOT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
CATALOG = ROOT / 'skolni_obedy.txt'
OLD_CATALOG = ROOT / 'skolni_obedy_CR_rozsireny_2026.txt'
HISTORY = ROOT / 'historie_jidelnicku.json'
HISTORY_UNDO = ROOT / 'historie_zmen.json'
RULES = ROOT / 'pravidla_jidelny.json'
TXT_RULES = ROOT / 'vlastni_pravidla.txt'
NAMES_INI = ROOT / 'nazvy_jidel.ini'
TEXTS_INI = ROOT / 'nastaveni_textu.ini'
SETTINGS_INI = ROOT / 'nastaveni_programu.ini'
HELP_HTML = ROOT / 'napoveda_programu.html'
LEARNING = ROOT / 'uceni_jidelnicku.json'
GENERAL_UNDO = ROOT / 'zmeny_programu_undo.json'
CATEGORY_INI = ROOT / 'nazvy_kategorii.ini'
# Kompatibilita: staré datové soubory ponecháme a jednorázově zkopírujeme,
# aby po přejmenování nezmizela historie ani naučené preference.
def migrate_legacy_filenames():
    import shutil
    for old, new in (
        (ROOT / 'historie_jidelniku.json', HISTORY),
        (ROOT / 'uceni_jidelniku.json', LEARNING),
    ):
        if old.exists() and not new.exists():
            try:
                shutil.copy2(old, new)
            except OSError as exc:
                raise OSError(f'Nepodařilo se převést starý soubor {old.name} na {new.name}. '
                              f'Původní data zůstala zachována. Podrobnosti: {exc}')

migrate_legacy_filenames()

UI_DEFAULTS = {
 'window_title':'Generátor jídelníčků – návrh','week_label':'Týden od (DD.MM.RRRR):', 'repeat_main':'Bez opakování hlavního jídla (týdny):','repeat_soup':'Polévky:',
 'pdf':'Uložit PDF','days_label':'Vaří se:','generate':'Generuj další','approve':'Schválit a uložit týden','export':'Export CSV','history':'Historie','rules':'Pravidla jídelny','txt_rules':'Pravidla TXT','texts':'Nastavení textů',
 'hint':'Klikněte na polévku nebo hlavní jídlo pro výměnu.','menu_title':'JÍDELNÍ LÍSTEK','soup_label':'Polévka:','main_label':'Oběd 1:',
 'all':'VŠECHNY','categories':'Kategorie','meals':'Jídla','search':'Hledat podle názvu, suroviny či kategorie (bez diakritiky):',
 'pick_soup':'vyberte polévku','pick_main':'vyberte Oběd 1','choose':'Vybrat označené','random_pick':'Generuj výběr','rename_meal':'Přejmenovat jídlo','cancel':'Zrušit',
 'history_title':'Generátor jídelníčků – historie','history_load':'Načíst vybraný jídelníček','history_copy':'Zkopírovat do jiného týdne','history_close':'Zavřít','history_preview':'Náhled uloženého týdne','history_list':'Uložené týdny',
 'category_hint':'Dvojklik na kategorii ji přejmenuje; dvojklik na jídlo ho vybere.',
 'help':'Nápověda', 'tips_toggle':'Zobrazovat bubliny',
 'tip_generate':'Vytvoří nový návrh týdne podle pravidel a historie.',
 'tip_approve':'Schválí jídelníček a uloží jej do historie.',
 'tip_export':'Uloží tabulku jídel do CSV pro Excel.',
 'tip_pdf':'Uloží jídelní lístek do PDF bez doplňků a alergenů.',
 'tip_history':'Zobrazí archiv schválených týdnů a umožní opětovné použití.',
 'tip_rules':'Nastaví počty rybích, luštěninových a dalších jídel.',
 'tip_txt_rules':'Načte nebo upraví vlastní pravidla v TXT.',
 'tip_texts':'Upraví texty programu a informačních bublin v INI.',
 'tip_help':'Otevře podrobný návod k programu.',
 'tip_calendar':'Vybere datum; program nastaví pondělí daného týdne.',
 'tip_date':'Datum začátku týdne ve formátu DD.MM.RRRR.',
 'tip_repeat_main':'Počet týdnů bez opakování hlavního jídla.',
 'tip_repeat_soup':'Počet týdnů bez opakování polévky.',
 'tip_days':'Zaškrtněte dny, kdy se skutečně vaří.',
  'lunch_count':'Počet obědů:', 'tip_lunch_count':'1 = pouze Oběd 1, 2 = Oběd 1 a Oběd 2 každý den vaření.',
 'tip_preview':'Kliknutím na polévku nebo hlavní jídlo otevřete výběr jiného pokrmu.'}
DEFAULT_RULES = {'fish':1,'legumes':1,'meatless':1,'sweet_max':1,'sweet_gap_weeks':2,'avoid_legume_pair':True,'avoid_fish_pair':True}

def load_ui_texts():
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.optionxform=str
    if TEXTS_INI.exists(): cfg.read(TEXTS_INI,encoding='utf-8-sig')
    result={k:cfg.get('Texty',k,fallback=v) for k,v in UI_DEFAULTS.items()}
    if result.get('main_label','').strip().casefold() == 'hlavní jídlo:': result['main_label']='Oběd 1:'
    if result.get('pick_main','').strip().casefold() == 'vyberte hlavní jídlo': result['pick_main']='vyberte Oběd 1'
    return result

def save_ui_texts(values):
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.optionxform=str
    cfg['Texty']=values
    with TEXTS_INI.open('w',encoding='utf-8') as f:cfg.write(f)

def load_rules():
    if not RULES.exists(): return DEFAULT_RULES.copy()
    data=json.loads(RULES.read_text(encoding='utf-8'))
    if not isinstance(data,dict): raise ValueError('Soubor pravidel musí obsahovat objekt JSON.')
    result=DEFAULT_RULES.copy()
    for key in DEFAULT_RULES:
        if key in data:
            value=data[key]
            if isinstance(DEFAULT_RULES[key],bool):
                if not isinstance(value,bool): raise ValueError('Neplatné pravidlo: '+key)
            elif type(value) is not int or not 0<=value<=5:
                raise ValueError('Neplatné pravidlo: '+key+' (povolené celé číslo 0–5).')
            result[key]=value
    if result['fish']+result['legumes']+result['meatless']>5: raise ValueError('Povinné počty jídel přesahují 5 dní.')
    return result

def parse_txt_rules(content):
    """Přísná kontrola: chyby se vysvětlí a nic se potichu nepřeskočí."""
    import difflib
    result={'ban_main':[], 'ban_soup':[], 'ban_pair':[], 'require_main':[], 'require_soup':[], 'require_pair':[]}
    names={'ZAKAZ_HLAVNI':'ban_main','ZAKAZ_POLEVKA':'ban_soup',
           'ZAKAZ_KOMBINACE':'ban_pair','VYZADUJ_HLAVNI':'require_main',
           'VYZADUJ_POLEVKA':'require_soup','VYZADUJ_KOMBINACE':'require_pair',
           'ZAKAZ_POLEVKU':'ban_soup','ZAKAZ_KOMBINACI':'ban_pair',
           'VYZADUJ_POLEVKU':'require_soup'}
    seen=set()
    for n,raw in enumerate(content.splitlines(),1):
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if '=' not in line:
            raise ValueError(f'Řádek {n}: chybí znak =.\nSprávný zápis: ZAKAZ_HLAVNI = smažený sýr\nNapsáno: {line}')
        key,value=(x.strip() for x in line.split('=',1))
        key=key.upper()
        if key not in names:
            close=difflib.get_close_matches(key,list(names),n=1,cutoff=0.55)
            hint=f'\nNemělo být: {close[0]}?' if close else '\nPoužijte jeden z příkazů ZAKAZ_HLAVNI, ZAKAZ_POLEVKA, ZAKAZ_KOMBINACE, VYZADUJ_HLAVNI, VYZADUJ_POLEVKA, VYZADUJ_KOMBINACE.'
            raise ValueError(f'Řádek {n}: neznámý příkaz „{key}“.{hint}')
        if not value:
            raise ValueError(f'Řádek {n}: za znakem = chybí název jídla nebo výraz.')
        if '=' in value:
            raise ValueError(f'Řádek {n}: nadbytečný znak =. Každý řádek smí obsahovat jen jeden.')
        if key.endswith('KOMBINACE') or key=='ZAKAZ_KOMBINACI':
            if '|' not in value and any(c in value for c in ',;'):
                raise ValueError(f'Řádek {n}: kombinaci oddělte znakem |, nikoli čárkou nebo středníkem.\nPříklad: {key} = vývar | kuřecí')
            parts=[x.strip() for x in value.split('|')]
            if len(parts)!=2 or not all(parts):
                raise ValueError(f'Řádek {n}: kombinace musí obsahovat právě dvě neprázdné části oddělené |.\nPříklad: {key} = vývar | kuřecí')
            entry=tuple(parts)
        else:
            if '|' in value:
                raise ValueError(f'Řádek {n}: znak | patří pouze ke kombinacím.\nPro více zákazů napište každý na samostatný řádek.')
            entry=value
        signature=(names[key],entry)
        if signature in seen:
            raise ValueError(f'Řádek {n}: stejné pravidlo už je uvedeno výše. Smažte duplicitní řádek.')
        seen.add(signature)
        result[names[key]].append(entry)
    return result

def load_txt_rules():
    if not TXT_RULES.exists():return parse_txt_rules('')
    return parse_txt_rules(TXT_RULES.read_text(encoding='utf-8-sig'))

DAYS = ['Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek']

def load_catalog():
    if not CATALOG.exists() and OLD_CATALOG.exists():
        try:
            import shutil
            shutil.copy2(OLD_CATALOG, CATALOG)
        except OSError as exc:
            raise OSError('Nepodařilo se převést katalog na skolni_obedy.txt: '+str(exc))
    if not CATALOG.exists():
        raise FileNotFoundError('Vedle programu musí být soubor skolni_obedy.txt (případně původní skolni_obedy_CR_rozsireny_2026.txt).')
    groups, current = {}, None
    for line in CATALOG.read_text(encoding='utf-8-sig').splitlines():
        m = re.match(r'^(POLÉVKY|HLAVNÍ JÍDLA)\s*[–-]\s*(.+?)\s*\(\d+\)\s*$', line.strip())
        if m:
            current = ('soup' if m.group(1) == 'POLÉVKY' else 'main', m.group(2))
            groups[current] = []
        elif re.match(r'^[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ].*\(\d+\)$', line.strip()):
            current = None
        elif line.startswith('- ') and current:
            groups[current].append(line[2:].strip())
    return groups

def load_names():
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.optionxform=str
    if NAMES_INI.exists(): cfg.read(NAMES_INI,encoding='utf-8-sig')
    return cfg

def save_names(cfg):
    with NAMES_INI.open('w',encoding='utf-8') as f: cfg.write(f)

def rename_catalog(groups, cfg):
    for (kind,category),items in list(groups.items()):
        section='polevky' if kind=='soup' else 'hlavni'
        groups[(kind,category)]=[cfg.get(section, name, fallback=name) for name in items]
    return groups

def read_history():
    """Neplatnou historii nikdy tiše nepovažovat za prázdnou."""
    if not HISTORY.exists():
        return []
    try:
        data = json.loads(HISTORY.read_text(encoding='utf-8-sig'))
        if not isinstance(data, list):
            raise ValueError('Kořen historie musí být seznam týdnů.')
        seen = set()
        for i, record in enumerate(data, 1):
            if not isinstance(record, dict) or not isinstance(record.get('week'), str):
                raise ValueError(f'Záznam {i}: chybí platné datum týdne.')
            datetime.date.fromisoformat(record['week'])
            if record['week'] in seen:
                raise ValueError(f'Duplicitní týden {record["week"]}.')
            seen.add(record['week'])
            days = record.get('days')
            if not isinstance(days, list) or len(days) != 5 or any(not isinstance(d, dict) for d in days):
                raise ValueError(f'Týden {record["week"]}: očekáváno pět dnů.')
        return data
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError('Soubor historie_jidelnicku.json nelze bezpečně načíst.\n'
                         'Program jej NEPŘEPÍŠE. Zkontrolujte zálohu a opravte soubor.\n'
                         f'Podrobnosti: {exc}') from exc


def read_learning():
    if not LEARNING.exists():
        return {'main':{},'soup':{},'pair':{}}
    try:
        data=json.loads(LEARNING.read_text(encoding='utf-8'))
        if not isinstance(data,dict):raise ValueError('Neplatný formát učení.')
        return {k:{str(a):max(-20,min(20,int(b))) for a,b in data.get(k,{}).items()} for k in ('main','soup','pair')}
    except (ValueError,TypeError,OSError,AttributeError) as exc:
        raise ValueError('Soubor uceni_jidelnicku.json je poškozený.\\n'
                         'Zálohujte jej nebo přejmenujte a program spusťte znovu.\\n'+str(exc))

def pair_key(soup,main):
    return soup+' ||| '+main


def parse_czech_date(s):
    """Český formát, se zpětnou kompatibilitou pro stará data a nastavení."""
    s=s.strip()
    try:
        return datetime.datetime.strptime(s, '%d.%m.%Y').date()
    except ValueError:
        return datetime.date.fromisoformat(s)

def week_monday(s):
    d = parse_czech_date(s)
    return d - datetime.timedelta(days=d.weekday())

class HoverTip:
    """Jedna nenápadná nápověda pro ovládací prvky Tkinteru."""
    def __init__(self, root, enabled):
        self.root, self.enabled = root, enabled
        self.tips = {}
        self.timer = None
        self.popup = None
        self.active = None
        root.bind_all('<Enter>', self.enter, add='+')
        root.bind_all('<Leave>', self.leave, add='+')
        root.bind_all('<ButtonPress>', self.leave, add='+')

    def register(self, widget, description):
        self.tips[str(widget)] = description

    def clear(self):
        if self.timer is not None:
            try: self.root.after_cancel(self.timer)
            except tk.TclError: pass
            self.timer = None
        if self.popup:
            try: self.popup.destroy()
            except tk.TclError: pass
            self.popup = None

    def enter(self, event):
        self.clear()
        self.active = str(event.widget)
        if self.enabled() and self.active in self.tips:
            self.timer = self.root.after(700, lambda w=event.widget: self.show(w))

    def leave(self, event):
        self.clear()

    def show(self, widget):
        self.timer = None
        if not self.enabled() or str(widget) != self.active or not widget.winfo_exists(): return
        tip = self.tips.get(str(widget), '')
        if not tip: return
        self.popup = tk.Toplevel(widget)
        self.popup.wm_overrideredirect(True)
        try: self.popup.attributes('-topmost', True)
        except tk.TclError: pass
        label = tk.Label(self.popup, text=tip, justify='left', wraplength=340,
                         bg='#fff9db', fg='#202020', relief='solid', borderwidth=1,
                         padx=9, pady=6, font=('Segoe UI', 9))
        label.pack()
        self.popup.update_idletasks()
        x = widget.winfo_pointerx() + 15
        y = widget.winfo_pointery() + 18
        x = min(x, widget.winfo_screenwidth() - self.popup.winfo_reqwidth() - 8)
        y = min(y, widget.winfo_screenheight() - self.popup.winfo_reqheight() - 8)
        self.popup.geometry(f'+{max(0,x)}+{max(0,y)}')

class App:
    def open_calendar(self):
        """Český kalendář bez externích knihoven; výběr libovolného dne nastaví pondělí."""
        try:
            chosen = parse_czech_date(self.date.get())
        except ValueError:
            chosen = datetime.date.today()
        popup = tk.Toplevel(self.root)
        popup.title('Vybrat týden – kalendář')
        popup.transient(self.root)
        popup.resizable(False, False)
        popup.grab_set()
        frame = ttk.Frame(popup, padding=12)
        frame.pack()
        month_var = tk.StringVar()
        months = ('leden','únor','březen','duben','květen','červen','červenec','srpen','září','říjen','listopad','prosinec')
        weeknames = ('Po','Út','St','Čt','Pá','So','Ne')
        view = [chosen.year, chosen.month]
        header = ttk.Frame(frame)
        header.pack(fill='x', pady=(0,8))
        grid = ttk.Frame(frame)
        grid.pack()
        def change_month(delta):
            n = view[0] * 12 + view[1] - 1 + delta
            view[:] = [n // 12, n % 12 + 1]
            render()
        ttk.Button(header,text='◀',width=4,command=lambda:change_month(-1)).pack(side='left')
        ttk.Label(header,textvariable=month_var,anchor='center',width=20,font=('Segoe UI',11,'bold')).pack(side='left',padx=8)
        ttk.Button(header,text='▶',width=4,command=lambda:change_month(1)).pack(side='left')
        def select(day):
            picked = datetime.date(view[0], view[1], day)
            monday = picked - datetime.timedelta(days=picked.weekday())
            self.date.set(monday.strftime('%d.%m.%Y'))
            popup.destroy()
            # Nový týden se musí znovu vygenerovat, aby nezůstala data předchozího týdne.
            self.open_selected_week()
        def render():
            for child in grid.winfo_children(): child.destroy()
            month_var.set(f'{months[view[1]-1].capitalize()} {view[0]}')
            for c,name in enumerate(weeknames):
                ttk.Label(grid,text=name,anchor='center',width=5).grid(row=0,column=c,pady=4)
            for r,week in enumerate(calendar.monthcalendar(view[0],view[1]),1):
                for c,day in enumerate(week):
                    if day:
                        date_cell = datetime.date(view[0], view[1], day)
                        monday_cell = date_cell - datetime.timedelta(days=date_cell.weekday())
                        selected_monday = chosen - datetime.timedelta(days=chosen.weekday())
                        bg = '#ffffff'
                        fg = '#203451'
                        if monday_cell == selected_monday and c < 5:
                            bg = '#dceafa'
                        if date_cell == chosen:
                            bg, fg = '#285da3', '#ffffff'
                        if date_cell == datetime.date.today():
                            bg, fg = '#2c925e', '#ffffff'
                        btn=tk.Button(grid,text=str(day),width=4,command=lambda d=day:select(d),
                                      bg=bg,fg=fg,activebackground='#c7daf5',
                                      relief='flat',bd=1,cursor='hand2')
                        btn.grid(row=r,column=c,padx=2,pady=2)
        ttk.Label(frame,text='Zelená: dnes   Modrá: vybraný den   Světle modrá: pracovní týden',
                  foreground='#38516f').pack(pady=(8,0))
        render()
        popup.update_idletasks()
        x=self.root.winfo_rootx()+max(0,(self.root.winfo_width()-popup.winfo_width())//2)
        y=self.root.winfo_rooty()+max(0,(self.root.winfo_height()-popup.winfo_height())//2)
        popup.geometry(f'+{x}+{y}')

    def __init__(self, root):
        self.ui=load_ui_texts()
        settings=configparser.ConfigParser()
        settings.read(SETTINGS_INI,encoding='utf-8')
        self.tips_enabled=tk.BooleanVar(value=str(settings.get('Napoveda','bubliny',fallback='true')).strip().lower() in ('ano','true','1','yes','on'))
        self.lunch_count=tk.IntVar(value=settings.getint('Obedy','pocet',fallback=1) if settings.get('Obedy','pocet',fallback='1') in ('1','2') else 1)
        self.tips=HoverTip(root, lambda: self.tips_enabled.get())

        self.names_cfg=load_names()
        self.root, self.groups = root, rename_catalog(load_catalog(),self.names_cfg)
        self.history = read_history()
        self.history_undo, self.history_redo = self.load_history_journal()
        self.learning = read_learning()
        self.rules = load_rules()
        self.txt_rules = load_txt_rules()
        self.current = None
        self.parked_days = {}
        self.edit_undo, self.edit_redo = self.load_edit_journal()
        self.click_ranges = []
        root.title(self.t('window_title'))
        root.geometry('1050x780')
        root.minsize(780, 560)
        bar = ttk.Frame(root, padding=12); bar.pack(fill='x')
        ttk.Label(bar, text=self.t('week_label')).pack(side='left')
        today = datetime.date.today()
        self.date = tk.StringVar(value=(today - datetime.timedelta(days=today.weekday())).strftime('%d.%m.%Y'))
        date_entry=ttk.Entry(bar, textvariable=self.date, width=12);date_entry.pack(side='left', padx=(6, 1))
        self.tips.register(date_entry,self.t('tip_date'))
        cal_button=ttk.Button(bar, text='📅', width=3, command=self.open_calendar);cal_button.pack(side='left', padx=(0, 7))
        self.tips.register(cal_button,self.t('tip_calendar'))
        ttk.Label(bar, text=self.t('repeat_main')).pack(side='left')
        self.lock_main = tk.IntVar(value=8)
        spin_main=ttk.Spinbox(bar, from_=1, to=30, textvariable=self.lock_main, width=4);spin_main.pack(side='left', padx=5)
        self.tips.register(spin_main,self.t('tip_repeat_main'))
        ttk.Label(bar, text=self.t('repeat_soup')).pack(side='left')
        self.lock_soup = tk.IntVar(value=3)
        spin_soup=ttk.Spinbox(bar, from_=1, to=20, textvariable=self.lock_soup, width=4);spin_soup.pack(side='left', padx=5)
        self.tips.register(spin_soup,self.t('tip_repeat_soup'))
        actions = ttk.Frame(root, padding=(12, 0)); actions.pack(fill='x')
        for key, callback in [('generate',self.generate),('approve',self.approve),
                              ('export',self.export),('pdf',self.export_pdf),
                              ('history',self.show_history),('rules',self.edit_rules),
                              ('txt_rules',self.edit_txt_rules),('texts',self.edit_ui_texts)]:
            button=ttk.Button(actions,text=self.t(key),command=callback)
            button.pack(side='left',padx=4)
            self.tips.register(button,self.t('tip_'+key))
        help_button=ttk.Button(actions,text=self.t('help'),command=self.open_help)
        help_button.pack(side='left',padx=4)
        self.tips.register(help_button,self.t('tip_help'))
        daybar=ttk.Frame(root,padding=(16,6));daybar.pack(fill='x')
        day_controls=ttk.Frame(daybar);day_controls.pack(side='left')
        ttk.Label(day_controls,text=self.t('days_label')).pack(side='left',padx=(0,8))
        self.active_days=[tk.BooleanVar(value=True) for _ in DAYS]
        for i,name in enumerate(DAYS):
            day_check=ttk.Checkbutton(daybar,text=name,variable=self.active_days[i],command=self.on_days_changed);day_check.pack(in_=day_controls,side='left',padx=7)
            self.tips.register(day_check,self.t('tip_days'))
        # Počet obědů se ukládá a při příštím spuštění načítá.
        lunch_controls=ttk.Frame(day_controls);lunch_controls.pack(side='left',padx=(8,0))
        ttk.Label(lunch_controls,text=self.t('lunch_count')).pack(side='left',padx=(0,5))
        lunch_box=ttk.Combobox(lunch_controls,values=('1','2'),width=3,state='readonly',textvariable=self.lunch_count)
        lunch_box.pack(side='left')
        lunch_box.bind('<<ComboboxSelected>>',self.on_lunch_count_changed)
        self.tips.register(lunch_box,self.t('tip_lunch_count'))
        # Zpět/Znovu přímo za pátkem na řádku dnů vaření.
        undo_controls=ttk.Frame(day_controls)
        undo_controls.pack(side='left',padx=(8,0))
        self.btn_undo=ttk.Button(undo_controls,text='↶ Zpět',command=self.undo_edit)
        self.btn_undo.pack(side='left',padx=3)
        self.btn_redo=ttk.Button(undo_controls,text='↷ Znovu',command=self.redo_edit)
        self.btn_redo.pack(side='left',padx=3)
        self.tips.register(self.btn_undo,'Vrátí poslední úpravu jídelníčku, pravidel nebo nastavení.')
        self.tips.register(self.btn_redo,'Zopakuje poslední vrácenou úpravu.')
        # Náhled skutečného jídelního lístku místo tabulky.
        preview = ttk.Frame(root, padding=(14, 10)); preview.pack(fill='both', expand=True)
        self.paper = tk.Text(preview, wrap='word', font=('Segoe UI', 12), bg='white',
                             fg='#202020', padx=28, pady=16, relief='solid', borderwidth=1)
        scrollbar_paper = ttk.Scrollbar(preview, orient='vertical', command=self.paper.yview)
        scrollbar_paper.pack(side='right', fill='y')
        self.paper.configure(yscrollcommand=scrollbar_paper.set)
        self.paper.pack(side='left', fill='both', expand=True)
        self.paper.tag_configure('title', font=('Segoe UI', 20, 'bold'), justify='center', spacing3=4)
        self.paper.tag_configure('dates', font=('Segoe UI', 11, 'bold'), foreground='#17476b', justify='center', spacing3=18)
        self.paper.tag_configure('day', font=('Segoe UI', 12, 'bold'), foreground='#17476b', spacing1=9, spacing3=4)
        self.paper.tag_configure('soup', font=('Segoe UI', 11), lmargin1=22, lmargin2=22, spacing3=2)
        self.paper.tag_configure('main', font=('Segoe UI', 12, 'bold'), lmargin1=22, lmargin2=22, spacing3=6)
        self.paper.tag_configure('editable', underline=False)
        self.paper.bind('<Button-1>', self.click_meal)
        self.paper.bind('<Motion>', self.hover_meal)
        self.paper.bind('<Leave>', self.hide_meal_tip)
        self._meal_tip = None
        self._meal_tip_item = None
        self.paper.tag_configure('foot', font=('Segoe UI', 9), foreground='#666666', justify='center', spacing1=14)
        self.paper.insert('end', self.t('menu_title')+'\n', 'title')
        self.paper.insert('end', 'Klikněte na Generuj další a zobrazí se návrh týdne.\n', 'dates')
        self.paper.configure(state='disabled')
        self.status = tk.StringVar(value='Připraveno. Vyberte týden, upravte jídla nebo vytvořte nový návrh.')
        # Dvě informační řádky vlevo; volba bublin svisle uprostřed mezi nimi.
        # Pravý okraj textu volby je zarovnán s pravým okrajem náhledu jídelníčku.
        bottom=ttk.Frame(root,padding=(14,0,32,3));bottom.pack(side='bottom',fill='x')
        bottom.columnconfigure(0,weight=1)
        caution=ttk.Label(bottom,
            text='Vlastní pravidla jsou plánovací omezení, nikoli právní kontrola. Skutečný spotřební koš vyžaduje receptury, gramáže a počty strávníků.',
            wraplength=800,anchor='w',justify='left')
        caution.grid(row=0,column=0,sticky='ew',pady=(0,1))
        status_label=tk.Label(bottom,textvariable=self.status,wraplength=800,
            anchor='w',justify='left',fg='#165e96',font=('Segoe UI',9,'bold'))
        status_label.grid(row=1,column=0,sticky='ew')
        toggle=ttk.Checkbutton(bottom,text=self.t('tips_toggle'),
            variable=self.tips_enabled,command=self.save_tip_setting)
        toggle.grid(row=0,column=1,rowspan=2,sticky='e',padx=(16,0))
        self.root.after_idle(self.open_selected_week)

    def edit_snapshot(self):
        paths={'catalog':CATALOG,'rules':RULES,'txt':TXT_RULES,'names':NAMES_INI,'categories':CATEGORY_INI,
               'texts':TEXTS_INI,'settings':SETTINGS_INI,'learning':LEARNING}
        return {'files':{k:(p.read_text(encoding='utf-8') if p.exists() else None)
                         for k,p in paths.items()},
                'current':copy.deepcopy(self.current),
                'parked':copy.deepcopy(self.parked_days),
                'days':[v.get() for v in self.active_days],
                 'lunch_count':self.lunch_count.get()}

    def load_edit_journal(self):
        try:
            if GENERAL_UNDO.exists():
                data=json.loads(GENERAL_UNDO.read_text(encoding='utf-8'))
                return data.get('undo',[])[-30:],data.get('redo',[])[-30:]
        except (OSError,ValueError,AttributeError):
            messagebox.showwarning('Vrácení změn','Soubor zmeny_programu_undo.json nelze načíst.\n'
                                   'Původní data programu zůstávají zachována.')
        return [],[]

    def write_edit_journal(self):
        temp=GENERAL_UNDO.with_suffix('.json.tmp')
        temp.write_text(json.dumps({'undo':self.edit_undo[-30:],'redo':self.edit_redo[-30:]},
                                   ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(GENERAL_UNDO)

    def record_edit(self,before,description):
        after=self.edit_snapshot()
        if before==after:return
        self.edit_undo.append({'description':description,'state':before})
        self.edit_undo=self.edit_undo[-30:]
        self.edit_redo=[]
        self.status.set('Provedeno: '+description+'. Změnu lze vrátit tlačítkem Zpět.')
        try:self.write_edit_journal()
        except OSError as exc:
            messagebox.showwarning('Záloha změny','Změna se provedla, ale krok Zpět nelze uložit.\n'+str(exc))

    def restore_edit_snapshot(self,state):
        paths={'catalog':CATALOG,'rules':RULES,'txt':TXT_RULES,'names':NAMES_INI,'categories':CATEGORY_INI,
               'texts':TEXTS_INI,'settings':SETTINGS_INI,'learning':LEARNING}
        # Nejprve záloha, pak zápis; případná chyba obnoví dosavadní soubory.
        previous=self.edit_snapshot()
        try:
            for key,value in state['files'].items():
                if key not in paths:continue
                path=paths[key]
                if value is None:
                    if path.exists():path.unlink()
                else:
                    tmp=path.with_suffix(path.suffix+'.undo_tmp')
                    tmp.write_text(value,encoding='utf-8')
                    tmp.replace(path)
            self.rules=load_rules()
            self.txt_rules=load_txt_rules()
            self.names_cfg=load_names()
            self.groups=rename_catalog(load_catalog(),self.names_cfg)
            self.ui=load_ui_texts()
            self.learning=read_learning()
            cfg=configparser.ConfigParser();cfg.read(SETTINGS_INI,encoding='utf-8')
            self.tips_enabled.set(cfg.get('Napoveda','bubliny',fallback='true').lower() in ('true','ano','yes','1','on'))
            self.current=copy.deepcopy(state['current'])
            self.parked_days=copy.deepcopy(state['parked'])
            for var,val in zip(self.active_days,state['days']):var.set(val)
            self.lunch_count.set(state.get('lunch_count',1))
            if self.current:self.date.set(datetime.date.fromisoformat(self.current['week']).strftime('%d.%m.%Y'))
            if self.current:self.display(self.current['days'])
            else:
                self.paper.configure(state='normal')
                self.paper.delete('1.0','end')
                self.paper.insert('end','Návrh byl vrácen. Klikněte na Generuj další nebo načtěte týden z historie.')
                self.paper.configure(state='disabled')
        except Exception:
            for key,value in previous['files'].items():
                path=paths[key]
                if value is None:
                    if path.exists():path.unlink()
                else:path.write_text(value,encoding='utf-8')
            raise

    def edit_step(self,redo=False):
        source=self.edit_redo if redo else self.edit_undo
        target=self.edit_undo if redo else self.edit_redo
        if not source:
            messagebox.showinfo('Změny','Není žádná změna k '+('opakování.' if redo else 'vrácení.')+'\n'
                'Změny uložené historie se vracejí samostatně v okně Historie.')
            return
        entry=source[-1]
        current=self.edit_snapshot()
        try:self.restore_edit_snapshot(entry['state'])
        except Exception as exc:
            messagebox.showerror('Nelze vrátit změnu',str(exc));return
        source.pop()
        target.append({'description':entry['description'],'state':current})
        target[:]=target[-30:]
        try:self.write_edit_journal()
        except OSError as exc:messagebox.showwarning('Uložení vrácení',str(exc))
        self.status.set(('Znovu provedeno: ' if redo else 'Vrácena změna: ')+entry['description']+'.')

    def undo_edit(self):self.edit_step(False)
    def redo_edit(self):self.edit_step(True)

    def save_tip_setting(self):
        before=self.edit_snapshot()
        previous=configparser.ConfigParser()
        previous.read(SETTINGS_INI,encoding='utf-8')
        before_value=previous.get('Napoveda','bubliny',fallback='true').lower() in ('true','ano','1','yes','on')
        cfg=configparser.ConfigParser()
        cfg.read(SETTINGS_INI,encoding='utf-8')
        if not cfg.has_section('Napoveda'):cfg.add_section('Napoveda')
        cfg.set('Napoveda','bubliny','true' if self.tips_enabled.get() else 'false')
        with SETTINGS_INI.open('w',encoding='utf-8') as file: cfg.write(file)
        self.record_edit(before,'Změna zobrazování bublin')
        self.status.set('Informační bubliny '+('zapnuty.' if self.tips_enabled.get() else 'vypnuty.')+' Změnu lze vrátit tlačítkem Zpět.')
        if not self.tips_enabled.get():
            self.tips.clear()
            self.hide_meal_tip()

    def on_lunch_count_changed(self,event=None):
        before=self.edit_snapshot()
        # Combobox už obsahuje novou hodnotu; v záznamu Zpět uchováme předchozí.
        cfg=configparser.ConfigParser();cfg.read(SETTINGS_INI,encoding='utf-8')
        previous=cfg.getint('Obedy','pocet',fallback=1)
        before['lunch_count']=previous
        count=self.lunch_count.get()
        if not cfg.has_section('Obedy'):cfg.add_section('Obedy')
        cfg.set('Obedy','pocet',str(count))
        try:
            with SETTINGS_INI.open('w',encoding='utf-8') as f:cfg.write(f)
        except OSError as exc:
            self.lunch_count.set(previous)
            messagebox.showerror('Nastavení obědů',str(exc));return
        if not self.current:
            self.ensure_editable_week()
        if self.current:
            for i,d in enumerate(self.current['days']):
                if d.get('closed'):continue
                if count==2:
                    # I dříve uložený Oběd 2 může být po přepnutí neplatný.
                    same_meal=d.get('main2')==d.get('main')
                    wrong_monday=(i==0 and bool(d.get('main2')) and
                        self.main_category_family(d.get('category2',''))==
                        self.main_category_family(d.get('category','')))
                    if not d.get('main2') or same_meal or wrong_monday:
                        d['main2']='';d['category2']=''
                        self.fill_second_main(i)
            self.display(self.current['days'])
        self.record_edit(before,'Změna počtu obědů')
        self.status.set(f'Počet obědů: {count}. Nastavení je uloženo i pro příští spuštění.')

    def fill_second_main(self,index):
        if not self.current:return
        days=self.current['days'];d=days[index]
        if d.get('closed'):return
        used={x.get(k) for x in days if not x.get('closed') for k in ('main','main2')}
        choices=[(cat,meal) for (kind,cat),items in self.groups.items() if kind=='main'
                 for meal in items if meal not in used and self.allowed_item(meal,'main')
                 and self.allowed_pair(d['soup'],meal)
                 # Při přepnutí z 1 na 2 obědy nesmí mít pondělní Oběd 2
                 # stejnou kategorii jako Oběd 1 (např. dvě různá jídla z cizrny).
                 and not (index==0 and self.main_category_family(cat)==self.main_category_family(d.get('category','')))]
        if self.rules['avoid_fish_pair'] and 'rybi' in self.normalize(d['soup']):
            choices=[(cat,m) for cat,m in choices if not cat.startswith('RYBY')]
        if self.rules['avoid_legume_pair'] and any(d['soup'] in items for (kind,cat),items in self.groups.items() if kind=='soup' and 'LUŠTĚNINOVÉ' in cat):
            choices=[(cat,m) for cat,m in choices if not cat.startswith('LUŠTĚNINOVÁ')]
        if choices:
            cat,meal=self.weighted_choice(choices,'main',lambda x:x[1])
            d['main2']=meal;d['category2']=cat
        else:
            d['main2']='';d['category2']=''
            messagebox.showwarning('Oběd 2','Pro '+DAYS[index]+' nebylo možné najít další vhodné jídlo. Upravte pravidla nebo blokování.')

    def open_help(self):
        if HELP_HTML.exists():
            webbrowser.open(HELP_HTML.resolve().as_uri())
        else:
            messagebox.showerror('Nápověda','Soubor napoveda_programu.html nebyl nalezen.\nUmístěte jej vedle programu.',parent=self.root)

    def ensure_editable_week(self):
        """Při úpravě schváleného týdne vytvoří bezpečnou pracovní kopii."""
        try:
            week=str(week_monday(self.date.get()))
        except ValueError as exc:
            messagebox.showwarning('Datum týdne',str(exc))
            return False
        if self.current and self.current.get('week')==week:
            return True
        if self.current and self.current.get('week')!=week:
            self.current=None
        stored=next((h for h in self.history if h['week']==week),None)
        if not stored:
            return False
        self.current=copy.deepcopy(stored)
        self.parked_days.clear()
        self.sync_days(self.current['days'])
        self.status.set('Upravujete pracovní kopii schváleného týdne. Historie se změní až po potvrzení tlačítkem Schválit a uložit týden.')
        return True

    def on_days_changed(self):
        # Při ruční změně data nepoužít zobrazené jídlo z jiného týdne.
        try:
            selected_week=str(week_monday(self.date.get()))
        except ValueError as exc:
            messagebox.showwarning('Datum týdne',str(exc));return
        if self.current and self.current.get('week')!=selected_week:
            self.open_selected_week()
            return
        before=self.edit_snapshot()
        if not self.current:
            try:
                week=str(week_monday(self.date.get()))
                stored=next((h for h in self.history if h['week']==week),None)
                if stored:before['current']=copy.deepcopy(stored)
            except ValueError:pass
        before['days']=[(not d.get('closed',False)) for d in self.current['days']] if self.current else [v.get() for v in self.active_days]
        if not self.ensure_editable_week():
            # Nový týden bez uloženého jídelníčku: vytvořit návrh podle zaškrtnutých dnů.
            self.generate()
            return
        for i,var in enumerate(self.active_days):
            day=self.current['days'][i]
            if not var.get() and not day.get('closed'):
                self.parked_days[i]=dict(day)
                self.current['days'][i]={'closed':True,'soup':'','main':'','category':''}
            elif var.get() and day.get('closed'):
                restored=self.parked_days.pop(i,None)
                if restored and restored.get('soup') and restored.get('main'):
                    self.current['days'][i]=restored
                else:
                    self.current['days'][i]={'soup':'','main':'','category':''}
                    self.fill_missing_day(i)
        if self.lunch_count.get()==2:
            for i,d in enumerate(self.current['days']):
                if not d.get('closed') and not d.get('main2'):self.fill_second_main(i)
        self.display(self.current['days'])
        self.record_edit(before,'Změna dnů vaření')
        issue=self.validate_days(self.current['days'])
        self.status.set('Provedeno: změna dnů vaření ('+', '.join(DAYS[i] for i,v in enumerate(self.active_days) if v.get())+'). '+('Upozornění: '+issue if issue else 'Změnu lze vrátit tlačítkem Zpět.'))

    def fill_missing_day(self,index):
        # Doplňujeme pouze nově aktivovaný den; ostatní jídla se nemění.
        days=self.current['days']
        used_main={d.get(k) for i,d in enumerate(days) if i!=index and not d.get('closed') for k in ('main','main2') if d.get(k)}
        used_soup={d.get('soup') for i,d in enumerate(days) if i!=index and not d.get('closed')}
        monday_prefix=self.monday_required_category(week_monday(self.date.get())) if index==0 else None
        mains=[(cat,meal) for (kind,cat),items in self.groups.items() if kind=='main' for meal in items if meal not in used_main and self.allowed_item(meal,'main')
               and (monday_prefix is None or cat.startswith(monday_prefix))]
        random.shuffle(mains)
        for cat,meal in mains:
            soups=[s for (kind,_),items in self.groups.items() if kind=='soup' for s in items if s not in used_soup and self.allowed_item(s,'soup') and self.allowed_pair(s,meal)]
            if soups:
                days[index]={'soup':random.choice(soups),'main':meal,'category':cat}
                if self.lunch_count.get()==2:self.fill_second_main(index)
                return
        messagebox.showwarning('Doplnění dne','Nepodařilo se najít vhodnou dvojici jídel. Vyberte ji ručně.')

    def sync_days(self,days):
        for i,d in enumerate(days):
            self.active_days[i].set(not d.get('closed',False))

    def learn(self,kind,key,delta):
        table=self.learning[kind]
        table[key]=max(-20,min(20,table.get(key,0)+delta))
        try:
            temp=LEARNING.with_suffix('.json.tmp')
            temp.write_text(json.dumps(self.learning,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(LEARNING)
        except OSError as exc:
            messagebox.showwarning('Učení nelze uložit',
                'Změna jídelníčku se provedla, ale preference se neuložila.\\n'+str(exc))

    def weighted_choice(self,options,kind,extract=lambda x:x):
        if not options:raise ValueError('Nejsou dostupná vhodná jídla.')
        weights=[max(1,10+self.learning[kind].get(extract(x),0)*2 + (self.learning['main'].get(x[3],0) if kind=='pair' else 0) + (self.learning['soup'].get(x[1],0) if kind=='pair' else 0)) for x in options]
        return random.choices(options,weights=weights,k=1)[0]

    def build_candidate(self,selected,used_main,used_soup,fish,legumes,r):
        """Cíleně vloží povinné kombinace, pak doplní požadované kategorie."""
        all_mains=[(cat,meal) for (kind,cat),items in self.groups.items()
                   if kind=='main' for meal in items
                   if meal not in used_main and self.allowed_item(meal,'main')]
        all_soups=[(cat,meal) for (kind,cat),items in self.groups.items()
                   if kind=='soup' for meal in items
                   if meal not in used_soup and self.allowed_item(meal,'soup')]
        def compatible(sc,soup,mc,main):
            return self.allowed_pair(soup,main) and not (
                r['avoid_legume_pair'] and mc==legumes and 'LUŠTĚNINOVÉ' in sc) and not (
                r['avoid_fish_pair'] and mc==fish and 'rybi' in self.normalize(soup))
        pairs=[]
        obligations=[(a,b) for a,b in self.txt_rules['require_pair']]
        # Samostatné požadavky lze spojit do stejného dne, pokud to jídla umožní.
        obligations += [('',b) for b in self.txt_rules['require_main']]
        obligations += [(a,'') for a in self.txt_rules['require_soup']]
        random.shuffle(obligations)
        for soup_term,main_term in obligations:
            if any((not soup_term or self.matches(s,soup_term)) and
                   (not main_term or self.matches(m,main_term)) for _,s,_,m in pairs):
                continue
            options=[(sc,s,mc,m) for mc,m in all_mains for sc,s in all_soups
                     if m not in [p[3] for p in pairs] and s not in [p[1] for p in pairs]
                     and (not main_term or self.matches(m,main_term))
                     and (not soup_term or self.matches(s,soup_term))
                     and compatible(sc,s,mc,m)]
            if not options:raise ValueError('Požadované jídlo nebo kombinace nejsou dostupné: '+
                                            (soup_term+' | '+main_term).strip(' |'))
            choice=self.weighted_choice(options,'pair',lambda p:pair_key(p[1],p[3]))
            pairs.append(choice)
            if len(pairs)>len(selected):
                raise ValueError('Příliš mnoho povinných jídel či kombinací na počet dní vaření.')
        required_categories=[]
        for cat,count in ((fish,r['fish']),(legumes,r['legumes'])):
            required_categories.extend([cat]*count)
        meatless=next(c for c in selected if c.startswith('BEZMASÁ')) if any(c.startswith('BEZMASÁ') for c in selected) else None
        if meatless:required_categories.extend([meatless]*r['meatless'])
        for _,_,mc,_ in pairs:
            if mc in required_categories:required_categories.remove(mc)
        if len(required_categories)+len(pairs)>len(selected):
            raise ValueError('Povinné kombinace jsou v rozporu s počty kategorií.')
        remaining=len(selected)-len(pairs)-len(required_categories)
        optional=list(selected)
        for _,_,mc,_ in pairs:
            if mc in optional:optional.remove(mc)
        for c in required_categories:
            if c in optional:optional.remove(c)
        random.shuffle(optional)
        categories=required_categories+optional[:remaining]
        if len(categories)<len(selected)-len(pairs):
            categories.extend(random.choices([c for c in selected if not c.startswith('SLADKÁ')],k=len(selected)-len(pairs)-len(categories)))
        usedm={p[3] for p in pairs}
        useds={p[1] for p in pairs}
        for cat in categories:
            main_options=[m for mc,m in all_mains if mc==cat and m not in usedm]
            random.shuffle(main_options)
            soup_options=[(sc,s) for sc,s in all_soups if s not in useds]
            random.shuffle(soup_options)
            options=[(sc,s,cat,m) for m in main_options[:35] for sc,s in soup_options[:35]
                     if compatible(sc,s,cat,m)]
            if not options:raise ValueError('Pro kategorii '+cat+' není dostupná vhodná dvojice.')
            choice=self.weighted_choice(options,'pair',lambda p:pair_key(p[1],p[3]))
            pairs.append(choice);useds.add(choice[1]);usedm.add(choice[3])
        random.shuffle(pairs)
        return [{'soup':s,'main':m,'category':mc} for _,s,mc,m in pairs]

    def add_second_mains(self,days,used_main):
        """Druhý oběd má stejnou polévku, ale odlišné hlavní jídlo."""
        used=set(used_main)|{d.get('main') for d in days if not d.get('closed')}
        for day_index,d in enumerate(days):
            if d.get('closed'):continue
            choices=[(cat,m) for (kind,cat),items in self.groups.items() if kind=='main'
                     for m in items if m not in used and self.allowed_item(m,'main')
                     and not (day_index==0 and self.main_category_family(cat)==self.main_category_family(d.get('category','')))
                     and self.allowed_pair(d['soup'],m)
                     and not (self.rules['avoid_fish_pair'] and cat.startswith('RYBY') and 'rybi' in self.normalize(d['soup']))
                     and not (self.rules['avoid_legume_pair'] and cat.startswith('LUŠTĚNINOVÁ') and
                         any(d['soup'] in items2 for (kind2,cat2),items2 in self.groups.items() if kind2=='soup' and 'LUŠTĚNINOVÉ' in cat2))]
            if not choices:raise ValueError('Nedostatek dalších vhodných jídel pro Oběd 2.')
            cat,m=self.weighted_choice(choices,'main',lambda x:x[1])
            d['main2']=m;d['category2']=cat;used.add(m)
        return days

    def align_saved_lunch_count(self, days):
        """Historický jídelníček zobrazit v počtu obědů, ve kterém byl uložen."""
        self.lunch_count.set(2 if any(d.get('main2') for d in days if not d.get('closed')) else 1)

    def open_selected_week(self):
        """Při spuštění a změně data bez dotazů otevře uložený týden."""
        try:
            monday=week_monday(self.date.get())
            existing=next((h for h in self.history if h.get('week')==str(monday)),None)
            if existing:
                self.current=copy.deepcopy(existing)
                self.align_saved_lunch_count(existing['days'])
                self.parked_days.clear()
                self.sync_days(existing['days'])
                self.display(existing['days'])
                self.status.set('Načten uložený týden. Můžete upravovat jídla i dny; historie se změní až po schválení.')
            else:
                self.current=None
                self.generate()
        except (ValueError,KeyError) as exc:
            messagebox.showerror('Načtení týdne',str(exc))

    def generate(self):
        try:
            monday = week_monday(self.date.get())
            if monday < datetime.date.today() - datetime.timedelta(days=7):
                raise ValueError('Zvolte současný nebo budoucí týden.')
            lock_main, lock_soup = int(self.lock_main.get()), int(self.lock_soup.get())
            if not 1 <= lock_main <= 30 or not 1 <= lock_soup <= 20:
                raise ValueError('Neplatná délka blokování.')
            existing = next((h for h in self.history if h['week'] == str(monday)), None)
            if existing:
                # Zobrazit uložený týden, ale dovolit vytvořit nový návrh po potvrzení.
                if not messagebox.askyesno('Schválený týden',
                    'Tento týden už je uložen v historii.\n\n'
                    'Chcete pro něj vygenerovat NOVÝ návrh?\n'
                    'Původní uložený jídelníček zůstane zachován, dokud změnu neschválíte.'):
                    self.current=copy.deepcopy(existing)
                    self.align_saved_lunch_count(existing['days'])
                    self.parked_days.clear()
                    self.sync_days(existing['days'])
                    self.display(existing['days'])
                    self.status.set('Načten schválený týden k úpravám. Změny se uloží až po schválení.')
                    return
                # Při tvorbě nového návrhu zůstane uložený týden nedotčen.
                self.current=None
            used_main, used_soup = set(), set()
            for h in self.history:
                if h.get('week')==str(monday):
                    continue  # Při novém návrhu neblokovat jídla z právě upravovaného týdne.
                try: delta = (monday - datetime.date.fromisoformat(h['week'])).days
                except (ValueError, KeyError): continue
                if 0 <= delta < lock_main * 7:
                    used_main.update(d.get(k) for d in h['days'] if not d.get('closed') for k in ('main','main2') if d.get(k))
                if 0 <= delta < lock_soup * 7:
                    used_soup.update(d['soup'] for d in h['days'] if not d.get('closed'))
            if self.current and self.current['week'] == str(monday):
                used_main.update(d.get(k) for d in self.current['days'] if not d.get('closed') for k in ('main','main2') if d.get(k))
                used_soup.update(d['soup'] for d in self.current['days'] if not d.get('closed'))
            def pool(kind, category):
                return [x for x in self.groups.get((kind,category),[]) if x not in (used_main if kind == 'main' else used_soup) and self.allowed_item(x,kind)]
            cats = [cat for kind,cat in self.groups if kind == 'main']
            fish = next(c for c in cats if c.startswith('RYBY'))
            legumes = next(c for c in cats if c.startswith('LUŠTĚNINOVÁ'))
            meatless = next(c for c in cats if c.startswith('BEZMASÁ'))
            sweet = next(c for c in cats if c.startswith('SLADKÁ'))
            r=self.rules
            previous_sweet = any(0 < (monday - datetime.date.fromisoformat(h['week'])).days < r['sweet_gap_weeks']*7 and any(d.get('category') == sweet for d in h['days']) for h in self.history)
            n_days=sum(v.get() for v in self.active_days)
            if n_days==0:raise ValueError('Musí být vybrán alespoň jeden den vaření.')
            selected = [fish]*r['fish'] + [legumes]*r['legumes'] + [meatless]*r['meatless']
            if self.active_days[0].get():
                required=legumes if self.monday_required_category(monday)=='LUŠTĚNINOVÁ' else fish
                if required not in selected:selected.insert(0,required)
            if len(selected)>n_days:raise ValueError('Počet povinných kategorií přesahuje počet dní vaření. Upravte pravidla jídelny.')
            sweet_limit = 0 if previous_sweet else r['sweet_max']
            if sweet_limit and len(selected)<n_days and random.random()<.5:
                selected.append(sweet)
            remaining = [c for c in cats if c not in (fish,legumes,meatless,sweet)]
            # Remaining days can include extra fish, legumes or meatless, but not sweet.
            remaining += [fish,legumes,meatless]
            while len(selected)<n_days:
                candidates=[c for c in remaining if len(pool('main',c))>selected.count(c)]
                if not candidates: raise ValueError('Nedostatek jídel pro požadovaná pravidla.')
                selected.append(random.choice(candidates))
            last_problem=None
            for attempt in range(45):
                try:
                    days=self.build_candidate(selected,used_main,used_soup,fish,legumes,r)
                    preview=iter(days)
                    test=[next(preview) if v.get() else {'closed':True,'soup':'','main':'','category':''}
                          for v in self.active_days]
                    self.arrange_monday(test,monday)
                    if self.lunch_count.get()==2:self.add_second_mains(test,used_main)
                    last_problem=self.validate_days(test)
                    if not last_problem:break
                except ValueError as exc:
                    last_problem=str(exc)
            else:
                raise ValueError('Nepodařilo se sestavit jídelníček ani po opakovaných pokusech.\\n'
                                 'Důvod: '+str(last_problem)+'\\n'
                                 'Zkuste upravit povinné kombinace, délku blokování nebo počet dní.')
            days=test
            problem=self.validate_days(days)
            if problem: raise ValueError('Návrh nesplnil pravidla: '+problem+' Zkuste Generuj další.')
            self.parked_days.clear()
            self.current = {'week':str(monday),'days':days}
            self.display(days)
            self.status.set('Nový návrh pro týden od '+monday.strftime('%d.%m.%Y')+'. Historie se změní až po schválení. Nutná kontrola vedoucí jídelny.')
        except (ValueError, StopIteration) as e:
            messagebox.showwarning('Nelze vygenerovat',str(e))

    def display(self, days):
        self.hide_meal_tip()
        monday = week_monday(self.date.get())
        friday = monday + datetime.timedelta(days=4)
        self.paper.configure(state='normal')
        self.paper.delete('1.0', 'end')
        self.click_ranges = []
        self.paper.insert('end', self.t('menu_title')+'\n', 'title')
        self.paper.insert('end', f'{monday:%d.%m.%Y} – {friday:%d.%m.%Y}\n', 'dates')
        for i, d in enumerate(days):
            day_date = monday + datetime.timedelta(days=i)
            self.paper.insert('end', f'{DAYS[i].upper()}  {day_date:%d.%m.%Y}'+(' (nevaří se)' if d.get('closed') else '')+'\n', 'day')
            if d.get('closed'):
                self.paper.insert('end','\n','soup')
                continue
            entries=[('soup',self.t('soup_label')+'  ','soup'),('main','Oběd 1:  ','main')]
            if self.lunch_count.get()==2:entries.append(('main2','Oběd 2:  ','main'))
            for kind, label, tag in entries:
                self.paper.insert('end', label, tag)
                start = self.paper.index('end-1c')
                self.paper.insert('end', d.get(kind,''), (tag,'editable'))
                end = self.paper.index('end-1c')
                if d.get(kind):self.click_ranges.append((start,end,i,kind))
                self.paper.insert('end', '\n', tag)
        self.paper.insert('end', '\nZměna jídelníčku vyhrazena.\n', 'foot')
        self.paper.configure(state='disabled')

    @staticmethod
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))

    def locate_meal(self, event):
        index = self.paper.index(f'@{event.x},{event.y}')
        return next(((day,kind) for start,end,day,kind in self.click_ranges
                     if self.paper.compare(index,'>=',start) and self.paper.compare(index,'<',end)),None)

    def hide_meal_tip(self, event=None):
        if self._meal_tip is not None:
            try:
                self._meal_tip.destroy()
            except tk.TclError:
                pass
        self._meal_tip = None
        self._meal_tip_item = None

    def hover_meal(self,event):
        item = self.locate_meal(event) if self.current else None
        self.paper.configure(cursor='hand2' if item else 'arrow')
        if not self.tips_enabled.get():
            self.hide_meal_tip()
            return
        if item == self._meal_tip_item:
            return
        self.hide_meal_tip()
        if item is None:
            return
        self._meal_tip_item = item
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        try:
            tip.wm_attributes('-topmost', True)
        except tk.TclError:
            pass
        text = 'Kliknutím změníte polévku' if item[1] == 'soup' else ('Kliknutím změníte Oběd 2' if item[1]=='main2' else 'Kliknutím změníte Oběd 1')
        tk.Label(tip, text=text, font=('Segoe UI', 10), bg='#fff8d8',
                 fg='#202020', relief='solid', borderwidth=1, padx=10, pady=6).pack()
        tip.update_idletasks()
        x = event.x_root + 15
        y = event.y_root + 18
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = min(x, screen_w - tip.winfo_reqwidth() - 8)
        y = min(y, screen_h - tip.winfo_reqheight() - 8)
        tip.wm_geometry(f'+{max(0,x)}+{max(0,y)}')
        self._meal_tip = tip

    def click_meal(self,event):
        self.hide_meal_tip()
        item=self.locate_meal(event)
        if not item:return
        if not self.ensure_editable_week():
            messagebox.showinfo('Nejdříve návrh','Nejdříve vytvořte nebo načtěte jídelníček.')
            return
        self.pick_meal(*item)

    @staticmethod
    def main_category_family(category):
        if category.startswith('LUŠTĚNINOVÁ'):return 'legumes'
        if category.startswith('RYBY'):return 'fish'
        return category

    def monday_required_category(self, monday):
        """Střídání dle posledního dřívějšího schváleného vařeného pondělí.

        Historie se prochází zpětně; zavřená pondělí a jiné kategorie
        nepřerušují posloupnost. Ruční výjimky zůstávají povolené.
        """
        monday_key = monday.isoformat()
        earlier = sorted((h for h in self.history
                          if h.get('week', '') < monday_key),
                         key=lambda h: h['week'], reverse=True)
        for record in earlier:
            days = record.get('days') or []
            if not days or days[0].get('closed'):
                continue
            category = days[0].get('category', '')
            if category.startswith('RYBY'):
                return 'LUŠTĚNINOVÁ'
            if category.startswith('LUŠTĚNINOVÁ'):
                return 'RYBY'
        return 'LUŠTĚNINOVÁ'

    def arrange_monday(self, days, monday):
        """Přesune hotovou dvojici jídel na pondělí, bez zásahu do polévky."""
        if not days or days[0].get('closed'):
            return days
        prefix=self.monday_required_category(monday)
        if days[0].get('category','').startswith(prefix):
            return days
        for idx in range(1,len(days)):
            d=days[idx]
            if not d.get('closed') and d.get('category','').startswith(prefix):
                days[0],days[idx]=days[idx],days[0]
                return days
        return days

    def validate_days(self, days):
        r=self.rules
        monday_day=days[0] if days else None
        days=[d for d in days if not d.get('closed')]
        if not days:return 'Není vybrán žádný den vaření.'
        if monday_day and not monday_day.get('closed'):
            prefix=self.monday_required_category(week_monday(self.date.get()))
            if not monday_day.get('category','').startswith(prefix):
                return 'Pondělí – Oběd 1: podle posledního schváleného pondělí má být '+('luštěninové' if prefix=='LUŠTĚNINOVÁ' else 'rybí')+' hlavní jídlo.'
        if any(not d.get('soup') or not d.get('main') for d in days):
            return 'V některém dni chybí polévka nebo hlavní jídlo.'
        mains=[d[k] for d in days for k in (('main','main2') if self.lunch_count.get()==2 else ('main',)) if d.get(k)]
        if self.lunch_count.get()==2 and any(not d.get('main2') for d in days):
            return 'V některém dni chybí Oběd 2.'
        if self.lunch_count.get()==2 and monday_day and not monday_day.get('closed') and self.main_category_family(monday_day.get('category2',''))==self.main_category_family(monday_day.get('category','')):
            return 'Pondělí: Oběd 2 musí být z jiné kategorie než Oběd 1 (nikoliv dvě ryby nebo dvě luštěninová jídla).'
        soups=[d['soup'] for d in days]
        if len(set(mains))<len(mains) or len(set(soups))<len(soups):
            return 'V jednom týdnu se nesmí opakovat stejné hlavní jídlo ani polévka.'
        cats=[c for kind,c in self.groups if kind=='main']
        for prefix,key in [('RYBY','fish'),('LUŠTĚNINOVÁ','legumes'),('BEZMASÁ','meatless')]:
            if sum(d.get(k,'').startswith(prefix) for d in days for k in (('category','category2') if self.lunch_count.get()==2 else ('category',)) if d.get(k))<r[key]:
                return 'Nedodržen minimální počet jídel v kategorii '+prefix+'.'
        if sum(d.get(k,'').startswith('SLADKÁ') for d in days for k in (('category','category2') if self.lunch_count.get()==2 else ('category',)) if d.get(k))>r['sweet_max']:
            return 'Překročen povolený počet sladkých jídel.'
        monday=week_monday(self.date.get())
        if any(d.get(k,'').startswith('SLADKÁ') for d in days for k in (('category','category2') if self.lunch_count.get()==2 else ('category',))):
            if any(0 < (monday-datetime.date.fromisoformat(h['week'])).days < r['sweet_gap_weeks']*7
                   and any(x.get('category','').startswith('SLADKÁ') for x in h['days']) for h in self.history):
                return 'Nedodržen odstup sladkých jídel od předchozího týdne.'
        for d in days:
            if r['avoid_legume_pair'] and any(d.get(k,'').startswith('LUŠTĚNINOVÁ') for k in (('category','category2') if self.lunch_count.get()==2 else ('category',))):
                if any(d['soup'] in items for (kind,cat),items in self.groups.items() if kind=='soup' and 'LUŠTĚNINOVÉ' in cat):
                    return 'Luštěninová polévka a luštěninové hlavní jídlo ve stejný den.'
            if r['avoid_fish_pair'] and any(d.get(k,'').startswith('RYBY') for k in (('category','category2') if self.lunch_count.get()==2 else ('category',))) and 'rybi' in self.normalize(d['soup']):
                return 'Rybí polévka a rybí hlavní jídlo ve stejný den.'
        for d in days:
            if any(not self.allowed_item(d[k],'main') for k in (('main','main2') if self.lunch_count.get()==2 else ('main',)) if d.get(k)) or not self.allowed_item(d['soup'],'soup'):
                return 'Jídlo je zakázáno vlastními pravidly TXT.'
            if any(not self.allowed_pair(d['soup'],d[k]) for k in (('main','main2') if self.lunch_count.get()==2 else ('main',)) if d.get(k)): return 'Zakázaná kombinace podle pravidel TXT.'
        for key,kind in [('require_main','main'),('require_soup','soup')]:
            for term in self.txt_rules[key]:
                if not any(self.matches(d[kind],term) or (kind=='main' and self.lunch_count.get()==2 and self.matches(d.get('main2',''),term)) for d in days):
                    return 'Chybí požadovaný výraz z TXT: '+term
        for soup_term,main_term in self.txt_rules['require_pair']:
            if not any(self.matches(d['soup'],soup_term) and (self.matches(d['main'],main_term) or (self.lunch_count.get()==2 and self.matches(d.get('main2',''),main_term))) for d in days):
                return 'Chybí požadovaná kombinace z TXT: '+soup_term+' | '+main_term
        return None

    def matches(self,name,term):
        return self.normalize(term) in self.normalize(name)

    def allowed_item(self,name,kind):
        return not any(self.matches(name,term) for term in self.txt_rules['ban_main' if kind=='main' else 'ban_soup'])

    def allowed_pair(self,soup,main):
        return not any(self.matches(soup,a) and self.matches(main,b) for a,b in self.txt_rules['ban_pair'])

    def monday_exception_messages(self, days):
        """Pouze upozornění na pondělní plánovací pravidla, ne zákaz editace."""
        if not days or days[0].get('closed'):
            return []
        day=days[0]
        required=self.monday_required_category(week_monday(self.date.get()))
        messages=[]
        if day.get('main') and not day.get('category','').startswith(required):
            messages.append('Oběd 1 má být podle lichého/sudého ISO týdne '+
                            ('luštěninový' if required=='LUŠTĚNINOVÁ' else 'rybí')+'.')
        if (self.lunch_count.get()==2 and day.get('main2') and
                self.main_category_family(day.get('category2',''))==
                self.main_category_family(day.get('category',''))):
            messages.append('Oběd 2 má být v pondělí z jiné skupiny než Oběd 1.')
        return messages

    def validate_manual_change(self, days):
        """Při jednotlivé výměně hlídat okamžité konflikty, nikoli týdenní kvóty.

        Pondělní střídání a odlišnost obou pondělních obědů jsou
        při ruční výměně pouze upozornění, nikoliv zákaz.
        """
        cooking=[d for d in days if not d.get('closed')]
        if not cooking:
            return 'Není vybrán žádný den vaření.'
        keys=('main','main2') if self.lunch_count.get()==2 else ('main',)
        category_keys=('category','category2') if self.lunch_count.get()==2 else ('category',)
        mains=[d.get(k,'') for d in cooking for k in keys if d.get(k)]
        soups=[d.get('soup','') for d in cooking if d.get('soup')]
        if len(mains)!=len(set(mains)) or len(soups)!=len(set(soups)):
            return 'V jednom týdnu se nesmí opakovat stejné hlavní jídlo ani polévka.'
        if sum(d.get(k,'').startswith('SLADKÁ') for d in cooking for k in category_keys)>self.rules['sweet_max']:
            return 'Překročen povolený počet sladkých jídel.'
        for d in cooking:
            for k in keys:
                main=d.get(k,'')
                if main and not self.allowed_item(main,'main'):
                    return 'Jídlo je zakázáno vlastními pravidly TXT.'
                if main and d.get('soup') and not self.allowed_pair(d['soup'],main):
                    return 'Zakázaná kombinace podle pravidel TXT.'
            soup=d.get('soup','')
            if soup and not self.allowed_item(soup,'soup'):
                return 'Polévka je zakázána vlastními pravidly TXT.'
            if soup and self.rules['avoid_legume_pair'] and any(d.get(k,'').startswith('LUŠTĚNINOVÁ') for k in category_keys):
                if any(soup in items for (kind,cat),items in self.groups.items() if kind=='soup' and 'LUŠTĚNINOVÉ' in cat):
                    return 'Luštěninová polévka a luštěninové hlavní jídlo ve stejný den.'
            if soup and self.rules['avoid_fish_pair'] and any(d.get(k,'').startswith('RYBY') for k in category_keys) and 'rybi' in self.normalize(soup):
                return 'Rybí polévka a rybí hlavní jídlo ve stejný den.'
        return None

    def pick_meal(self, day, kind):
        win=tk.Toplevel(self.root)
        win.title(f'Výběr jídla – {DAYS[day]}')
        original_kind=kind
        lookup_kind='main' if kind=='main2' else kind
        win.withdraw()
        win.update_idletasks()
        sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
        w=min(1040,max(620,sw-100))
        h=min(680,max(430,sh-150))
        win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}')
        win.minsize(min(620,w),min(430,h))
        win.transient(self.root)
        frame=ttk.Frame(win,padding=10);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=f'{DAYS[day]} – '+(self.t('pick_soup') if kind=='soup' else ('Oběd 2' if kind=='main2' else self.t('pick_main'))),font=('Segoe UI',14,'bold')).pack(anchor='w')
        query=tk.StringVar()
        ttk.Label(frame,text=self.t('search')).pack(anchor='w',pady=(5,2))
        entry=ttk.Entry(frame,textvariable=query,font=('Segoe UI',11));entry.pack(fill='x')
        ttk.Label(frame,text=self.t('category_hint'),wraplength=w-45).pack(anchor='w',pady=(3,5))
        area=ttk.Panedwindow(frame,orient='horizontal');area.pack(fill='both',expand=True)
        left=ttk.Frame(area);right=ttk.Frame(area)
        area.add(left,weight=1);area.add(right,weight=4)
        ttk.Label(left,text=self.t('categories'),font=('Segoe UI',10,'bold')).pack(anchor='w')
        cats=tk.Listbox(left,exportselection=False,font=('Segoe UI',10),width=22)
        cats.pack(fill='both',expand=True,padx=(0,8))
        ttk.Label(right,text=self.t('meals'),font=('Segoe UI',10,'bold')).pack(anchor='w')
        holder=ttk.Frame(right);holder.pack(fill='both',expand=True)
        box=tk.Listbox(holder,font=('Segoe UI',10),activestyle='dotbox',exportselection=False)
        scrollbar=ttk.Scrollbar(holder,orient='vertical',command=box.yview)
        box.configure(yscrollcommand=scrollbar.set)
        box.pack(side='left',fill='both',expand=True);scrollbar.pack(side='right',fill='y')
        sort_key=lambda item:(self.normalize(item[0]),self.normalize(item[1]))
        entries=sorted([(name,cat) for (k,cat),items in self.groups.items() if k==lookup_kind for name in items],key=sort_key)
        categories=['VŠECHNY']+sorted(set(cat for _,cat in entries),key=self.normalize)
        for cat in categories:cats.insert('end',self.t('all') if cat=='VŠECHNY' else cat)
        cats.selection_set(0)
        shown=[]
        current_name=self.current['days'][day].get(kind,'')
        def tags(name,cat):
            # Hledání je doslovné (bez diakritiky), bez synonym odvozených z kategorie.
            return self.normalize(name), self.normalize(cat)
        count=tk.StringVar()
        def refresh(*_):
            selected=cats.curselection()
            active=categories[selected[0]] if selected else 'VŠECHNY'
            terms=self.normalize(query.get()).split()
            shown[:]=[(name,cat) for name,cat in entries if (active=='VŠECHNY' or cat==active) and all(t in tags(name,cat)[0] or t in tags(name,cat)[1] for t in terms) and self.allowed_item(name,lookup_kind)]
            box.delete(0,'end')
            for name,cat in shown:box.insert('end',name)
            count.set(f'Nalezeno: {len(shown)} jídel')
            current_name=self.current['days'][day].get(kind,'') if self.current else ''
            for idx,(name,cat) in enumerate(shown):
                if name==current_name:
                    box.selection_set(idx);box.activate(idx);box.see(idx)
                    break
        def choose(*_):
            selected=box.curselection()
            if not selected:return
            name,cat=shown[selected[0]]
            candidate=[dict(d) for d in self.current['days']]
            candidate[day][kind]=name
            if kind in ('main','main2'):candidate[day]['category2' if kind=='main2' else 'category']=cat
            problem=self.validate_manual_change(candidate)
            if problem:
                messagebox.showwarning('Nesplněná pravidla',problem+'\nVyberte jiné jídlo.',parent=win)
                return
            # Ruční pondělní výjimku může vedoucí jídelny vědomě potvrdit.
            # Ostatní okamžité zákazy zůstávají závazné.
            if day==0 and kind in ('main','main2'):
                exceptions=self.monday_exception_messages(candidate)
                if exceptions and not messagebox.askyesno(
                        'Pondělní pravidlo – potvrzení výjimky',
                        'Navržená výměna nedodržuje pondělní pravidlo:\n\n'+
                        '\n'.join('• '+x for x in exceptions)+
                        '\n\nChcete přesto toto jídlo použít?\n'
                        'Výjimka se znovu zkontroluje při schválení týdne.',
                        parent=win):
                    return
            before=self.edit_snapshot()
            old=self.current['days'][day][kind]
            old_pairs={pair_key(self.current['days'][day]['soup'],self.current['days'][day][k]) for k in ('main','main2') if self.current['days'][day].get('soup') and self.current['days'][day].get(k)}
            self.current['days']=candidate
            if old!=name:
                self.learn(lookup_kind,old,-1)
                self.learn(lookup_kind,name,2)
                new_pairs={pair_key(candidate[day]['soup'],candidate[day][k]) for k in ('main','main2') if candidate[day].get('soup') and candidate[day].get(k)}
                for pk in old_pairs-new_pairs:self.learn('pair',pk,-1)
                for pk in new_pairs-old_pairs:self.learn('pair',pk,2)
            self.display(candidate)
            self.record_edit(before,'Výměna jídla – '+DAYS[day])
            self.status.set(f'Upraveno: {DAYS[day]} – '+('polévka' if kind=='soup' else ('Oběd 2' if kind=='main2' else 'Oběd 1'))+f' z „{old}“ na „{name}“. Týdenní pravidla se ověří při schválení; Zpět/Znovu je dostupné.')
            win.destroy()
        def generate_selection():
            if not shown:
                messagebox.showinfo('Žádný výběr','Aktuální filtr neobsahuje žádné jídlo.',parent=win);return
            # Preferujeme nabídku, která při výběru splní nastavená pravidla.
            valid=[]
            for idx,(name,cat) in enumerate(shown):
                candidate=[dict(d) for d in self.current['days']]
                candidate[day][kind]=name
                if kind in ('main','main2'):candidate[day]['category2' if kind=='main2' else 'category']=cat
                if not self.validate_manual_change(candidate):valid.append(idx)
            if not valid:
                messagebox.showinfo('Bez vhodného jídla','V aktuálním filtru není položka splňující pravidla. Zkuste jinou kategorii.',parent=win);return
            # Náhodný výběr dává přednost dodržení pondělního pravidla,
            # ale ruční potvrzení jiné položky je možné.
            if day==0 and kind in ('main','main2'):
                preferred=[]
                for idx in valid:
                    name,cat=shown[idx]
                    candidate=[dict(d) for d in self.current['days']]
                    candidate[day][kind]=name
                    candidate[day]['category2' if kind=='main2' else 'category']=cat
                    if not self.monday_exception_messages(candidate):preferred.append(idx)
                if preferred:valid=preferred
            idx=random.choice(valid)
            box.selection_clear(0,'end');box.selection_set(idx);box.activate(idx);box.see(idx);box.focus_set()
            count.set(f'Nalezeno: {len(shown)} jídel – náhodně označeno: {shown[idx][0]}')
        def rename_selected():
            selected=box.curselection()
            if not selected:
                messagebox.showinfo('Přejmenování','Nejdříve označte jídlo v seznamu.',parent=win);return
            old,cat=shown[selected[0]]
            # Vlastní široký dialog namísto úzkého simpledialog.askstring.
            # Kategorie není součástí názvu a zůstává v katalogu samostatně.
            dialog=tk.Toplevel(win)
            dialog.title(self.ui['rename_meal'])
            dialog.transient(win)
            dialog.resizable(True,False)
            dialog.geometry('780x175')
            dialog.minsize(560,175)
            dialog.columnconfigure(0,weight=1)
            dialog.rowconfigure(1,weight=1)
            ttk.Label(dialog,text='Nový název jídla (bez kategorie):').grid(row=0,column=0,sticky='w',padx=18,pady=(17,6))
            value=tk.StringVar(value=old)
            field=ttk.Entry(dialog,textvariable=value,font=('Segoe UI',11))
            field.grid(row=1,column=0,sticky='ew',padx=18,pady=(0,12))
            actions=ttk.Frame(dialog)
            actions.grid(row=2,column=0,sticky='e',padx=18,pady=(0,15))
            result={'value':None}
            def finish(accept):
                if accept:result['value']=value.get()
                dialog.destroy()
            ttk.Button(actions,text='Uložit',command=lambda:finish(True)).pack(side='left',padx=(0,8))
            ttk.Button(actions,text=self.ui['cancel'],command=lambda:finish(False)).pack(side='left')
            dialog.bind('<Return>',lambda e:finish(True))
            dialog.bind('<Escape>',lambda e:finish(False))
            dialog.protocol('WM_DELETE_WINDOW',lambda:finish(False))
            dialog.update_idletasks()
            dialog.geometry(f'+{max(0,win.winfo_rootx()+(win.winfo_width()-dialog.winfo_width())//2)}+{max(0,win.winfo_rooty()+(win.winfo_height()-dialog.winfo_height())//2)}')
            field.focus_set()
            field.selection_range(0,'end')
            dialog.grab_set()
            win.wait_window(dialog)
            new=result['value']
            if new is None:return
            new=new.strip()
            if not new or '\n' in new or '\r' in new:
                messagebox.showwarning('Neplatný název','Zadejte neprázdný název na jednom řádku.',parent=win);return
            if new==old:return
            if any(new in items for (k,_),items in self.groups.items() if k==lookup_kind):
                messagebox.showwarning('Duplicita','Jídlo s tímto názvem již existuje.',parent=win);return
            # Zachováme původní identifikátor z katalogu, takže opakované přejmenování nepřidává řetězce náhrad.
            section='polevky' if lookup_kind=='soup' else 'hlavni'
            if not self.names_cfg.has_section(section):self.names_cfg.add_section(section)
            original=next((key for key,value in self.names_cfg.items(section) if value==old),old)
            before=self.edit_snapshot()
            self.names_cfg.set(section,original,new)
            save_names(self.names_cfg)
            self.groups=rename_catalog(load_catalog(),self.names_cfg)
            # Přejmenování promítneme i do aktuálního rozpracovaného týdne.
            for d in self.current['days']:
                for field in (('soup',) if lookup_kind=='soup' else ('main','main2')):
                    if d.get(field)==old:d[field]=new
            self.display(self.current['days'])
            self.record_edit(before,'Přejmenování jídla')
            entries[:]=sorted([(new if name==old else name,c) for name,c in entries],key=sort_key)
            refresh()
            for idx,(name,c) in enumerate(shown):
                if name==new:box.selection_set(idx);box.see(idx);break
        def add_meal():
            selected=cats.curselection()
            if not selected or selected[0]==0:
                messagebox.showinfo('Přidat polévku' if lookup_kind=='soup' else 'Přidat hlavní jídlo','Nejdříve vlevo vyberte konkrétní kategorii.',parent=win)
                return
            category=categories[selected[0]]
            # Stejně široký dialog jako u přejmenování položky.
            dialog=tk.Toplevel(win)
            dialog.title('Přidat polévku' if lookup_kind=='soup' else 'Přidat hlavní jídlo')
            dialog.transient(win)
            dialog.resizable(True,False)
            dialog.geometry('780x175')
            dialog.minsize(560,175)
            dialog.columnconfigure(0,weight=1)
            dialog.rowconfigure(1,weight=1)
            ttk.Label(dialog,text=('Název nové polévky:' if lookup_kind=='soup' else 'Název nového hlavního jídla:')).grid(row=0,column=0,sticky='w',padx=18,pady=(17,6))
            value=tk.StringVar()
            field=ttk.Entry(dialog,textvariable=value,font=('Segoe UI',11))
            field.grid(row=1,column=0,sticky='ew',padx=18,pady=(0,12))
            actions=ttk.Frame(dialog)
            actions.grid(row=2,column=0,sticky='e',padx=18,pady=(0,15))
            result={'value':None}
            def finish(accept):
                if accept:result['value']=value.get()
                dialog.destroy()
            ttk.Button(actions,text='Uložit',command=lambda:finish(True)).pack(side='left',padx=(0,8))
            ttk.Button(actions,text=self.ui['cancel'],command=lambda:finish(False)).pack(side='left')
            dialog.bind('<Return>',lambda e:finish(True))
            dialog.bind('<Escape>',lambda e:finish(False))
            dialog.protocol('WM_DELETE_WINDOW',lambda:finish(False))
            dialog.update_idletasks()
            dialog.geometry(f'+{max(0,win.winfo_rootx()+(win.winfo_width()-dialog.winfo_width())//2)}+{max(0,win.winfo_rooty()+(win.winfo_height()-dialog.winfo_height())//2)}')
            field.focus_set()
            dialog.grab_set()
            win.wait_window(dialog)
            name=result['value']
            if name is None:return
            name=name.strip()
            if not name or any(c in name for c in '\r\n') or name.startswith('- '):
                messagebox.showwarning('Neplatný název','Zadejte název na jednom řádku.',parent=win);return
            if any(self.normalize(name)==self.normalize(n) for (k,_),items in self.groups.items() if k==lookup_kind for n in items):
                messagebox.showwarning('Duplicita','Toto jídlo už v katalogu existuje.',parent=win);return
            if not messagebox.askyesno('Přidat polévku' if lookup_kind=='soup' else 'Přidat hlavní jídlo',f'Přidat „{name}“ do kategorie „{cats.get(selected[0])}“?',parent=win):return
            before=self.edit_snapshot()
            try:
                raw=CATALOG.read_text(encoding='utf-8-sig')
                lines=raw.splitlines(keepends=True)
                heading=('POLÉVKY' if lookup_kind=='soup' else 'HLAVNÍ JÍDLA')
                pattern=re.compile(r'^(POLÉVKY|HLAVNÍ JÍDLA)\s*[–-]\s*(.+?)\s*\((\d+)\)\s*$')
                header_idx=None;end_idx=None
                for i,line in enumerate(lines):
                    m=pattern.match(line.strip())
                    if m and m.group(1)==heading and m.group(2)==category:
                        header_idx=i
                        end_idx=i+1
                        while end_idx<len(lines) and lines[end_idx].startswith('- '):end_idx+=1
                        break
                if header_idx is None:raise ValueError('Kategorie nebyla nalezena v původním katalogu.')
                lines[header_idx]=re.sub(r'\(\d+\)(?=\s*$)',f'({end_idx-header_idx})',lines[header_idx].rstrip('\r\n'))+'\n'
                if end_idx and lines[end_idx-1] and not lines[end_idx-1].endswith(('\n','\r')):
                    lines[end_idx-1]+='\n'
                lines.insert(end_idx,'- '+name+'\n')
                temp=CATALOG.with_suffix('.txt.tmp')
                temp.write_text(''.join(lines),encoding='utf-8')
                temp.replace(CATALOG)
                self.groups=rename_catalog(load_catalog(),self.names_cfg)
                entries[:]=sorted([(n,c) for (k,c),items in self.groups.items() if k==lookup_kind for n in items],key=sort_key)
                query.set('')
                refresh()
                for idx,(n,c) in enumerate(shown):
                    if n==name and c==category:
                        box.selection_clear(0,'end');box.selection_set(idx);box.activate(idx);box.see(idx);break
                self.record_edit(before,'Přidání polévky do katalogu' if lookup_kind=='soup' else 'Přidání hlavního jídla do katalogu')
            except Exception as exc:
                try:
                    self.restore_edit_snapshot(before)
                    entries[:]=sorted([(n,c) for (k,c),items in self.groups.items() if k==lookup_kind for n in items],key=sort_key)
                    refresh()
                except Exception as rollback_exc:
                    messagebox.showerror('Obnova katalogu','Při obnově po chybě došlo k problému: '+str(rollback_exc),parent=win)
                messagebox.showerror('Přidání se nezdařilo',str(exc),parent=win)

        def delete_meal():
            selected=box.curselection()
            if not selected:
                messagebox.showinfo('Smazání','Nejdříve označte položku v seznamu.',parent=win)
                return
            name,category=shown[selected[0]]
            label='polévku' if lookup_kind=='soup' else 'hlavní jídlo'
            if not messagebox.askyesno('Smazat '+label,
                    f'Opravdu trvale odstranit „{name}“ z katalogu skolni_obedy.txt?\n\n'
                    'Smazání lze vrátit tlačítkem Zpět. Již uložené jídelníčky zůstanou zachované.',parent=win):
                return
            before=self.edit_snapshot()
            try:
                raw=CATALOG.read_text(encoding='utf-8-sig')
                lines=raw.splitlines(keepends=True)
                heading='POLÉVKY' if lookup_kind=='soup' else 'HLAVNÍ JÍDLA'
                pattern=re.compile(r'^(POLÉVKY|HLAVNÍ JÍDLA)\s*[–-]\s*(.+?)\s*\((\d+)\)\s*$')
                start=end=None
                for i,line in enumerate(lines):
                    m=pattern.match(line.strip())
                    if m and m.group(1)==heading and m.group(2)==category:
                        start=i
                        end=i+1
                        while end<len(lines) and lines[end].startswith('- '):end+=1
                        break
                if start is None:raise ValueError('Kategorie v katalogu nebyla nalezena.')
                section='polevky' if lookup_kind=='soup' else 'hlavni'
                original=next((key for key,value in self.names_cfg.items(section) if value==name),name) if self.names_cfg.has_section(section) else name
                matches=[i for i in range(start+1,end) if lines[i].removeprefix('- ').strip()==original]
                if len(matches)!=1:raise ValueError('Položku nelze jednoznačně dohledat v TXT; katalog zůstal beze změny.')
                del lines[matches[0]]
                header=lines[start].rstrip('\r\n')
                lines[start]=re.sub(r'\(\d+\)(?=\s*$)',f'({end-start-2})',header)+'\n'
                temp=CATALOG.with_suffix('.txt.tmp')
                temp.write_text(''.join(lines),encoding='utf-8')
                temp.replace(CATALOG)
                # Odstranění přejmenovacího aliasu zabraňuje zbytkům starého záznamu.
                if self.names_cfg.has_section(section) and self.names_cfg.has_option(section,original):
                    self.names_cfg.remove_option(section,original)
                    save_names(self.names_cfg)
                self.groups=rename_catalog(load_catalog(),self.names_cfg)
                entries[:]=sorted([(n,c) for (k,c),items in self.groups.items() if k==lookup_kind for n in items],key=sort_key)
                refresh()
                self.record_edit(before,'Smazání '+('polévky' if lookup_kind=='soup' else 'hlavního jídla')+' z katalogu')
                self.status.set('Položka „'+name+'“ byla odstraněna z katalogu. Zpět/Znovu obnoví i TXT.')
            except Exception as exc:
                try:
                    self.restore_edit_snapshot(before)
                    entries[:]=sorted([(n,c) for (k,c),items in self.groups.items() if k==lookup_kind for n in items],key=sort_key)
                    refresh()
                except Exception as rollback_exc:
                    messagebox.showerror('Obnova katalogu','Při obnově po chybě došlo k problému: '+str(rollback_exc),parent=win)
                messagebox.showerror('Mazání se nezdařilo',str(exc),parent=win)

        def rename_category(event=None):
            selected=cats.curselection()
            if not selected:return
            idx=selected[0]
            if idx==0:
                messagebox.showinfo('VŠECHNY','Tato položka je pevný filtr všech jídel, nikoliv název kategorie.',parent=win);return
            from tkinter import simpledialog
            old=categories[idx]
            new=simpledialog.askstring('Název kategorie','Nový název kategorie:',initialvalue=old,parent=win)
            if new is None:return
            new=new.strip()
            if not new or new in categories:
                messagebox.showwarning('Neplatný název','Kategorie musí mít jedinečný neprázdný název.',parent=win);return
            # Kategorie přejmenováváme jen pro zobrazení. Interní štítky musí zůstat
            # nezměněné kvůli pravidlům ryb, luštěnin a dalších skupin.
            category_aliases[old]=new
            save_category_aliases()
            cats.delete(idx);cats.insert(idx,new);cats.selection_set(idx)
        # Alias kategorie ukládáme odděleně, bez změny interních kategorií.
        alias_file=ROOT/'nazvy_kategorii.ini'
        alias_cfg=configparser.ConfigParser(interpolation=None)
        alias_cfg.optionxform=str
        if alias_file.exists():alias_cfg.read(alias_file,encoding='utf-8-sig')
        category_aliases=dict(alias_cfg.items(lookup_kind)) if alias_cfg.has_section(lookup_kind) else {}
        for i in range(1,len(categories)):
            if categories[i] in category_aliases:
                cats.delete(i);cats.insert(i,category_aliases[categories[i]])
        def save_category_aliases():
            if alias_cfg.has_section(lookup_kind):alias_cfg.remove_section(lookup_kind)
            alias_cfg.add_section(lookup_kind)
            for original in categories[1:]:
                # při dalších úpravách identifikujeme původní název
                display_name=cats.get(categories.index(original))
                if display_name!=original:alias_cfg.set(lookup_kind,original,display_name)
            with alias_file.open('w',encoding='utf-8') as f:alias_cfg.write(f)
        # Přejmenování kategorií: výběr stále používá interní originální hodnotu.
        def rename_category_safe(event=None):
            sel=cats.curselection()
            if not sel:return
            idx=sel[0]
            if idx==0:return
            from tkinter import simpledialog
            new=simpledialog.askstring('Přejmenovat kategorii','Nový zobrazovaný název:',initialvalue=cats.get(idx),parent=win)
            if new is None:return
            new=new.strip()
            if not new or (new in cats.get(0,'end') and new!=cats.get(idx)):
                messagebox.showwarning('Neplatný název','Zadejte jedinečný neprázdný název.',parent=win);return
            before=self.edit_snapshot()
            cats.delete(idx);cats.insert(idx,new);cats.selection_set(idx)
            save_category_aliases();refresh()
            self.record_edit(before,'Přejmenování kategorie')
        cats.bind('<<ListboxSelect>>',refresh)
        cats.bind('<Double-Button-1>',rename_category_safe)
        # Dvojklik do vyhledávacího pole smaže filtr; trace automaticky obnoví seznam.
        entry.bind('<Double-Button-1>', lambda event: query.set(''))
        query.trace_add('write',refresh)
        box.bind('<Double-Button-1>',choose)
        box.bind('<Return>',choose)
        bottom=ttk.Frame(frame);bottom.pack(fill='x',pady=(6,0))
        ttk.Label(bottom,textvariable=count).pack(side='left')
        def modal_history(redo=False):
            if not (self.edit_redo if redo else self.edit_undo):
                messagebox.showinfo('Změny','Žádná změna k '+('opakování.' if redo else 'vrácení.'),parent=win)
                return
            self.edit_step(redo)
            entries[:]=sorted([(n,c) for (k,c),items in self.groups.items() if k==lookup_kind for n in items],key=sort_key)
            chosen=categories[cats.curselection()[0]] if cats.curselection() else 'VŠECHNY'
            categories[:]=['VŠECHNY']+sorted({c for _,c in entries},key=self.normalize)
            alias_cfg.clear()
            if alias_file.exists():alias_cfg.read(alias_file,encoding='utf-8-sig')
            cats.delete(0,'end')
            for c in categories:
                label=alias_cfg.get(lookup_kind,c,fallback=c) if c!='VŠECHNY' else self.t('all')
                cats.insert('end',label)
            cats.selection_set(categories.index(chosen) if chosen in categories else 0)
            refresh()
        ttk.Button(bottom,text='↶ Zpět',command=lambda:modal_history(False)).pack(side='left',padx=(8,0))
        ttk.Button(bottom,text='↷ Znovu',command=lambda:modal_history(True)).pack(side='left',padx=(6,0))
        ttk.Button(bottom,text=self.t('cancel'),command=win.destroy).pack(side='right',padx=(6,0))
        ttk.Button(bottom,text=self.t('choose'),command=choose).pack(side='right',padx=(6,0))
        ttk.Button(bottom,text=self.t('random_pick'),command=generate_selection).pack(side='right',padx=(6,0))
        ttk.Button(bottom,text=self.t('rename_meal'),command=rename_selected).pack(side='right',padx=(6,0))
        ttk.Button(bottom,text='Přidat polévku' if lookup_kind=='soup' else 'Přidat hlavní jídlo',command=add_meal).pack(side='right',padx=(6,0))
        ttk.Button(bottom,text='Smazat polévku' if lookup_kind=='soup' else 'Smazat hlavní jídlo',command=delete_meal).pack(side='right',padx=(6,0))
        refresh();win.deiconify();win.grab_set();entry.focus_set()

    def approve(self):
        if not self.current:
            messagebox.showinfo('Informace', 'Nejdříve vygenerujte nebo načtěte týden.')
            return
        # Při ručním schvalování nekontrolujeme plánovací kvóty (ryby, luštěniny,
        # sladká jídla atd.). Ty platí pro automatické generování návrhů.
        # Schválit lze jen kompletní dny vaření; uzavřené dny jsou v pořádku.
        try:
            selected_week = str(week_monday(self.date.get()))
        except ValueError as exc:
            messagebox.showwarning('Datum týdne', str(exc))
            return
        if self.current.get('week') != selected_week:
            messagebox.showwarning('Nesouhlasí týden',
                'Zobrazený jídelníček nepatří k vybranému týdnu. Nejdříve načtěte správný týden.')
            return
        cooking = [d for d in self.current['days'] if not d.get('closed')]
        if not cooking or any(not d.get('soup') or not d.get('main') or
                              (self.lunch_count.get() == 2 and not d.get('main2')) for d in cooking):
            messagebox.showwarning('Neúplný jídelníček',
                'Nejdříve vyplňte polévku a všechna hlavní jídla ve dnech vaření.')
            return
        mains=[d.get(k) for d in cooking for k in (('main','main2') if self.lunch_count.get()==2 else ('main',)) if d.get(k)]
        soups=[d['soup'] for d in cooking]
        if len(mains)!=len(set(mains)) or len(soups)!=len(set(soups)):
            messagebox.showwarning('Duplicitní jídla',
                'V jednom týdnu se opakuje stejné hlavní jídlo nebo polévka. Opravte duplicitu před uložením.')
            return
        # Vědomá výjimka i při načtení staršího či zkopírovaného týdne.
        # Žádné tiché schválení pondělní odchylky.
        monday_exceptions=self.monday_exception_messages(self.current['days'])
        if monday_exceptions and not messagebox.askyesno(
                'Pondělní pravidlo – schválit výjimku',
                'Jídelníček nedodržuje pondělní pravidlo:\n\n'+
                '\n'.join('• '+x for x in monday_exceptions)+
                '\n\nChcete tuto výjimku vědomě schválit a pokračovat v uložení?'):
            return
        existing = next((h for h in self.history if h.get('week') == selected_week), None)
        # Nový týden ukládáme rovnou; pouze přepsání již uloženého týdne vyžaduje souhlas.
        if existing is not None and not messagebox.askyesno(
                'Přepsat uložený týden',
                'Tento týden je již uložen. Chcete přepsat existující jídelníček?'):
            return
        before=copy.deepcopy(self.history)
        if existing is not None:
            self.history=[h for h in self.history if h['week']!=self.current['week']]
        self.history.append(copy.deepcopy(self.current))
        try:
            self.write_history()
            self.save_history_state(before,('Úprava týdne ' if existing is not None else 'Uložení týdne ')+self.current['week'])
        except OSError as exc:
            self.history=before
            try:self.write_history()
            except OSError:pass
            messagebox.showerror('Ukládání historie','Týden se nepodařilo bezpečně uložit.\n'+str(exc))
            return
        if existing is not None:
            for old_day in existing['days']:
                if old_day.get('closed'):continue
                for old_field in ('main','main2'):
                    if old_day.get(old_field):
                        m=old_day[old_field];self.learning['main'][m]=max(-20,self.learning['main'].get(m,0)-1)
                if old_day.get('soup'):
                    soup=old_day['soup'];self.learning['soup'][soup]=max(-20,self.learning['soup'].get(soup,0)-1)
                if old_day.get('soup'):
                    for old_field in ('main','main2'):
                        if old_day.get(old_field):
                            key=pair_key(old_day['soup'],old_day[old_field]);self.learning['pair'][key]=max(-20,self.learning['pair'].get(key,0)-1)
        for d in self.current['days']:
            if d.get('closed'):continue
            for key_main in ('main','main2'):
                if d.get(key_main):
                    m=d[key_main];self.learning['main'][m]=min(20,self.learning['main'].get(m,0)+1)
            self.learning['soup'][d['soup']]=min(20,self.learning['soup'].get(d['soup'],0)+1)
            for main_field in ('main','main2'):
                if d.get('soup') and d.get(main_field):
                    key=pair_key(d['soup'],d[main_field])
                    self.learning['pair'][key]=min(20,self.learning['pair'].get(key,0)+1)
        try:
            temp=LEARNING.with_suffix('.json.tmp')
            temp.write_text(json.dumps(self.learning,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(LEARNING)
        except OSError as exc:
            messagebox.showwarning('Učení nelze uložit','Jídelníček je uložen, ale preference se neuložily.\\n'+str(exc))
        approved_week=self.current['week']
        # Ponechat pracovní kopii zobrazeného týdne: ihned po uložení lze dál upravovat.
        self.status.set('Uloženo: jídelníček pro týden '+approved_week+'. Historie změn umožňuje vrátit uložení; preference se průběžně učí.')

    def export(self):
        try:
            selected_week=str(week_monday(self.date.get()))
            if self.current and self.current.get('week')!=selected_week:
                messagebox.showwarning('Export CSV','Zobrazený jídelníček nepatří k vybranému týdnu. Načtěte správný týden.')
                return
            days = self.current['days'] if self.current else next((h['days'] for h in self.history if h['week']==selected_week),None)
            if not days:
                messagebox.showinfo('Informace','Nejdříve vygenerujte návrh.')
                return
            path = filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV pro Excel','*.csv')],initialfile='jidelni_listek.csv')
            if not path:return
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f,delimiter=';')
                writer.writerow(['Den','Polévka','Oběd 1','Oběd 2'] if self.lunch_count.get()==2 else ['Den','Polévka','Oběd 1'])
                for day,d in zip(DAYS,days):
                    if d.get('closed'):
                        writer.writerow([day,'','',''] if self.lunch_count.get()==2 else [day,'',''])
                    else:
                        writer.writerow([day,d.get('soup',''),d.get('main',''),d.get('main2','')] if self.lunch_count.get()==2 else [day,d.get('soup',''),d.get('main','')])
            self.status.set('Exportováno: '+path)
        except (OSError,UnicodeError,ValueError) as exc:
            messagebox.showerror('Export CSV','CSV se nepodařilo uložit.\n'+str(exc))

    def export_pdf(self):
        try:
            selected_week=str(week_monday(self.date.get()))
        except ValueError as exc:
            messagebox.showwarning('PDF',str(exc));return
        if self.current and self.current.get('week')!=selected_week:
            messagebox.showwarning('PDF','Zobrazený jídelníček nepatří k vybranému týdnu. Načtěte správný týden.');return
        days=self.current['days'] if self.current else next((h['days'] for h in self.history if h['week']==str(week_monday(self.date.get()))),None)
        if not days:
            messagebox.showinfo('PDF','Nejdříve vygenerujte nebo načtěte jídelníček.');return
        if not any(not d.get('closed') for d in days):
            messagebox.showwarning('PDF','Není vybrán žádný den vaření.');return
        if any(not d.get('closed') and (not d.get('soup') or not d.get('main') or (self.lunch_count.get()==2 and not d.get('main2'))) for d in days):
            messagebox.showwarning('PDF','Některý aktivní den nemá polévku nebo hlavní jídlo. Doplňte jej.');return
        try:
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from xml.sax.saxutils import escape
            fonts=[Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/segoeui.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
            bolds=[Path('C:/Windows/Fonts/arialbd.ttf'),Path('C:/Windows/Fonts/segoeuib.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')]
            regular=next((x for x in fonts if x.exists()),None)
            bold=next((x for x in bolds if x.exists()),None)
            if not regular or not bold:raise RuntimeError('Nenalezen font s podporou češtiny.')
            pdfmetrics.registerFont(TTFont('SkolniRegular',str(regular)))
            pdfmetrics.registerFont(TTFont('SkolniBold',str(bold)))
            target=filedialog.asksaveasfilename(title='Uložit jídelní lístek jako PDF',defaultextension='.pdf',filetypes=[('PDF soubory','*.pdf')],initialfile='Jidelni_listek_'+week_monday(self.date.get()).strftime('%Y-%m-%d')+'.pdf')
            if not target:return
            monday=week_monday(self.date.get());friday=monday+datetime.timedelta(days=4)
            doc=SimpleDocTemplate(target,pagesize=A4,rightMargin=35,leftMargin=35,topMargin=35,bottomMargin=35)
            title=ParagraphStyle('title',fontName='SkolniBold',fontSize=19,leading=25,alignment=TA_CENTER,spaceAfter=6)
            period=ParagraphStyle('period',fontName='SkolniRegular',fontSize=11,leading=16,alignment=TA_CENTER,spaceAfter=20)
            daystyle=ParagraphStyle('day',fontName='SkolniBold',fontSize=11,leading=16,spaceAfter=7)
            line=ParagraphStyle('line',fontName='SkolniRegular',fontSize=10.5,leading=16,leftIndent=12,spaceAfter=7)
            story=[Paragraph(escape(self.t('menu_title')),title),Paragraph(f'{monday:%d.%m.%Y} – {friday:%d.%m.%Y}',period)]
            for i,d in enumerate(days):
                date=monday+datetime.timedelta(days=i)
                header=[HRFlowable(width='100%',thickness=.7,color=colors.grey,spaceAfter=7),Paragraph(f'{DAYS[i]} {date:%d.%m.%Y}'+(' (nevaří se)' if d.get('closed') else ''),daystyle)]
                if not d.get('closed'):
                    header += [Paragraph('Polévka – '+escape(d['soup']),line),Paragraph('Oběd 1 – '+escape(d['main']),line)]
                    if self.lunch_count.get()==2:header.append(Paragraph('Oběd 2 – '+escape(d.get('main2','')),line))
                header.append(Spacer(1,5))
                story.append(KeepTogether(header))
            story.append(HRFlowable(width='100%',thickness=.7,color=colors.grey))
            doc.build(story)
            self.status.set('PDF uložen: '+target)
            messagebox.showinfo('PDF','Jídelní lístek byl uložen:\n'+target)
        except ImportError:
            messagebox.showerror('Chybí knihovna','Pro export PDF je potřeba nainstalovat ReportLab.\nV příkazovém řádku spusťte: py -m pip install reportlab')
        except Exception as e:
            messagebox.showerror('PDF','PDF se nepodařilo vytvořit: '+str(e))

    def edit_rules(self):
        win=tk.Toplevel(self.root)
        win.title('Pravidla jídelny')
        win.geometry('540x420')
        win.transient(self.root)
        win.grab_set()
        frame=ttk.Frame(win,padding=18); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Vlastní pravidla pro generování',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=(0,12))
        labels=[('fish','Minimálně rybích hlavních jídel týdně'),('legumes','Minimálně luštěninových hlavních jídel týdně'),('meatless','Minimálně bezmasých slaných jídel týdně'),('sweet_max','Maximálně sladkých hlavních jídel týdně'),('sweet_gap_weeks','Odstup sladkých jídel mezi týdny (týdny)')]
        values={}
        for key,label in labels:
            row=ttk.Frame(frame);row.pack(fill='x',pady=4)
            ttk.Label(row,text=label).pack(side='left')
            var=tk.IntVar(value=self.rules[key]);values[key]=var
            ttk.Spinbox(row,from_=0,to=5,textvariable=var,width=5).pack(side='right')
        for key,label in [('avoid_legume_pair','Nekombinovat luštěninovou polévku s luštěninovým hlavním jídlem'),('avoid_fish_pair','Nekombinovat rybí polévku s rybím hlavním jídlem')]:
            var=tk.BooleanVar(value=self.rules[key]);values[key]=var
            ttk.Checkbutton(frame,text=label,variable=var).pack(anchor='w',pady=5)
        ttk.Label(frame,text='Tato nastavení nejsou kontrolou ministerských norem ani spotřebního koše.',wraplength=480).pack(anchor='w',pady=10)
        def save():
            try:
                data={k:v.get() for k,v in values.items()}
                if any(type(data[k]) is not int or not 0<=data[k]<=5 for k,_ in labels): raise ValueError('Zadejte celá čísla od 0 do 5.')
                if data['fish']+data['legumes']+data['meatless']>5: raise ValueError('Součet minimálních počtů přesahuje pět dní.')
                before=self.edit_snapshot()
                RULES.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
                self.rules=data
                # Změna pravidel nesmí odpojit právě zobrazený jídelníček.
                self.record_edit(before,'Změna pravidel jídelny')
                self.status.set('Provedeno: uložena pravidla jídelny. Zpět/Znovu je dostupné; pro nový návrh klikněte na Generuj další.')
                win.destroy()
            except (ValueError,tk.TclError,OSError) as exc: messagebox.showerror('Chyba pravidel',str(exc),parent=win)
        ttk.Button(frame,text='Uložit pravidla',command=save).pack(anchor='e',pady=6)

    def edit_txt_rules(self):
        win=tk.Toplevel(self.root);win.title('Vlastní pravidla TXT');win.geometry('820x650')
        win.transient(self.root);win.grab_set()
        frame=ttk.Frame(win,padding=14);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Vlastní pravidla – jedno pravidlo na řádek',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Podporované příkazy: ZAKAZ_HLAVNI, ZAKAZ_POLEVKA, ZAKAZ_KOMBINACE, VYZADUJ_HLAVNI, VYZADUJ_POLEVKA, VYZADUJ_KOMBINACE.\nHodnoty jsou hledané podřetězce bez ohledu na diakritiku. Kombinace: polévka | hlavní. # je komentář.',wraplength=770).pack(anchor='w',pady=8)
        editor=tk.Text(frame,wrap='word',font=('Consolas',11),undo=True)
        editor.pack(fill='both',expand=True)
        if TXT_RULES.exists(): editor.insert('1.0',TXT_RULES.read_text(encoding='utf-8-sig'))
        else: editor.insert('1.0','# Příklady – odkomentujte podle potřeby:\n# ZAKAZ_HLAVNI = smažený sýr\n# ZAKAZ_POLEVKA = frankfurtská\n# ZAKAZ_KOMBINACE = čočková | čočka\n# VYZADUJ_HLAVNI = zeleninové\n# VYZADUJ_KOMBINACE = vývar | kuřecí\n')
        buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=10)
        def load():
            path=filedialog.askopenfilename(parent=win,filetypes=[('Textové soubory','*.txt')])
            if path:
                try:
                    editor.delete('1.0','end');editor.insert('1.0',Path(path).read_text(encoding='utf-8-sig'))
                except Exception as e:messagebox.showerror('Chyba čtení',str(e),parent=win)
        def save():
            try:
                content=editor.get('1.0','end-1c')
                parsed=parse_txt_rules(content)
                # Kontrola před uložením: chybný TXT nikdy nepřepíše funkční pravidla.
                before=self.edit_snapshot()
                TXT_RULES.write_text(content,encoding='utf-8')
                self.txt_rules=parsed  # Zobrazený týden zůstává editovatelný.
                self.record_edit(before,'Úprava vlastních pravidel TXT')
                self.status.set('Provedeno: vlastní pravidla TXT zkontrolována a uložena. Zpět/Znovu je dostupné; vygenerujte nový návrh.')
                messagebox.showinfo('Pravidla uložena',
                    f'Kontrola proběhla v pořádku.\\nNačteno {sum(map(len,parsed.values()))} pravidel.\\n\\nPravidla budou platit i po dalším spuštění.',parent=win)
                win.destroy()
            except ValueError as e:
                import re
                match=re.search(r'Řádek (\d+)',str(e))
                if match:
                    row=int(match.group(1))
                    editor.tag_remove('chyba','1.0','end')
                    editor.tag_add('chyba',f'{row}.0',f'{row}.end')
                    editor.tag_config('chyba',background='#ffdddd')
                    editor.see(f'{row}.0')
                    editor.mark_set('insert',f'{row}.0')
                    editor.focus_set()
                messagebox.showerror('Opravte vlastní pravidla',str(e)+'\\n\\nPravidla zatím NEBYLA uložena.',parent=win)
            except OSError as e:
                messagebox.showerror('Nelze uložit soubor',str(e),parent=win)
        ttk.Button(buttons,text='Načíst z TXT…',command=load).pack(side='left')
        ttk.Button(buttons,text='Uložit a použít',command=save).pack(side='right')

    def t(self,key):
        return self.ui.get(key,UI_DEFAULTS.get(key,key))

    def edit_ui_texts(self):
        win=tk.Toplevel(self.root);win.title(self.t('texts'));win.geometry('850x570')
        win.transient(self.root)
        outer=ttk.Frame(win,padding=12);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Upravte texty tlačítek, nadpisů, kategorií a dialogů. Změny se projeví po restartu programu.').pack(anchor='w',pady=(0,8))
        frame=ttk.Frame(outer);frame.pack(fill='both',expand=True)
        canvas=tk.Canvas(frame,highlightthickness=0);scroll=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
        inside=ttk.Frame(canvas);inside.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0,0),window=inside,anchor='nw');canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        variables={}
        for row,(key,default) in enumerate(UI_DEFAULTS.items()):
            ttk.Label(inside,text=key,width=22).grid(row=row,column=0,sticky='w',padx=4,pady=3)
            var=tk.StringVar(value=self.t(key));variables[key]=var
            ttk.Entry(inside,textvariable=var,width=65).grid(row=row,column=1,sticky='ew',padx=4,pady=3)
        def save():
            values={key:var.get().strip() or UI_DEFAULTS[key] for key,var in variables.items()}
            before=self.edit_snapshot()
            save_ui_texts(values);self.ui=values
            self.record_edit(before,'Úprava textů programu')
            messagebox.showinfo('Uloženo','Texty uloženy do nastaveni_textu.ini. Pro úplné použití restartujte program.',parent=win)
            win.destroy()
        ttk.Button(outer,text='Uložit nastavení',command=save).pack(anchor='e',pady=8)

    def load_history_journal(self):
        if not HISTORY_UNDO.exists():return [], []
        try:
            data=json.loads(HISTORY_UNDO.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError('Nesprávný formát')
            return data.get('undo',[])[-30:],data.get('redo',[])[-30:]
        except (ValueError,OSError,TypeError) as exc:
            messagebox.showwarning('Historie změn',
                'Nepodařilo se načíst seznam kroků Zpět/Znovu.\n'
                'Samotná historie jídelníčků zůstala zachována.\n'+str(exc))
            return [], []

    def save_history_state(self, previous, action):
        # Uchováme kopii před změnou, aby šlo obnovit i smazaný týden.
        self.history_undo.append({'action':action,'history':copy.deepcopy(previous)})
        self.history_undo=self.history_undo[-30:]
        self.history_redo.clear()
        self.write_history_journal()

    def write_history_journal(self):
        data={'undo':self.history_undo[-30:],'redo':self.history_redo[-30:]}
        temp=HISTORY_UNDO.with_suffix('.json.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(HISTORY_UNDO)

    def write_history(self):
        temp=HISTORY.with_suffix('.json.tmp')
        temp.write_text(json.dumps(self.history,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(HISTORY)

    def history_step(self, redo=False):
        source=self.history_redo if redo else self.history_undo
        dest=self.history_undo if redo else self.history_redo
        if not source:
            messagebox.showinfo('Historie změn','Žádná změna k '+('opakování.' if redo else 'vrácení.'))
            return False
        entry=source[-1]
        old_history=copy.deepcopy(self.history)
        old_undo=copy.deepcopy(self.history_undo)
        old_redo=copy.deepcopy(self.history_redo)
        source.pop()
        dest.append({'action':entry.get('action','Změna historie'),
                     'history':old_history})
        dest[:]=dest[-30:]
        self.history=copy.deepcopy(entry['history'])
        try:
            self.write_history()
            self.write_history_journal()
        except (OSError,ValueError,KeyError) as exc:
            self.history=old_history
            self.history_undo=old_undo
            self.history_redo=old_redo
            try:self.write_history()
            except OSError:pass
            messagebox.showerror('Nepodařilo se vrátit změnu',str(exc))
            return False
        self.status.set(('Historie – znovu provedeno: ' if redo else 'Historie – vráceno: ')+entry.get('action','změna historie')+'.')
        return True

    def show_history(self):
        win=tk.Toplevel(self.root);win.title(self.t('history_title'))
        sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
        w=min(960,sw-80);h=min(600,sh-120)
        win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}')
        win.transient(self.root)
        outer=ttk.Frame(win,padding=12);outer.pack(fill='both',expand=True)
        area=ttk.Panedwindow(outer,orient='horizontal');area.pack(fill='both',expand=True)
        left=ttk.Frame(area);right=ttk.Frame(area);area.add(left,weight=1);area.add(right,weight=3)
        ttk.Label(left,text=self.t('history_list')).pack(anchor='w')
        items=[]
        weeks=tk.Listbox(left,exportselection=False,width=25);weeks.pack(fill='both',expand=True,padx=(0,10))
        def reload_items(preferred=None):
            nonlocal items
            items=sorted(self.history,key=lambda x:x['week'],reverse=True)
            weeks.delete(0,'end')
            for hitem in items:
                start=datetime.date.fromisoformat(hitem['week']);end=start+datetime.timedelta(days=4)
                weeks.insert('end',f'{start:%d.%m.%Y} – {end:%d.%m.%Y}')
            if items:
                pos=next((i for i,x in enumerate(items) if x['week']==preferred),0)
                weeks.selection_set(pos)
                refresh()
            else:
                preview.configure(state='normal')
                preview.delete('1.0','end')
                preview.insert('1.0','Historie je prázdná. Smazané týdny můžete vrátit tlačítkem Zpět.')
                preview.configure(state='disabled')
        ttk.Label(right,text=self.t('history_preview')).pack(anchor='w')
        preview=tk.Text(right,wrap='word',font=('Segoe UI',11),state='disabled')
        preview.pack(fill='both',expand=True)
        def refresh(*_):
            sel=weeks.curselection()
            if not sel:return
            hitem=items[sel[0]];start=datetime.date.fromisoformat(hitem['week'])
            lines=[self.t('menu_title'),f'{start:%d.%m.%Y} – {start+datetime.timedelta(days=4):%d.%m.%Y}','']
            for i,day in enumerate(hitem['days']):
                lines.append(f'{DAYS[i]}  {start+datetime.timedelta(days=i):%d.%m.%Y}'+(' (nevaří se)' if day.get('closed') else ''))
                if not day.get('closed'):
                    lines.extend([self.t('soup_label')+' '+day['soup'],'Oběd 1: '+day['main']])
                    if day.get('main2'):lines.append('Oběd 2: '+day['main2'])
                lines.append('')
            preview.configure(state='normal');preview.delete('1.0','end');preview.insert('1.0','\n'.join(lines));preview.configure(state='disabled')
        weeks.bind('<<ListboxSelect>>',refresh);reload_items()
        buttons=ttk.Frame(outer);buttons.pack(fill='x',pady=(10,0))
        def load_selected():
            sel=weeks.curselection()
            if not sel:
                messagebox.showinfo('Historie','Nejdříve vyberte uložený týden.',parent=win)
                return
            hitem=copy.deepcopy(items[sel[0]])
            self.date.set(datetime.date.fromisoformat(hitem['week']).strftime('%d.%m.%Y'))
            self.current=hitem
            self.align_saved_lunch_count(hitem['days'])
            self.parked_days.clear()
            self.sync_days(hitem['days'])
            self.display(hitem['days'])
            self.status.set('Načten uložený týden. Můžete upravit jídla; historie se změní až po schválení.')
            win.destroy()

        def copy_to_another_week():
            sel=weeks.curselection()
            if not sel:
                messagebox.showinfo('Historie','Nejdříve vyberte uložený týden.',parent=win)
                return
            source=copy.deepcopy(items[sel[0]])
            try:
                initial=week_monday(self.date.get())
            except ValueError:
                initial=datetime.date.fromisoformat(source['week'])+datetime.timedelta(days=7)
            # Datum vybíráme kliknutím v kalendáři, nikoli ručním přepisováním.
            picker=tk.Toplevel(win)
            picker.title('Vybrat týden pro kopii jídelníčku')
            picker.transient(win)
            picker.resizable(False,False)
            picker.grab_set()
            panel=ttk.Frame(picker,padding=14)
            panel.pack()
            ttk.Label(panel,text='Klikněte na libovolný den cílového týdne.',
                      font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(0,5))
            ttk.Label(panel,text='Program automaticky použije pondělí až pátek.').pack(anchor='w',pady=(0,10))
            header=ttk.Frame(panel)
            header.pack(fill='x',pady=(0,8))
            month_text=tk.StringVar()
            month_names=('leden','únor','březen','duben','květen','červen',
                         'červenec','srpen','září','říjen','listopad','prosinec')
            view=[initial.year,initial.month]
            grid=ttk.Frame(panel)
            grid.pack()
            selected_text=tk.StringVar()
            ttk.Label(panel,textvariable=selected_text,foreground='#17476b').pack(pady=(9,3))
            def choose(day):
                picked=datetime.date(view[0],view[1],day)
                target=picked-datetime.timedelta(days=picked.weekday())
                if str(target)==source['week']:
                    messagebox.showinfo('Stejný týden',
                        'Vybrali jste původní týden. Pro jeho otevření použijte „Načíst vybraný jídelníček“.',
                        parent=picker)
                    return
                hitem=copy.deepcopy(source)
                hitem['week']=str(target)
                self.date.set(target.strftime('%d.%m.%Y'))
                self.current=hitem
                self.align_saved_lunch_count(hitem['days'])
                self.parked_days.clear()
                self.sync_days(hitem['days'])
                self.display(hitem['days'])
                exists=any(h.get('week')==str(target) for h in self.history)
                self.status.set('Jídelníček zkopírován do týdne '+target.strftime('%d.%m.%Y')+
                    ('. Cílový týden již existuje; při schválení se program zeptá na přepsání.' if exists else
                     '. Zatím jde pouze o návrh; pro uložení klikněte na Schválit a uložit týden.'))
                picker.destroy()
                win.destroy()
            def change_month(delta):
                n=view[0]*12+view[1]-1+delta
                view[:]=[n//12,n%12+1]
                render()
            ttk.Button(header,text='◀',width=4,command=lambda:change_month(-1)).pack(side='left')
            ttk.Label(header,textvariable=month_text,anchor='center',width=23,
                      font=('Segoe UI',11,'bold')).pack(side='left',padx=8)
            ttk.Button(header,text='▶',width=4,command=lambda:change_month(1)).pack(side='left')
            def render():
                for child in grid.winfo_children():child.destroy()
                month_text.set(month_names[view[1]-1].capitalize()+' '+str(view[0]))
                selected_text.set('Zobrazený měsíc: '+month_names[view[1]-1]+' '+str(view[0]))
                for col,name in enumerate(('Po','Út','St','Čt','Pá','So','Ne')):
                    ttk.Label(grid,text=name,width=5,anchor='center').grid(row=0,column=col,pady=(0,5))
                for row,week in enumerate(calendar.monthcalendar(view[0],view[1]),1):
                    for col,day in enumerate(week):
                        if day:
                            date=datetime.date(view[0],view[1],day)
                            monday_cell=date-datetime.timedelta(days=date.weekday())
                            selected_monday=initial-datetime.timedelta(days=initial.weekday())
                            bg,fg='#ffffff','#203451'
                            if monday_cell==selected_monday and col<5:
                                bg='#dceafa'
                            if date==initial:
                                bg,fg='#285da3','#ffffff'
                            if date==datetime.date.today():
                                bg,fg='#2c925e','#ffffff'
                            button=tk.Button(grid,text=str(day),width=4,
                                             command=lambda d=day:choose(d),
                                             bg=bg,fg=fg,activebackground='#c7daf5',
                                             relief='flat',bd=1,cursor='hand2')
                            button.grid(row=row,column=col,padx=2,pady=2)
                            if date==initial:
                                button.focus_set()
            ttk.Label(panel,text='Zelená: dnes   Modrá: vybraný den   Světle modrá: pracovní týden',
                      foreground='#38516f').pack(pady=(5,0))
            render()
            ttk.Button(panel,text='Zrušit',command=picker.destroy).pack(pady=(10,0))
            picker.bind('<Escape>',lambda event:picker.destroy())
            picker.update_idletasks()
            x=win.winfo_rootx()+max(0,(win.winfo_width()-picker.winfo_width())//2)
            y=win.winfo_rooty()+max(0,(win.winfo_height()-picker.winfo_height())//2)
            picker.geometry(f'+{x}+{y}')
        def delete_selected():
            sel=weeks.curselection()
            if not sel:
                messagebox.showinfo('Smazání','Nejdříve vyberte týden.',parent=win);return
            week=items[sel[0]]['week']
            display=datetime.date.fromisoformat(week).strftime('%d.%m.%Y')
            if not messagebox.askyesno('Smazat uložený týden',
                    'Opravdu odstranit z historie týden od '+display+'?\n\n'
                    'Smazání lze vrátit tlačítkem Zpět, a to i po restartu programu.',parent=win):return
            before=copy.deepcopy(self.history)
            self.history=[x for x in self.history if x['week']!=week]
            try:
                self.write_history()
                self.save_history_state(before,'Smazání týdne '+week)
            except OSError as exc:
                self.history=before
                try:self.write_history()
                except OSError:pass
                messagebox.showerror('Chyba při mazání','Týden nebylo možné bezpečně smazat.\n'+str(exc),parent=win)
                return
            if self.current and self.current.get('week')==week:
                self.status.set('Týden '+display+' odstraněn z historie; zobrazený jídelníček zůstává rozpracovaný a lze jej upravovat i znovu schválit.')
            else:
                self.status.set('Týden '+display+' smazán z historie. Lze jej vrátit tlačítkem Zpět.')
            reload_items()
        def step(redo=False):
            if self.history_step(redo):reload_items()
        ttk.Button(buttons,text='Smazat vybraný',command=delete_selected).pack(side='left',padx=4)
        ttk.Button(buttons,text='↶ Zpět',command=lambda:step(False)).pack(side='left',padx=4)
        ttk.Button(buttons,text='↷ Znovu',command=lambda:step(True)).pack(side='left',padx=4)
        win.bind('<Control-z>',lambda event:step(False))
        win.bind('<Control-y>',lambda event:step(True))
        win.bind('<Control-Shift-Z>',lambda event:step(True))
        # Dvojklik na týden v seznamu provede stejné načtení jako tlačítko.
        weeks.bind('<Double-Button-1>',lambda event:load_selected())
        ttk.Button(buttons,text='Načíst vybraný jídelníček',command=load_selected).pack(side='left',padx=4)
        ttk.Button(buttons,text='Zkopírovat do jiného týdne',command=copy_to_another_week).pack(side='left',padx=4)
        ttk.Button(buttons,text=self.t('history_close'),command=win.destroy).pack(side='right',padx=4)


def main():
    import traceback
    root = None
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception:
        details = traceback.format_exc()
        try:
            (ROOT / 'chyba_generatoru.log').write_text(details, encoding='utf-8')
        except OSError:
            pass
        print(details, flush=True)
        try:
            messagebox.showerror('Chyba generátoru', 'Program narazil na chybu. Podrobnosti jsou v souboru chyba_generatoru.log.\n\n' + details[-1200:])
        except Exception:
            pass
        if root is not None:
            try: root.destroy()
            except Exception: pass
        raise SystemExit(1)

if __name__ == '__main__':
    main()

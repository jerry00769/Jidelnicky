// catalog.js – Načítání katalogu z TXT a správa databáze jídel
window.SchoolCatalog = (() => {
    let catalog = { soup: {}, main: {} };
    let rawTxtContent = "";

    // Výchozí fallback katalog, pokud by se txt nenačetlo
    const defaultText = `
POLÉVKY – VÝVARY (2)
- Hovězí vývar s nudlemi
- Kuřecí vývar se zeleninou

POLÉVKY – ZELENINOVÉ A KRÉMOVÉ (2)
- Bramboračka
- Česnečka

HLAVNÍ JÍDLA – HOVĚZÍ A TELECÍ (2)
- Svíčková na smetaně
- Hovězí guláš

HLAVNÍ JÍDLA – VEPŘOVÉ A UZENÉ (2)
- Vepřová pečeně se zelím
- Vepřový řízek

HLAVNÍ JÍDLA – DRŮBEŽ A KRÁLÍK (2)
- Pečené kuře
- Kuřecí řízek

HLAVNÍ JÍDLA – MLETÉ MASO A ZAPÉKANÉ (2)
- Sekaná pečeně
- Zapečené těstoviny

HLAVNÍ JÍDLA – RYBY (2)
- Obalované rybí filé
- Losos pečený

HLAVNÍ JÍDLA – LUŠTĚNINOVÁ (2)
- Čočka na kyselo s vejcem
- Hrachová kaše

HLAVNÍ JÍDLA – BEZMASÁ SLANÁ (2)
- Smažený sýr
- Zeleninové rizoto

HLAVNÍ JÍDLA – SLADKÁ (2)
- Dukátové buchtičky
- Žemlovka s jablky
`;

    function parseTxt(text) {
        let groups = { soup: {}, main: {} };
        let currentKind = null;
        let currentCat = null;

        const lines = text.split(/\r?\n/);
        for (let line of lines) {
            line = line.trim();
            if (!line) continue;

            // Detekce hlavičky kategorie např: POLÉVKY – VÝVARY (17) nebo HLAVNÍ JÍDLA – HOVĚZÍ A TELECÍ (13)
            let match = line.match(/^(POLÉVKY|HLAVNÍ JÍDLA)\s*[–-]\s*(.+?)\s*\(\d+\)\s*$/i);
            if (match) {
                currentKind = (match[1].toUpperCase().startsWith('POLÉVKY')) ? 'soup' : 'main';
                currentCat = match[2].trim().toUpperCase();
                if (!groups[currentKind][currentCat]) {
                    groups[currentKind][currentCat] = [];
                }
                continue;
            }

            // Položka jídla začínající pomlčkou
            if (line.startsWith('-') && currentKind && currentCat) {
                let mealName = line.replace(/^-\s*/, '').trim();
                if (mealName && !groups[currentKind][currentCat].includes(mealName)) {
                    groups[currentKind][currentCat].push(mealName);
                }
            }
        }
        return groups;
    }

    async function loadFromFile() {
        try {
            let response = await fetch('skolni_obedy.txt');
            if (!response.ok) throw new Error('Soubor nelze načíst');
            rawTxtContent = await response.text();
        } catch (e) {
            console.warn('Nepodařilo se načíst skolni_obedy.txt, používám výchozí data.', e);
            rawTxtContent = defaultText;
        }
        catalog = parseTxt(rawTxtContent);
    }

    function getCatalog() {
        return catalog;
    }

    function addMeal(kind, category, name) {
        if (!catalog[kind][category]) catalog[kind][category] = [];
        if (!catalog[kind][category].includes(name)) {
            catalog[kind][category].push(name);
            catalog[kind][category].sort((a, b) => a.localeCompare(b, 'cs'));
            updateRawTxtFromCatalog();
        }
    }

    function removeMeal(kind, category, name) {
        if (catalog[kind][category]) {
            catalog[kind][category] = catalog[kind][category].filter(x => x !== name);
            updateRawTxtFromCatalog();
        }
    }

    function updateRawTxtFromCatalog() {
        // Vygeneruje zpět textovou strukturu TXT pro případný export/uložení
        let lines = ["KATALOG JÍDEL – AKTUALIZOVANÝ\n"];
        
        for (let kind of ['soup', 'main']) {
            let prefix = kind === 'soup' ? 'POLÉVKY – ' : 'HLAVNÍ JÍDLA – ';
            for (let [cat, items] of Object.entries(catalog[kind])) {
                lines.push(`${prefix}${cat} (${items.length})`);
                for (let item of items) {
                    lines.push(`- ${item}`);
                }
                lines.push("");
            }
        }
        rawTxtContent = lines.join('\n');
    }

    function exportTxt() {
        return rawTxtContent;
    }

    return {
        loadFromFile,
        getCatalog,
        addMeal,
        removeMeal,
        exportTxt
    };
})();
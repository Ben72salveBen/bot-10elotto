import os
import json
import re
import urllib.request
import ssl
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Intersezione Voti (Griglia 90)",
    page_icon="🤖",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE_ARCHIVIO = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")
NOME_FILE_ULTIMA_GIOCATA = os.path.join(CARTELLA_DOCUMENTI, "ultima_giocata.json")

def carica_archivio():
    if os.path.exists(NOME_FILE_ARCHIVIO):
        try:
            with open(NOME_FILE_ARCHIVIO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Errore nella lettura dell'archivio: {e}")
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE_ARCHIVIO, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio archivio: {e}")
        return False

def salva_giocata(numeri_scelti):
    try:
        with open(NOME_FILE_ULTIMA_GIOCATA, "w", encoding="utf-8") as f:
            json.dump(numeri_scelti, f, ensure_ascii=False, indent=4)
    except Exception as e:
        pass

def carica_giocata():
    if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
        try:
            with open(NOME_FILE_ULTIMA_GIOCATA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def estrai_numeri_da_testo(testo, limite):
    pezzi = re.findall(r'\d+', testo)
    numeri_validi = []
    visti = set()
    for p in pezzi:
        if len(p) > 2 and len(p) % 2 == 0:
            for j in range(0, len(p), 2):
                sub = int(p[j:j+2])
                if 1 <= sub <= 90 and sub not in visti:
                    visti.add(sub)
                    numeri_validi.append(sub)
        else:
            val = int(p)
            if 1 <= val <= 90 and val not in visti:
                visti.add(val)
                numeri_validi.append(val)
        if len(numeri_validi) == limite:
            break
    return numeri_validi

def scarica_estrazioni_con_bypass():
    url = "https://lottologia.com/10elotto5minuti/estrazioni"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://lottologia.com/'
    }
    
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            html = response.read().decode('utf-8', 'ignore')
            
            if "Domande Frequenti" in html:
                html = html.split("Domande Frequenti")[0]
            elif "domande frequenti" in html:
                html = html.split("domande frequenti")[0]
                
            if "Seleziona Numeri" in html:
                html = html.split("Seleziona Numeri")[-1]
            elif "seleziona numeri" in html:
                html = html.split("seleziona numeri")[-1]
            
            estrazioni_trovate = []
            blocchi = re.split(r'#(\d+)', html)
            
            for i in range(1, len(blocchi), 2):
                id_concorso = int(blocchi[i])
                testo_blocco = blocchi[i+1]
                
                if "Numeri" not in testo_blocco and "numeri" not in testo_blocco:
                    continue
                
                match_num = re.search(r'Numeri[:\s]*([\s\S]*?)(?=Extra|Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                numeri_base = []
                if match_num:
                    numeri_base = estrai_numeri_da_testo(match_num.group(1), 20)
                
                if len(numeri_base) < 20:
                    numeri_base = estrai_numeri_da_testo(testo_blocco, 20)

                numeri_extra = []
                match_extra = re.search(r'Extra[:\s]*([\s\S]*?)(?=Doppio|Oro|$)', testo_blocco, re.IGNORECASE)
                if match_extra:
                    numeri_extra = estrai_numeri_da_testo(match_extra.group(1), 15)
                else:
                    pos_extra = testo_blocco.lower().find('extra')
                    if pos_extra != -1:
                        testo_dopo_extra = testo_blocco[pos_extra:]
                        numeri_extra = estrai_numeri_da_testo(testo_dopo_extra, 15)

                if len(numeri_base) == 20:
                    tutti_35 = sorted(list(set(numeri_base + numeri_extra)))
                    estrazioni_trovate.append({
                        'id': id_concorso,
                        'base': sorted(numeri_base),
                        'extra': sorted(numeri_extra),
                        'tutti': tutti_35
                    })

            if not estrazioni_trovate:
                return []

            estrazioni_trovate.sort(key=lambda x: x['id'])
            return estrazioni_trovate

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ==========================================
# VERIFICA ESITO ULTIMA GIOCATA
# ==========================================
def verifica_esito_ultima_giocata(ultima_estrazione_obj):
    ultima_giocata = carica_giocata()
    if not ultima_giocata:
        return

    st.markdown("### 📊 VERIFICA ESITO GIOCATA PRECEDENTE:")
    set_giocati = set(ultima_giocata)
    
    set_base = set(ultima_estrazione_obj.get('base', []))
    presi_base = set_giocati.intersection(set_base)
    punti_base = len(presi_base)
    
    set_extra = set(ultima_estrazione_obj.get('extra', []))
    presi_extra = set_giocati.intersection(set_extra)
    punti_extra = len(presi_extra)
    
    st.write(f"• **Numeri giocati:** `{sorted(list(set_giocati))}`")
    
    st.markdown("#### 🔵 Numeri Base (20 estratti):")
    st.write(f"• Estratti: `{sorted(list(set_base))}`")
    if punti_base >= 2:
        st.success(f"🎉 **BASE VINCENTE! {punti_base} punti realizzati!** (Indovinati: {sorted(list(presi_base))})")
    else:
        st.info(f"ℹ️ Base: {punti_base} punti.")

    st.markdown("#### 🟠 Opzione Extra (15 estratti):")
    if set_extra:
        st.write(f"• Estratti Extra: `{sorted(list(set_extra))}`")
        if punti_extra >= 2:
            st.success(f"🎉 **EXTRA VINCENTE! {punti_extra} punti realizzati!** (Indovinati: {sorted(list(presi_extra))})")
        else:
            st.info(f"ℹ️ Extra: {punti_extra} punti.")
    else:
        st.warning("⚠️ Dati Extra non disponibili per questa estrazione.")
        
    st.markdown("---")

# ==========================================
# ELABORAZIONE PREVISIONE: INTERSEZIONE RIGHE/COLONNE VUOTE
# ==========================================
def elabora_previsione(quantita_desiderata):
    archivio = carica_archivio()
    
    if len(archivio) == 0:
        st.warning("Nessuna estrazione in archivio!")
        return

    st.info("Analisi geometrica della griglia 90 numeri (20 numeri base dell'ultima estrazione)...")

    ultima_estrazione = archivio[-1]
    numeri_base = set(ultima_estrazione['base'])

    # 1. Costruiamo la matrice 9x10 (Righe 0-8, Colonne 0-9)
    # Le righe vanno da 0 a 8 (corrispondono alle decine: 1-10 -> riga 0, 11-20 -> riga 1, ecc.)
    # Le colonne vanno da 0 a 9 (colonna 0: numeri che finiscono per 1 o 0 a seconda della disposizione, standard 1-10 per riga)
    
    righe_vuote = []
    colonne_vuote = []

    # Controllo righe (9 righe da 10 numeri ciascuna)
    for r in range(9):
        inizio = r * 10 + 1
        fine = (r + 1) * 10
        numeri_riga = set(range(inizio, fine + 1))
        # Se nessun numero della riga è uscito
        if len(numeri_base.intersection(numeri_riga)) == 0:
            righe_vuote.append(r)

    # Controllo colonne (10 colonne)
    for c in range(10):
        # I numeri di una colonna c (dove c va da 0 a 9, es. colonna 0 = 1, 11, 21... colonna 9 = 10, 20, 30...)
        col_nums = [c + 1 + i * 10 for i in range(9)]
        # Gestione speciale per lo 0 che corrisponde al 10, 20, ecc.
        if c == 9:
            col_nums = [10 + i * 10 for i in range(9)]
        else:
            col_nums = [c + 1 + i * 10 for i in range(9) if (c + 1 + i * 10) <= 90]
            
        numeri_colonna = set(col_nums)
        if len(numeri_base.intersection(numeri_colonna)) == 0:
            colonne_vuote.append(c)

    st.write(f"• **Righe completamente vuote identificate:** {len(righe_vuote)} (Indici: {righe_vuote})")
    st.write(f"• **Colonne completamente vuote identificate:** {len(colonne_vuote)} (Indici: {colonne_vuote})")

    # 2. Troviamo i numeri di intersezione tra le righe vuote e le colonne vuote
    numeri_intersezione = []
    for r in righe_vuote:
        for c in colonne_vuote:
            # Calcoliamo il numero esatto dell'intersezione
            if c == 9:
                num = (r + 1) * 10
            else:
                num = r * 10 + (c + 1)
            if 1 <= num <= 90:
                numeri_intersezione.append(num)

    pool_candidati = set()

    # Se troviamo intersezioni dirette, partiamo da quelle come "fulcro"
    if numeri_intersezione:
        st.success(f"🎯 **Trovati numeri di intersezione (Riga Vuota x Colonna Vuota):** {numeri_intersezione}")
        fulcri = numeri_intersezione
    else:
        st.warning("⚠️ Nessuna intersezione perfetta riga/colonna vuota trovata in questa estrazione. Uso le righe o colonne singolarmente.")
        # Fallback: prendiamo tutti i numeri delle righe vuote o colonne vuote
        for r in righe_vuote:
            for i in range(1, 11):
                n = r * 10 + i
                if n <= 90: pool_candidati.add(n)
        for c in colonne_vuote:
            for i in range(9):
                n = (i * 10) + (c + 1) if c != 9 else (i + 1) * 10
                if 1 <= n <= 90: pool_candidati.add(n)
        fulcri = list(pool_candidati)

    # 3. Aggiungiamo i vicini geometrici (Sopra, Sotto, Sinistra, Destra sulla griglia 10x9)
    vicini_finali = set()
    for f in fulcri:
        vicini_finali.add(f) # Aggiungiamo il fulcro stesso
        
        # Calcolo riga e colonna del fulcro
        r_f = (f - 1) // 10
        c_f = (f - 1) % 10
        
        # Vicino Sinistra
        if c_f > 0:
            vicini_finali.add(f - 1)
        # Vicino Destra
        if c_f < 9:
            vicini_finali.add(f + 1)
        # Vicino Sopra
        if r_f > 0:
            vicini_finali.add(f - 10)
        # Vicino Sotto
        if r_f < 8:
            vicini_finali.add(f + 10)

    # Convertiamo in lista ordinata
    lista_finale = sorted(list(vicini_finali))

    # Se abbiamo troppi o pochi numeri, li adattiamo alla quantità richiesta
    if len(lista_finale) > quantita_desiderata:
        migliori = lista_finale[:quantita_desiderata]
    elif len(lista_finale) < quantita_desiderata:
        # Integriamo prendendo numeri sparsi se mancano
        rimanenti = [n for n in range(1, 91) if n not in lista_finale and n not in numeri_base]
        while len(lista_finale) < quantita_desiderata and rimanenti:
            lista_finale.append(rimanenti.pop(0))
        migliori = sorted(lista_finale[:quantita_desiderata])
    else:
        migliori = lista_finale

    salva_giocata(migliori)

    st.markdown(f"### 🤖 PREVISIONE GEOMETRICA ({quantita_desiderata} NUMERI):")
    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"## **` {numeri_str} `**")

    st.markdown("---")
    st.info("📌 **Logica applicata:** Intersezione geometrica tra righe e colonne con zero presenze nell'ultima estrazione, estesa ai vicini immediati (croce).")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - Intersezione Voti Griglia")
st.write("Metodo geometrico basato sulle righe e colonne vuote del tabellone a 10 colonne.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Scarica Web, Verifica & Previsione", "Genera Solamente Previsione", "Visualizza Archivio", "Svuota Archivio")
)

if opzione == "Scarica Web, Verifica & Previsione":
    if st.button("Avvia Sincronizzazione & Calcolo", type="primary"):
        with st.spinner("Scraping e calcolo geometrico in corso..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if len(estrazioni) > 0:
                archivio = carica_archivio()
                set_esistenti = {ext['id'] for ext in archivio}
                nuove_aggiunte = 0
                for ext in estrazioni:
                    if ext['id'] not in set_esistenti:
                        archivio.append(ext)
                        set_esistenti.add(ext['id'])
                        nuove_aggiunte += 1
                
                salva_archivio(archivio)
                st.success(f"Sincronizzazione completata! ({nuove_aggiunte} nuove estrazioni salvate)")
                
                if len(archivio) > 0:
                    verifica_esito_ultima_giocata(archivio[-1])
                
                elabora_previsione(quantita)
            else:
                st.error("Nessuna estrazione trovata sul web.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione da Archivio Locale", type="primary"):
        with st.spinner("Elaborazione previsione geometrica in corso..."):
            elabora_previsione(quantita)

elif opzione == "Visual

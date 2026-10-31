import os
import json
import re
import urllib.request
import ssl
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Intersezione Pura (Griglia 10x9)",
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
        except Exception:
            return []
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE_ARCHIVIO, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def salva_giocata(numeri_scelti):
    try:
        with open(NOME_FILE_ULTIMA_GIOCATA, "w", encoding="utf-8") as f:
            json.dump(numeri_scelti, f, ensure_ascii=False, indent=4)
    except Exception:
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
            if "Seleziona Numeri" in html:
                html = html.split("Seleziona Numeri")[-1]
            
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

                match_extra = re.search(r'Extra[:\s]*([\s\S]*?)(?=Doppio|Oro|$)', testo_blocco, re.IGNORECASE)
                numeri_extra = []
                if match_extra:
                    numeri_extra = estrai_numeri_da_testo(match_extra.group(1), 15)

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
        st.error(f"Errore di connessione: {e}")
        return []

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
    st.markdown(f"• **Base ({punti_base} punti):** {sorted(list(presi_base)) if punti_base > 0 else 'Nessuno'}")
    st.markdown(f"• **Extra ({punti_extra} punti):** {sorted(list(presi_extra)) if punti_extra > 0 else 'Nessuno'}")
    st.markdown("---")

def elabora_previsione():
    archivio = carica_archivio()
    if not archivio:
        st.warning("Nessuna estrazione in archivio! Sincronizza prima dal web.")
        return

    ultima_estrazione = archivio[-1]
    numeri_base = set(ultima_estrazione.get('base', []))
    
    if not numeri_base:
        st.error("I dati dell'ultima estrazione non contengono i numeri base.")
        return

    righe_vuote = []
    colonne_vuote = []

    # 1. Individuazione Righe Vuote (9 righe, ciascuna da 10 numeri: riga 0 = 1-10, riga 1 = 11-20, ..., riga 8 = 81-90)
    for r in range(9):
        inizio = r * 10 + 1
        fine = (r + 1) * 10
        numeri_riga = set(range(inizio, fine + 1))
        if len(numeri_base.intersection(numeri_riga)) == 0:
            righe_vuote.append(r)

    # 2. Individuazione Colonne Vuote (10 colonne, ciascuna da 9 numeri: colonna 0 = 1,11,21...81, colonna 9 = 10,20...90)
    for c in range(10):
        if c == 9:
            col_nums = [10 + i * 10 for i in range(9)]
        else:
            col_nums = [c + 1 + i * 10 for i in range(9) if (c + 1 + i * 10) <= 90]
        
        numeri_colonna = set(col_nums)
        if len(numeri_base.intersection(numeri_colonna)) == 0:
            colonne_vuote.append(c)

    st.write(f"• **Righe completamente vuote (0-8):** {righe_vuote if righe_vuote else 'Nessuna'}")
    st.write(f"• **Colonne completamente vuote (0-9):** {colonne_vuote if colonne_vuote else 'Nessuna'}")

    # 3. Estrazione PURA dei numeri all'intersezione tra le 10 colonne e le 9 righe
    intersezioni_pure = []
    for r in righe_vuote:
        for c in colonne_vuote:
            if c == 9:
                num = (r + 1) * 10
            else:
                num = r * 10 + (c + 1)
            if 1 <= num <= 90:
                intersezioni_pure.append(num)

    migliori = sorted(list(set(intersezioni_pure)))

    if not migliori:
        st.warning("⚠️ In questa estrazione non ci sono intersezioni perfette tra righe e colonne entrambe totalmente vuote nella griglia 10x9.")
        salva_giocata([])
        return

    salva_giocata(migliori)

    st.markdown(f"### 🎯 NUMERI DALL'INTERSEZIONE PURA ({len(migliori)} trovati):")
    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"## **` {numeri_str} `**")
    st.markdown("---")

# Interfaccia Streamlit
st.title("🤖 Bot 10eLotto - Intersezione Pura (10x9)")
st.write("Estrazione esclusiva dei numeri all'incrocio tra le 9 righe e le 10 colonne prive di presenze.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Scarica Web, Verifica & Previsione", "Genera Solamente Previsione", "Visualizza Archivio", "Svuota Archivio")
)

if opzione == "Scarica Web, Verifica & Previsione":
    if st.button("Avvia Sincronizzazione & Calcolo", type="primary"):
        with st.spinner("Elaborazione in corso..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if estrazioni:
                archivio = carica_archivio()
                set_esistenti = {ext['id'] for ext in archivio}
                for ext in estrazioni:
                    if ext['id'] not in set_esistenti:
                        archivio.append(ext)
                salva_archivio(archivio)
                st.success("Sincronizzazione completata!")
                archivio_aggiornato = carica_archivio()
                if archivio_aggiornato:
                    verifica_esito_ultima_giocata(archivio_aggiornato[-1])
                elabora_previsione()
            else:
                st.error("Nessuna estrazione trovata.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione", type="primary"):
        elabora_previsione()

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Archivio")
    if not archivio_corrente:
        st.info("Archivio vuoto.")
    else:
        for ext in reversed(archivio_corrente):
            st.text(f"Concorso #{ext['id']} - Base: {ext.get('base', [])}")

elif opzione == "Svuota Archivio":
    if st.button("Conferma Svuotamento"):
        salva_archivio([])
        if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
            os.remove(NOME_FILE_ULTIMA_GIOCATA)
        st.success("Archivio pulito con successo.")

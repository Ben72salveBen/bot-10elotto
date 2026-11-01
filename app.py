import os
import json
import re
import urllib.request
import ssl
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Filtro Dinamico (Verifica Base + Extra)",
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
                archivio = json.load(f)
                return archivio
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
# VERIFICA ESITO ULTIMA GIOCATA (BASE + EXTRA)
# ==========================================
def verifica_esito_ultima_giocata(ultima_estrazione_obj):
    ultima_giocata = carica_giocata()
    if not ultima_giocata:
        return

    st.markdown("### 📊 VERIFICA ESITO GIOCATA PRECEDENTE:")
    set_giocati = set(ultima_giocata)
    
    # 1. Controllo sui Numeri Base
    set_base = set(ultima_estrazione_obj.get('base', []))
    presi_base = set_giocati.intersection(set_base)
    punti_base = len(presi_base)
    
    # 2. Controllo sui Numeri Extra
    set_extra = set(ultima_estrazione_obj.get('extra', []))
    presi_extra = set_giocati.intersection(set_extra)
    punti_extra = len(presi_extra)
    
    st.write(f"• **Numeri giocati:** `{sorted(list(set_giocati))}`")
    
    # Esito Base
    st.markdown("#### 🔵 Numeri Base (20 estratti):")
    st.write(f"• Estratti: `{sorted(list(set_base))}`")
    if punti_base >= 2:
        st.success(f"🎉 **BASE VINCENTE! {punti_base} punti realizzati!** (Indovinati: {sorted(list(presi_base))})")
    else:
        st.info(f"ℹ️ Base: {punti_base} punti.")

    # Esito Extra
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
# ELABORAZIONE PREVISIONE CON FILTRI
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    
    if len(archivio) < 3:
        st.warning("Servono almeno 3 estrazioni in archivio per applicare i filtri di rotazione!")
        return

    st.info("Applicazione dei filtri sui numeri dell'ultima estrazione (Base + Extra)...")

    ultima_estrazione_obj = archivio[-1]
    tutti_35 = ultima_estrazione_obj['tutti']

    # Filtro 1: Escludiamo i numeri già usciti nelle 2 estrazioni precedenti
    numeri_precedenti_esclusione = set()
    for ext in archivio[-3:-1]:
        for n in ext.get('base', []):
            numeri_precedenti_esclusione.add(n)

    candidati_filtrati = [n for n in tutti_35 if n not in numeri_precedenti_esclusione]

    # Filtro 2: Isoleremo quelli che formavano coppie a distanza 1
    candidati_filtrati.sort()
    coppie_distanza_1 = []
    
    for i in range(len(candidati_filtrati) - 1):
        n1 = candidati_filtrati[i]
        n2 = candidati_filtrati[i+1]
        if n2 - n1 == 1:
            if n1 not in coppie_distanza_1: coppie_distanza_1.append(n1)
            if n2 not in coppie_distanza_1: coppie_distanza_1.append(n2)

    pool_finale = coppie_distanza_1 if len(coppie_distanza_1) >= quantita_numeri else candidati_filtrati
    
    if len(pool_finale) < quantita_numeri:
        pool_finale = tutti_35

    migliori = sorted(pool_finale[:quantita_numeri])
    salva_giocata(migliori)

    st.markdown(f"### 🤖 PREVISIONE FILTRATA ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"## **` {numeri_str} `**")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🔢 Numeri Base", value=len(ultima_estrazione_obj.get('base', [])))
    with col2:
        st.metric(label="➕ Numeri Extra", value=len(ultima_estrazione_obj.get('extra', [])))
    with col3:
        st.metric(label="🎯 Totale Bacino", value=len(tutti_35))

    st.info("📌 **Logica applicata:** Previsione generata dai 35 numeri filtrati. Alla prossima sincronizzazione il bot verificherà separatamente Base ed Extra.")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - Verifica Base & Extra")
st.write("Analisi intelligente dei numeri con controllo esiti separato per estrazione Base e Opzione Extra.")

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
        with st.spinner("Scraping e verifica esiti in corso..."):
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
                
                # Verifica l'ultima estrazione salvata in archivio rispetto alla giocata precedente
                if len(archivio) > 0:
                    verifica_esito_ultima_giocata(archivio[-1])
                
                elabora_previsione(quantita)
            else:
                st.error("Nessuna estrazione trovata sul web.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione da Archivio Locale", type="primary"):
        with st.spinner("Elaborazione previsione in corso..."):
            elabora_previsione(quantita)

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni (Base & Extra)")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Archivio vuoto.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            base_str = ', '.join(map(str, ext.get('base', [])))
            extra_str = ', '.join(map(str, ext.get('extra', []))) if ext.get('extra') else "Nessuno"
            st.text(f"Concorso #{ext['id']}\n  Base: {base_str}\n  Extra: {extra_str}\n")

elif opzione == "Svuota Archivio":
    if st.button("Conferma Cancellazione Archivio e Memoria", type="secondary"):
        salva_archivio([])
        if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
            os.remove(NOME_FILE_ULTIMA_GIOCATA)
        st.success("Archivio e ultime giocate cancellate con successo.")

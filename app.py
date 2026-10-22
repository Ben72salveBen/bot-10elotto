import os
import json
import re
import urllib.request
import ssl
from collections import defaultdict
import streamlit as st

# Configurazione della pagina ottimizzata per Mobile
st.set_page_config(
    page_title="Bot 10eLotto",
    page_icon="🔥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto_extra.json")

def carica_archivio():
    if os.path.exists(NOME_FILE):
        try:
            with open(NOME_FILE, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                archivio_normalizzato = []
                for item in archivio:
                    if isinstance(item, list):
                        archivio_normalizzato.append({
                            'numeri': sorted([int(n) for n in item]),
                            'extra': []
                        })
                    elif isinstance(item, dict):
                        archivio_normalizzato.append({
                            'numeri': sorted([int(n) for n in item.get('numeri', [])]),
                            'extra': sorted([int(n) for n in item.get('extra', [])])
                        })
                return [ext for ext in archivio_normalizzato if len(ext['numeri']) >= 20]
        except Exception as e:
            st.error(f"Errore lettura file: {e}")
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio file: {e}")
        return False

def scarica_estrazioni_con_bypass():
    url = "https://lottologia.com/10elotto5minuti/estrazioni"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
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
                
                match_num = re.search(r'Numeri\s*([\s\S]*?)(?=Extra|Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                match_extra = re.search(r'Extra\s*([\s\S]*?)(?=Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                
                if match_num:
                    testo_sezione = match_num.group(1)
                    pezzi_cifre = re.findall(r'\d+', testo_sezione)
                    
                    numeri_validi = []
                    visti = set()
                    for p in pezzi_cifre:
                        val = int(p)
                        if 1 <= val <= 90 and val not in visti:
                            visti.add(val)
                            numeri_validi.append(val)
                        if len(numeri_validi) == 20:
                            break
                    
                    extra_validi = []
                    if match_extra:
                        testo_ext = match_extra.group(1)
                        pezzi_ext = re.findall(r'\d+', testo_ext)
                        visti_ext = set()
                        for p in pezzi_ext:
                            val = int(p)
                            if 1 <= val <= 90 and val not in visti_ext:
                                visti_ext.add(val)
                                extra_validi.append(val)
                            if len(extra_validi) == 15:
                                break

                    if len(numeri_validi) == 20:
                        numeri_validi.sort()
                        extra_validi.sort()
                        estrazioni_trovate.append({
                            'id': id_concorso,
                            'numeri': numeri_validi,
                            'extra': extra_validi
                        })

            if not estrazioni_trovate:
                return []

            estrazioni_trovate.sort(key=lambda x: x['id'])
            return estrazioni_trovate

    except Exception as e:
        st.error(f"Errore connessione web: {e}")
        return []

def elabora_previsione(quantita_numeri):
    archivio_completo = carica_archivio()
    lookback = 9
    
    if len(archivio_completo) < lookback:
        st.warning(f"Servono almeno {lookback} estrazioni salvate. Clicca su 'Sincronizza Web'!")
        return

    # ESCLUDIAMO l'ultimissima estrazione (-1) per evitare il blocco di saturazione
    ultime_otto_senza_ultima = [ext['numeri'] for ext in archivio_completo[-lookback:-1]]

    punteggio_fiammata = defaultdict(float)
    frequenza_recentissima = defaultdict(int)
    distanza_concorso = {}

    for idx, ext in enumerate(ultime_otto_senza_ultima):
        distanza = (len(ultime_otto_senza_ultima) - 1) - idx  
        
        for n in ext:
            num = int(n)
            frequenza_recentissima[num] += 1
            distanza_concorso[num] = distanza

            if distanza == 0:
                punteggio_fiammata[num] += 2.5
            elif distanza == 1:
                punteggio_fiammata[num] += 2.0
            elif distanza == 2:
                punteggio_fiammata[num] += 1.5
            else:
                punteggio_fiammata[num] += 0.5

    for num in range(1, 91):
        if frequenza_recentissima[num] >= 2:
            punteggio_fiammata[num] += (frequenza_recentissima[num] * 2.0)
            
        if num not in distanza_concorso:
            distanza_concorso[num] = 99

    classifica = sorted(
        range(1, 91),
        key=lambda i: (
            -punteggio_fiammata[i],
            -frequenza_recentissima[i],
            distanza_concorso[i],
            i
        )
    )

    migliori = classifica[:quantita_numeri]
    migliori.sort()

    st.session_state['ultima_previsione'] = migliori

    st.success("✅ Previsione Elaborata!")
    st.markdown(f"### 🔥 NUMERI CONSIGLIATI ({quantita_numeri}):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"# **` {numeri_str} `**")
    st.caption("🔍 Algoritmo Offset: L'ultimissima estrazione è stata ignorata per intercettare i rientri imminenti.")

# --- INTERFACCIA PRINCIPALE ---
st.title("🎲 Bot 10eLotto Mobile")

archivio_corrente = carica_archivio()
st.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.slider("Quanti numeri vuoi giocare?", min_value=2, max_value=10, value=2)

col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Sincronizza Web", type="primary", use_container_width=True):
        with st.spinner("Scraping..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if estrazioni:
                archivio = carica_archivio()
                set_esistenti = {tuple(ext['numeri']) for ext in archivio}
                nuove = 0
                for ext in estrazioni:
                    if tuple(ext['numeri']) not in set_esistenti:
                        archivio.append(ext)
                        set_esistenti.add(tuple(ext['numeri']))
                        nuove += 1
                salva_archivio(archivio)
                st.success(f"+{nuove} nuove!")
                elabora_previsione(quantita)
            else:
                st.error("Nessun dato dal web.")

with col2:
    if st.button("⚡ Calcola Ora", type="secondary", use_container_width=True):
        elabora_previsione(quantita)

st.markdown("---")

# Sezione esito / verifica rapida
if 'ultima_previsione' in st.session_state and st.session_state['ultima_previsione']:
    st.subheader("📊 Ultima Previsione Memorizzata")
    pred = st.session_state['ultima_previsione']
    st.write("👉 " + " - ".join(map(str, pred)))
    
    if archivio_corrente:
        ultima_estrazione = archivio_corrente[-1]['numeri']
        presi = [n for n in pred if n in set(ultima_estrazione)]
        st.write(f"Ultima uscita: {', '.join(map(str, ultima_estrazione))}")
        st.metric(label="Centrati nell'Ultimo Concorso", value=f"{len(presi)} su {len(pred)}")
        if presi:
            st.success(f"Presi: {', '.join(map(str, presi))}")

# Accordion per lo storico su mobile
with st.expander("📁 Vedi Storico Estrazioni"):
    if not archivio_corrente:
        st.write("Archivio vuoto.")
    else:
        for idx, ext in enumerate(reversed(archivio_corrente[-10:])):
            st.text(f"#{len(archivio_corrente)-idx}: {', '.join(map(str, ext['numeri']))}")

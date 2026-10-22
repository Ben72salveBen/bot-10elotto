import os
import json
import re
import urllib.request
import ssl
from collections import defaultdict
import streamlit as st

st.set_page_config(
    page_title="Bot 10eLotto Mobile",
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
                            'id': 0,
                            'numeri': sorted([int(n) for n in item]),
                            'extra': []
                        })
                    elif isinstance(item, dict):
                        archivio_normalizzato.append({
                            'id': item.get('id', 0),
                            'numeri': sorted([int(n) for n in item.get('numeri', [])]),
                            'extra': sorted([int(n) for n in item.get('extra', [])])
                        })
                return archivio_normalizzato
        except Exception:
            pass
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def scarica_estrazioni_con_bypass():
    url = "https://lottologia.com/10elotto5minuti/estrazioni/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://lottologia.com/'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            html = response.read().decode('utf-8', 'ignore')
            
            estrazioni_trovate = []
            blocchi_split = re.split(r'#(\d+)', html)
            
            for i in range(1, len(blocchi_split) - 1, 2):
                id_concorso = int(blocchi_split[i])
                testo_blocco = blocchi_split[i+1]
                
                cifre = re.findall(r'\b([1-9]|[1-8]\d|90)\b', testo_blocco)
                numeri_int = [int(c) for c in cifre]
                
                visti = set()
                validi = [n for n in numeri_int if not (n in visti or visti.add(n))]
                
                if len(validi) >= 20:
                    base = sorted(validi[:20])
                    extra = sorted(validi[20:35]) if len(validi) >= 35 else []
                    estrazioni_trovate.append({
                        'id': id_concorso,
                        'numeri': base,
                        'extra': extra
                    })

            if estrazioni_trovate:
                diz = {e['id']: e for e in estrazioni_trovate}
                risultato = list(diz.values())
                risultato.sort(key=lambda x: x['id'])
                return risultato
    except Exception as e:
        print(f"Errore di rete nello scraping: {e}")
        
    return []

def elabora_previsione(quantita_numeri):
    archivio_completo = carica_archivio()
    lookback = 9
    
    if len(archivio_completo) < lookback:
        st.warning(f"Servono almeno {lookback} estrazioni in archivio. Clicca su Sincronizza Web!")
        return

    # ESCLUSIONE dell'ultimissima estrazione (-1) per evitare il blocco di saturazione
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

    st.success("✅ Previsione Elaborata con Algoritmo Offset!")
    st.markdown(f"### 🔥 NUMERI CONSIGLIATI ({quantita_numeri}):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"# **` {numeri_str} `**")
    st.caption("🔍 Algoritmo Offset: Ultima estrazione esclusa per intercettare i rientri imminenti.")

# --- INTERFACCIA PRINCIPALE ---
st.title("🎲 Bot 10eLotto Mobile")

archivio_corrente = carica_archivio()
st.metric(label="Estrazioni totali in Archivio", value=len(archivio_corrente))

quantita = st.slider("Quanti numeri vuoi giocare?", min_value=2, max_value=10, value=2)

col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Sincronizza Web", type="primary", use_container_width=True):
        with st.spinner("Scaricamento ultime estrazioni dal web..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if estrazioni:
                archivio = carica_archivio()
                set_esistenti = {tuple(ext['numeri']) for ext in archivio}
                nuove = 0
                for ext in estrazioni:
                    if tuple(ext['numeri']) not in set_esistenti:
                        archivio.append(ext)
                        nuove += 1
                salva_archivio(archivio)
                st.success(f"Sincronizzazione completata! Aggiunte {nuove} nuove estrazioni.")
                archivio_corrente = carica_archivio()
                elabora_previsione(quantita)
            else:
                st.error("Impossibile scaricare le estrazioni in automatico in questo momento (il sito ha risposto con un blocco temporaneo). Riprova tra poco.")

with col2:
    if st.button("⚡ Calcola Previsione", type="secondary", use_container_width=True):
        elabora_previsione(quantita)

st.markdown("---")

if 'ultima_previsione' in st.session_state and st.session_state['ultima_previsione']:
    st.subheader("📊 Ultima Previsione Memorizzata")
    pred = st.session_state['ultima_previsione']
    st.write("👉 " + " - ".join(map(str, pred)))
    
    if archivio_corrente:
        ultima_estrazione = archivio_corrente[-1]['numeri']
        presi = [n for n in pred if n in set(ultima_estrazione)]
        st.metric(label="Centrati nell'Ultima Estrazione", value=f"{len(presi)} su {len(pred)}")
        if presi:
            st.success(f"Presi: {', '.join(map(str, presi))}")

with st.expander("📁 Vedi Storico Estrazioni in Archivio"):
    if not archivio_corrente:
        st.write("Archivio vuoto.")
    else:
        for idx, ext in enumerate(reversed(archivio_corrente[-15:])):
            st.text(f"Concorso #{ext.get('id', 'N/D')}: {', '.join(map(str, ext['numeri']))}")

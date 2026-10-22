import os
import json
import re
import urllib.request
import ssl
from collections import defaultdict
import streamlit as st

# Configurazione della pagina per Mobile
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
            st.error(f"Errore lettura file archivio: {e}")
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio archivio: {e}")
        return False

def scarica_estrazioni_con_bypass():
    url = "https://lottologia.com/10elotto5minuti/estrazioni/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            html = response.read().decode('utf-8', 'ignore')
            
            # Pulisce blocchi inutili che possono alterare il parsing
            if "Domande Frequenti" in html:
                html = html.split("Domande Frequenti")[0]
            if "domande frequenti" in html:
                html = html.split("domande frequenti")[0]
                
            estrazioni_trovate = []
            
            # Cerca tutti i blocchi concorso (es. #123 o concorso 123)
            blocchi = re.findall(r'#(\d+)[\s\S]*?(?=#\d+|$)', html)
            if not blocchi:
                # Metodo di fallback con regex diretta su sequenze di numeri
                blocchi_raw = re.split(r'#(\d+)', html)
                for i in range(1, len(blocchi_raw)-1, 2):
                    id_concorso = int(blocchi_raw[i])
                    testo = blocchi_raw[i+1]
                    numeri = [int(n) for n in re.findall(r'\b(?:[1-8]?\d|90)\b', testo)]
                    
                    # Rimuove duplicati mantenendo l'ordine
                    visti = set()
                    validi = [n for n in numeri if not (n in visti or visti.add(n))]
                    
                    if len(validi) >= 20:
                        base = sorted(validi[:20])
                        extra = sorted(validi[20:35]) if len(validi) >= 35 else []
                        estrazioni_trovate.append({
                            'id': id_concorso,
                            'numeri': base,
                            'extra': extra
                        })
            else:
                # Estrazione standard a blocchi isolati
                blocchi_split = re.split(r'#(\d+)', html)
                for i in range(1, len(blocchi_split)-1, 2):
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

            if not estrazioni_trovate:
                st.warning("Nessuna estrazione strutturata estratta dalla pagina web.")
                return []

            # Mantiene solo elementi unici ordinati per ID concorso
            diz_estrazioni = {e['id']: e for e in estrazioni_trovate}
            risultato = list(diz_estrazioni.values())
            risultato.sort(key=lambda x: x['id'])
            return risultato

    except Exception as e:
        st.error(f"Errore di connessione o scraping web: {e}")
        return []

def elabora_previsione(quantita_numeri):
    archivio_completo = carica_archivio()
    lookback = 9
    
    if len(archivio_completo) < lookback:
        st.warning(f"Servono almeno {lookback} estrazioni salvate. Clicca su 'Sincronizza Web'!")
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

    st.success("✅ Previsione Elaborata!")
    st.markdown(f"### 🔥 NUMERI CONSIGLIATI ({quantita_numeri}):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"# **` {numeri_str} `**")
    st.caption("🔍 Algoritmo Offset: Ultima estrazione ignorata per intercettare i rientri imminenti.")

# --- INTERFACCIA PRINCIPALE ---
st.title("🎲 Bot 10eLotto Mobile")

archivio_corrente = carica_archivio()
st.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.slider("Quanti numeri vuoi giocare?", min_value=2, max_value=10, value=2)

col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Sincronizza Web", type="primary", use_container_width=True):
        with st.spinner("Scraping Lottologia..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if estrazioni:
                archivio = carica_archivio()
                set_esistenti = {tuple(ext['numeri']) for ext in archivio}
                nuove = 0
                for ext in estrazioni:
                    if tuple(ext['numeri']) not in set_esistenti:
                        archivio.append(ext)
                        set_esist

import os
import json
import re
import urllib.request
import ssl
from collections import defaultdict
from itertools import combinations
import streamlit as st

# Configurazione della pagina per dispositivi mobili
st.set_page_config(
    page_title="Bot 10eLotto Due Ambi Recenti",
    page_icon="🎯",
    layout="centered"
)

# Percorso di salvataggio
CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")

def carica_archivio():
    if os.path.exists(NOME_FILE):
        try:
            with open(NOME_FILE, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                archivio_ordinato = [sorted([int(n) for n in ext]) for ext in archivio if len(ext) == 20]
                return archivio_ordinato
        except Exception as e:
            st.error(f"Errore nella lettura del file di archivio: {e}")
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio su file: {e}")
        return False

def scarica_estrazioni_con_bypass():
    url = "https://lottologia.com/10elotto5minuti/estrazioni"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.9',
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
                
                match_num = re.search(r'Numeri\s*([\s\S]*?)(?=Oro|Extra|Doppio|$)', testo_blocco, re.IGNORECASE)
                if match_num:
                    testo_sezione = match_num.group(1)
                    pezzi_cifre = re.findall(r'\d+', testo_sezione)
                    
                    numeri_validi = []
                    visti = set()
                    
                    for p in pezzi_cifre:
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
                                
                        if len(numeri_validi) == 20:
                            break
                    
                    if len(numeri_validi) == 20:
                        numeri_validi.sort()
                        estrazioni_trovate.append({
                            'id': id_concorso,
                            'numeri': numeri_validi
                        })

            if not estrazioni_trovate:
                return []

            estrazioni_trovate.sort(key=lambda x: x['id'])
            return [item['numeri'] for item in estrazioni_trovate]

    default:
        return []

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ==========================================
# MOTORE DUE AMBI (ULTIME 10 ESTRAZIONI)
# ==========================================
def elabora_previsione_due_ambi():
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.warning("L'archivio è vuoto. Scarica prima le estrazioni!")
        return

    # Prendiamo rigorosamente le ultime 10 estrazioni
    ultime_10 = archivio[-10:] if len(archivio) >= 10 else archivio
    st.info(f"Analisi in corso sulle ultime **{len(ultime_10)}** estrazioni...")

    frequenze = defaultdict(int)
    ultima_apparizione = {}

    # Scandiamo le ultime 10 estrazioni tenendo traccia della frequenza e dell'indice di comparsa (più alto = più recente)
    for idx_estrazione, ext in enumerate(ultime_10):
        for ambo in combinations(ext, 2):
            ambo_ord = tuple(sorted(ambo))
            frequenze[ambo_ord] += 1
            # Memorizziamo l'indice dell'estrazione più recente in cui è comparso
            ultima_apparizione[ambo_ord] = idx_estrazione

    if not frequenze:
        st.warning("Nessun ambo rilevato nelle ultime estrazioni.")
        return

    # Ordinamento:
    # 1. Frequenza decrescente (chi è uscito più volte)
    # 2. In caso di parità, indice di apparizione più recente decrescente (chi è uscito nell'estrazione più vicina alla fine)
    ambi_ordinati = sorted(
        frequenze.keys(),
        key=lambda ambo: (frequenze[ambo], ultima_apparizione[ambo]),
        reverse=True
    )

    # Prendiamo i primi 2 ambi migliori
    migliori_due = ambi_ordinati[:2]

    st.success("Previsione completata!")
    st.markdown("### 🎯 LE 2 COPPIE SCELTE DA GIOCARE:")
    
    for i, ambo in enumerate(migliori_due, 1):
        freq = frequenze[ambo]
        st.markdown(f"**Giocata {i}:** ` {ambo[0]:02d} - {ambo[1]:02d} ` (Frequenza: {freq} volte nelle ultime 10)")

# Interfaccia grafica della Web App
st.title("🎯 Bot 10eLotto Due Ambi Recenti")
st.write("Generatore delle 2 coppie più calde basate sulle ultime 10 estrazioni (con priorità alla comparsa più recente).")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Genera Previsione", "Scarica Web & Prendi Previsione", "Visualizza Archivio", "Svuota Archivio")
)

if opzione == "Scarica Web & Prendi Previsione":
    if st.button("Avvia Sincronizzazione Web", type="primary"):
        with st.spinner("Connessione a Lottologia in corso..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if len(estrazioni) > 0:
                archivio = carica_archivio()
                set_esistenti = {tuple(ext) for ext in archivio}
                nuove_aggiunte = 0
                for ext in estrazioni:
                    chiave = tuple(ext)
                    if chiave not in set_esistenti:
                        archivio.append(ext)
                        set_esistenti.add(chiave)
                        nuove_aggiunte += 1
                
                if salva_archivio(archivio):
                    st.success(f"Sincronizzazione completata! Aggiunte {nuove_aggiunte} nuove estrazioni.")
                    elabora_previsione_due_ambi()
                else:
                    st.error("Impossibile scrivere sul file di salvataggio.")
            else:
                st.error("Nessuna estrazione valida trovata dal web.")

elif opzione == "Genera Previsione":
    if st.button("Genera 2 Ambi da Archivio", type="primary"):
        with st.spinner("Analisi in corso..."):
            elabora_previsione_due_ambi()

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni Salvate")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Nessuna estrazione presente nell'archivio.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            st.text(f"#{len(archivio)-idx}: {', '.join(map(str, ext))}")

elif opzione == "Svuota Archivio":
    st.warning("Attenzione: questa operazione cancellerà tutto l'archivio salvato.")
    if st.button("Conferma Cancellazione Archivio", type="secondary"):
        salva_archivio([])
        st.success("Archivio pulito con successo.")

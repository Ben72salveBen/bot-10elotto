import os
import json
import re
import urllib.request
import ssl
import numpy as np
import streamlit as st

# ==========================================
# CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(
    page_title="10eLotto Ciclometry Bot",
    page_icon="🧬",
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
                archivio_ordinato = []
                for ext in archivio:
                    if isinstance(ext, dict) and 'numeri' in ext:
                        nums = [int(n) for n in ext['numeri'] if 1 <= int(n) <= 90]
                        if len(nums) == 20:
                            archivio_ordinato.append(sorted(nums))
                    elif isinstance(ext, list):
                        nums = [int(n) for n in ext if 1 <= int(n) <= 90]
                        if len(nums) == 20:
                            archivio_ordinato.append(sorted(nums))
                return archivio_ordinato
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

# ==========================================
# MODULO CICLOMETRIA ARMONICA
# ==========================================
def distanza_ciclometrica(a, b):
    diff = abs(a - b)
    return min(diff, 90 - diff)

def get_diametrale(n):
    diam = (n + 45) % 90
    return 90 if diam == 0 else diam

def analizza_ciclometria(ultimi_numeri, quantita_richiesta):
    candidati = []
    
    for n in ultimi_numeri:
        diam = get_diametrale(int(n))
        if diam not in candidati:
            candidati.append(diam)
        
    for i in range(len(ultimi_numeri)):
        for j in range(i + 1, len(ultimi_numeri)):
            n1 = int(ultimi_numeri[i])
            n2 = int(ultimi_numeri[j])
            dist = distanza_ciclometrica(n1, n2)
            
            if dist in [15, 30, 45]:
                comp1 = (n1 + dist) % 90
                comp2 = (n2 - dist) % 90
                if comp1 == 0: comp1 = 90
                if comp2 == 0: comp2 = 90
                
                if comp1 not in candidati: candidati.append(comp1)
                if comp2 not in candidati: candidati.append(comp2)
                
    for n in ultimi_numeri:
        val = int(n)
        if val not in candidati:
            candidati.append(val)
            
    for n in range(1, 91):
        if n not in candidati:
            candidati.append(n)
            
    candidati.sort()
    return candidati[:quantita_richiesta]

# ==========================================
# PARSER ROBUSTO PER ESTRAZIONE DATI
# ==========================================
def estrai_numeri_puliti(testo):
    # Estrae tutte le cifre e le suddivide in coppie da 2 (formato 10eLotto attaccato es. 010207...)
    pezzi = re.findall(r'\d+', testo)
    numeri_validi = []
    visti = set()
    
    for p in pezzi:
        # Se il blocco ha una lunghezza pari maggiore di 2, spezzettalo in numeri a 2 cifre
        if len(p) >= 2 and len(p) % 2 == 0:
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
                
        if len(numeri_validi) >= 20:
            break
            
    return sorted(numeri_validi[:20])

def scarica_estrazioni_con_bypass():
    urls = [
        "https://lottologia.com/10elotto5minuti/archivio-estrazioni/?lang=it",
        "https://lottologia.com/10elotto5minuti/estrazioni"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8',
        'Referer': 'https://lottologia.com/'
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    html = ""
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                html = response.read().decode('utf-8', 'ignore')
                if "#" in html:
                    break
        except Exception:
            continue

    if not html:
        return []

    try:
        estrazioni_trovate = []
        # Suddividiamo la pagina in base ai cancelletti dei concorsi (#287, #286, ecc.)
        blocchi = re.split(r'#(\d+)', html)
        
        for i in range(1, len(blocchi), 2):
            id_concorso = int(blocchi[i])
            if id_concorso < 100: # Scarta ID falsi o troppo bassi
                continue
                
            testo_blocco = blocchi[i+1]
            
            # Isola la sotto-sezione dei numeri base prima della voce "Oro" o "Extra"
            parts = re.split(r'Oro|Extra', testo_blocco, flags=re.IGNORECASE)
            sezione_numeri = parts[0]
            
            numeri_20 = estrai_numeri_puliti(sezione_numeri)
            
            if len(numeri_20) == 20:
                estrazioni_trovate.append({
                    'id': id_concorso,
                    'numeri': numeri_20
                })

        if not estrazioni_trovate:
            return []

        # Ordina per ID crescente per mantenere la cronologia corretta
        estrazioni_trovate.sort(key=lambda x: x['id'])
        return [item['numeri'] for item in estrazioni_trovate]

    except Exception as e:
        st.error(f-f"Errore nell'elaborazione dello scraping: {e}")
        return []

# ==========================================
# ELABORAZIONE PREVISIONE CICLOMETRICA
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    
    if len(archivio) < 1:
        st.warning("Nessuna estrazione valida in archivio. Esegui prima la sincronizzazione dal web.")
        return

    st.info("Elaborazione quadro ciclometrico sull'ultima estrazione disponibile...")
    
    ultima_estrazione = archivio[-1]
    previsione = analizza_ciclometria(ultima_estrazione, quantita_numeri)
    salva_giocata(previsione)

    risultato_str = ",".join(map(str, previsione)) + ","

    st.markdown(f"### 🧬 PREVISIONE CICLOMETRICA ({quantita_numeri} NUMERI):")
    st.code(risultato_str, language="")
    st.info("📌 **Metodo applicato:** Calcolo geometrico dei diametrici e delle distanze armoniche (15, 30, 45).")

# ==========================================
# INTERFACCIA STREAMLIT
# ==========================================
st.title("🤖 10eLotto Ciclometry Bot")
st.write("Sistema di previsione basato sulla Ciclometria armonica e diametrali.")

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
        with st.spinner("Scaricamento estrazioni ufficiali in corso..."):
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
                
                salva_archivio(archivio)
                st.success(f"Sincronizzazione completata! ({nuove_aggiunte} nuove estrazioni salvate correttamente)")
                
                archivio_aggiornato = carica_archivio()
                if len(archivio_aggiornato) > 0:
                    # Pulisci eventuale archivio vecchio errato prima della verifica
                    pass
                elabora_previsione(quantita)
            else:
                st.error("Impossibile estrarre i dati corretti dal sito. Riprova tra qualche istante.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione da Archivio Locale", type="primary"):
        with st.spinner("Elaborazione previsione in corso..."):
            elabora_previsione(quantita)

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni Corrette")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Archivio vuoto o ripulito.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            st.text(f"#{len(archivio)-idx}: {', '.join(map(str, ext))}")

elif opzione == "Svuota Archivio":
    if st.button("Conferma Cancellazione Archivio e Memoria", type="secondary"):
        salva_archivio([])
        if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
            os.remove(NOME_FILE_ULTIMA_GIOCATA)
        st.success("Archivio svuotato con successo.")

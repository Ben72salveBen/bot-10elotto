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
# SCRAPING AGGIORNATO E PULITO
# ==========================================
def scarica_estrazioni_con_bypass():
    urls = [
        "https://www.10elotto5.it/estrazioni-10-e-lotto-ogni-5-minuti-di-oggi/",
        "https://lottologia.com/10elotto5minuti/estrazioni"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8',
        'Referer': 'https://www.google.com/'
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
                if len(html) > 1000:
                    break
        except Exception:
            continue

    if not html:
        return []

    try:
        estrazioni_trovate = []
        
        # Cerca pattern numerici puliti di 20 numeri all'interno del codice HTML
        # Estraiamo sequenze estese e le filtriamo per gruppi validi da 20 numeri compresi tra 1 e 90
        match_righe = re.findall(r'(?:(\d{1,2})[\s\-,\.]+){19,}(\d{1,2})', html)
        
        # In alternativa, usiamo un parsing dei blocchi basato sui numeri separati
        # Troviamo tutti i numeri singoli o doppi nel testo
        tutti_i_numeri = []
        # Pulizia tag HTML grossolana per isolare il testo utile
        testo_pulito = re.sub(r'<[^>]+>', ' ', html)
        token_numerici = re.findall(r'\b([1-9]|[1-8][0-9]|90)\b', testo_pulito)
        
        # Convertiamo in interi e cerchiamo finestre valide da 20 numeri univoci o estratti in sequenza
        interi = [int(t) for t in token_numerici]
        
        # Suddividiamo a blocchi rigorosi da 20 numeri se presenti in sequenza pulita
        for i in range(0, len(interi) - 19):
            finestra = interi[i:i+20]
            # Controllo validità: tutti compresi tra 1 e 90
            if all(1 <= x <= 90 for x in finestra):
                # Per evitare duplicati vicini sovrapposti, controlliamo l'unicità o la spaziatura
                unici_ordinati = sorted(list(set(finestra)))
                if len(unici_ordinati) == 20:
                    if unici_ordinati not in estrazioni_trovate:
                        estrazioni_trovate.append(unici_ordinati)

        # Se il blocco automatico estrae troppa roba casuale, limitiamo alle ultime valide trovate in ordine
        return estrazioni_trovate[-30:] if len(estrazioni_trovate) > 0 else []

    except Exception as e:
        st.error(f"Errore nello scraping: {e}")
        return []

# ==========================================
# ELABORAZIONE PREVISIONE CICLOMETRICA
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    
    if len(archivio) < 1:
        st.warning("Nessuna estrazione valida in archivio. Esegui prima la sincronizzazione.")
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
                    verifica_esito_ultima_giocata(archivio_aggiornato[-1])
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

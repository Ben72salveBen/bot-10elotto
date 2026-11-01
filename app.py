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
    try:
        os.makedirs(CARTELLA_DOCUMENTI, exist_ok=True)
    except Exception:
        CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE_ARCHIVIO = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")
NOME_FILE_ULTIMA_GIOCATA = os.path.join(CARTELLA_DOCUMENTI, "ultima_giocata.json")

def carica_archivio():
    if os.path.exists(NOME_FILE_ARCHIVIO):
        try:
            with open(NOME_FILE_ARCHIVIO, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                archivio_strutturato = []
                if isinstance(archivio, list):
                    for ext in archivio:
                        if isinstance(ext, dict) and 'numeri' in ext:
                            nums = [int(n) for n in ext['numeri'] if 1 <= int(n) <= 90]
                            if len(nums) == 20:
                                archivio_strutturato.append({
                                    'id': str(ext.get('id', 'N/D')),
                                    'data': str(ext.get('data', '')),
                                    'ora': str(ext.get('ora', '')),
                                    'numeri': sorted(nums)
                                })
                        elif isinstance(ext, list):
                            nums = [int(n) for n in ext if 1 <= int(n) <= 90]
                            if len(nums) == 20:
                                archivio_strutturato.append({
                                    'id': 'N/D',
                                    'data': '',
                                    'ora': '',
                                    'numeri': sorted(nums)
                                })
                return archivio_strutturato
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
    try:
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
    except Exception:
        pass
            
    candidati.sort()
    return candidati[:quantita_richiesta]

# ==========================================
# SCRAPING ROBUSTO
# ==========================================
def scarica_estrazioni_con_bypass():
    urls = [
        "https://www.10elotto5minuti.it/estrazioni-10-e-lotto-ogni-5-minuti-di-oggi/",
        "https://www.10elotto5minuti.it/10elotto-5-minuti.php"
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
                if len(html) > 500:
                    break
        except Exception:
            continue

    if not html:
        return []

    try:
        estrazioni_trovate = []
        testo_pulito = re.sub(r'<[^>]+>', ' | ', html)
        token_testo = re.findall(r'\b([1-9]|[1-8][0-9]|90)\b', testo_pulito)
        interi = [int(t) for t in token_testo]
        
        i = 0
        while i < len(interi) - 19:
            finestra = interi[i:i+20]
            if len(set(finestra)) >= 15:
                estratti_validi = []
                for n in finestra:
                    if 1 <= n <= 90 and n not in estratti_validi:
                        estratti_validi.append(n)
                
                if len(estratti_validi) == 20:
                    estratti_validi.sort()
                    estrazione_obj = {
                        'id': f"Estrazione_{len(estrazioni_trovate)+1}",
                        'data': 'Oggi',
                        'ora': '',
                        'numeri': estratti_validi
                    }
                    if estrazione_obj not in estrazioni_trovate:
                        estrazioni_trovate.append(estrazione_obj)
                    i += 20
                else:
                    i += 1
            else:
                i += 1

        return estrazioni_trovate[-15:] if len(estrazioni_trovate) >= 15 else estrazioni_trovate

    except Exception:
        return []

# ==========================================
# VERIFICA ESITO ULTIMA GIOCATA
# ==========================================
def verifica_esito_ultima_giocata(ultima_estrazione):
    try:
        ultima_giocata = carica_giocata()
        if not ultima_giocata:
            return

        st.markdown("### 📊 VERIFICA ESITO GIOCATA PRECEDENTE:")
        set_estratto = set(ultima_estrazione)
        set_giocati = set(ultima_giocata)
        
        presi = set_giocati.intersection(set_estratto)
        punti = len(presi)
        
        st.write(f"• Numeri giocati: {sorted(list(set_giocati))}")
        st.write(f"• Numeri usciti: {sorted(list(set_estratto))}")
        
        if punti >= 2:
            st.success(f"🎉 **RISULTATO: VINCENTE! {punti} PUNTI REALIZZATI!** (Indovinati: {sorted(list(presi))})")
            st.balloons()
        else:
            st.info(f"ℹ️ Risultato: {punti} punti.")
        st.markdown("---")
    except Exception:
        pass

# ==========================================
# ELABORAZIONE PREVISIONE CICLOMETRICA
# ==========================================
def elabora_previsione(quantita_numeri):
    try:
        archivio = carica_archivio()
        
        if len(archivio) < 1:
            st.warning("Nessuna estrazione valida in archivio. Esegui prima la sincronizzazione.")
            return

        st.info("Elaborazione quadro ciclometrico sull'ultima estrazione disponibile...")
        
        ultima_estrazione = archivio[-1]['numeri']
        previsione = analizza_ciclometria(ultima_estrazione, quantita_numeri)
        salva_giocata(previsione)

        risultato_str = ",".join(map(str, previsione)) + ","

        st.markdown(f"### 🧬 PREVISIONE CICLOMETRICA ({quantita_numeri} NUMERI):")
        st.code(risultato_str, language="")
        st.info("📌 **Metodo applicato:** Calcolo geometrico dei diametrici e delle distanze armoniche (15, 30, 45).")
    except Exception as e:
        st.error(f"Errore nell'elaborazione: {e}")

# ==========================================
# INTERFACCIA STREAMLIT (10% MOBILE SAFE)
# ==========================================
st.title("🤖 10eLotto Ciclometry Bot")
st.write("Sistema mobile-friendly basato su Ciclometria armonica.")

try:
    archivio_corrente = carica_archivio()
    st.metric(label="Estrazioni in Archivio Locale", value=len(archivio_corrente))
except Exception:
    st.metric(label="Estrazioni in Archivio Locale", value=0)

st.markdown("---")
st.subheader("⚙️ Pannello Operazioni")

quantita = st.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

opzione = st.radio(
    "Scegli un'azione:",
    ("Scarica Web, Verifica & Previsione", "Genera Solamente Previsione", "Visualizza Archivio", "Svuota Archivio")
)

st.markdown("---")

if opzione == "Scarica Web, Verifica & Previsione":
    if st.button("🚀 Avvia Sincronizzazione & Calcolo", type="primary", use_container_width=True):
        with st.spinner("Scaricamento blocco estrazioni ufficiali in corso..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if len(estrazioni) > 0:
                archivio = carica_archivio()
                ids_esistenti = {str(item['id']) for item in archivio}
                nuove_aggiunte = 0
                for ext in estrazioni:
                    if str(ext['id']) not in ids_esistenti:
                        archivio.append(ext)
                        ids_esistenti.add(str(ext['id']))
                        nuove_aggiunte += 1
                
                salva_archivio(archivio)
                st.success(f"Sincronizzazione completata! ({nuove_aggiunte} nuove estrazioni salvate)")
                
                archivio_aggiornato = carica_archivio()
                if len(archivio_aggiornato) > 0:
                    verifica_esito_ultima_giocata(archivio_aggiornato[-1]['numeri'])
                elabora_previsione(quantita)
            else:
                st.error("Impossibile estrarre i dati corretti dal sito. Riprova tra qualche istante.")

elif opzione == "Genera Solamente Previsione":
    if st.button("🔮 Genera Previsione da Archivio", type="primary", use_container_width=True):
        with st.spinner("Elaborazione previsione in corso..."):
            elabora_previsione(quantita)

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni Ufficiali")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Archivio vuoto.")
    else:
        for ext in reversed(archivio):
            num_str = ", ".join(map(str, ext['numeri']))
            st.text(f"#{ext['id']} | {ext['data']} {ext['ora']} -> [{num_str}]")

elif opzione == "Svuota Archivio":
    if st.button("🗑️ Conferma Cancellazione Archivio", type="secondary", use_container_width=True):
        salva_archivio([])
        if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
            os.remove(NOME_FILE_ULTIMA_GIOCATA)
        st.success("Archivio svuotato con successo.")

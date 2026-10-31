import os
import json
import re
import urllib.request
import ssl
import numpy as np
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Top 2 Ambi Distinti (Ultime 10 Estrazioni)",
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
                archivio_ordinato = [sorted([int(n) for n in ext]) for ext in archivio if len(ext) == 20]
                return archivio_ordinato
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

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ==========================================
# GESTIONE VERIFICA ULTIMA GIOCATA
# ==========================================
def verifica_esito_ultima_giocata(ultima_estrazione):
    ultima_giocata = carica_giocata()
    if not ultima_giocata:
        return

    st.markdown("### 📊 VERIFICA ESITO GIOCATA PRECEDENTE:")
    set_estratto = set(ultima_estrazione)
    set_giocati = set(ultima_giocata)
    
    presi = set_giocati.intersection(set_estratto)
    punti = len(presi)
    
    st.write(f"• Numeri giocati: {sorted(list(set_giocati))}")
    st.write(f"• Numeri usciti nell'estrazione: {sorted(list(set_estratto))}")
    
    if punti >= 2:
        st.success(f"🎉 **RISULTATO: VINCENTE! {punti} PUNTI REALIZZATI!** (Indovinati: {sorted(list(presi))})")
        st.balloons()
    else:
        st.info(f"ℹ️ Risultato: {punti} punti. Il modello ha registrato l'esito.")
    st.markdown("---")

# ==========================================
# ELABORAZIONE PREVISIONE (Top 2 Ambi con Numeri Diversi)
# ==========================================
def elabora_previsione():
    archivio = carica_archivio()
    
    if len(archivio) < 10:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno 10 estrazioni!")
        return

    st.info("Analisi delle ultime 10 estrazioni per trovare i 2 ambi più frequenti con numeri completamente diversi...")

    ultime_10 = archivio[-10:]
    ambi_count = {}

    for ext in ultime_10:
        ext_sorted = sorted(ext)
        for i in range(len(ext_sorted)):
            for j in range(i + 1, len(ext_sorted)):
                ambo = (ext_sorted[i], ext_sorted[j])
                ambi_count[ambo] = ambi_count.get(ambo, 0) + 1

    # Ordiniamo gli ambi per frequenza decrescente
    ambi_ordinati = sorted(ambi_count.items(), key=lambda x: x[1], reverse=True)

    top_2_ambi = []
    numeri_usati = set()

    for ambo, freq in ambi_ordinati:
        n1, n2 = ambo
        # Verificiamo che nessuno dei due numeri sia già stato usato nell'altro ambo
        if n1 not in numeri_usati and n2 not in numeri_usati:
            top_2_ambi.append((ambo, freq))
            numeri_usati.add(n1)
            numeri_usati.add(n2)
            
            if len(top_2_ambi) == 2:
                break

    if len(top_2_ambi) < 2:
        st.error("Impossibile trovare 2 ambi completamente distinti nelle ultime 10 estrazioni.")
        return

    migliori = sorted(list(numeri_usati))
    salva_giocata(migliori)

    st.markdown("### 🤖 TOP 2 AMBI DISTINTI (ULTIME 10 ESTRAZIONI):")
    
    for idx, (ambo, freq) in enumerate(top_2_ambi, 1):
        st.write(f"• **Ambo #{idx}:** `{ambo[0]:02d} - {ambo[1]:02d}` (Uscito {freq} volte nelle ultime 10)")

    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"### Numeri da giocare (4 numeri unici): ## **` {numeri_str} `**")

    st.markdown("---")
    st.info("📌 **Consiglio Operativo:** Questi sono i due ambi più frequenti con 4 numeri totalmente indipendenti. Attiva sempre l'opzione **EXTRA**!")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - Top 2 Ambi Distinti")
st.write("Modello pulito: individua i 2 ambi più frequenti nelle ultime 10 estrazioni che non condividono alcun numero.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Scarica Web, Verifica & Previsione", "Genera Solamente Previsione", "Visualizza Archivio", "Svuota Archivio")
)

if opzione == "Scarica Web, Verifica & Previsione":
    if st.button("Avvia Sincronizzazione & Calcolo", type="primary"):
        with st.spinner("Scraping e conteggio ambi distinti in corso..."):
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
                st.success(f"Sincronizzazione completata! ({nuove_aggiunte} nuove estrazioni salvate)")
                
                verifica_esito_ultima_giocata(archivio[-1])
                elabora_previsione()
            else:
                st.error("Nessuna estrazione trovata sul web.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione da Archivio Locale", type="primary"):
        with st.spinner("Elaborazione previsione in corso..."):
            elabora_previsione()

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Archivio vuoto.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            st.text(f"#{len(archivio)-idx}: {', '.join(map(str, ext))}")

elif opzione == "Svuota Archivio":
    if st.button("Conferma Cancellazione Archivio e Memoria", type="secondary"):
        salva_archivio([])
        if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
            os.remove(NOME_FILE_ULTIMA_GIOCATA)
        st.success("Archivio e ultime giocate cancellate con successo.")

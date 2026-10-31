import os
import json
import re
import urllib.request
import ssl
import numpy as np
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Coppie a Distanza 1 & Trend",
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
# ELABORAZIONE PREVISIONE (Coppie Distanza 1 + Trend)
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    
    if len(archivio) < 3:
        st.warning("Servono almeno 3 estrazioni in archivio per analizzare il trend di decine e cadenze!")
        return

    st.info("Ricerca coppie a distanza 1 nell'ultima estrazione e filtraggio sul trend termico...")

    # 1. Analisi delle ultime 3 estrazioni per decine e cadenze calde
    conteggio_decine = {d: 0 for d in range(10)}
    conteggio_cadenze = {c: 0 for c in range(10)}

    for ext in archivio[-3:]:
        for n in ext:
            if 1 <= n <= 90:
                decina = (n - 1) // 10
                if decina > 8: decina = 8
                cadenza = n % 10
                
                conteggio_decine[decina] += 1
                conteggio_cadenze[cadenza] += 1

    decina_calda = max(conteggio_decine, key=conteggio_decine.get)
    cadenza_calda = max(conteggio_cadenze, key=conteggio_cadenze.get)

    # 2. Ultima estrazione ordinata geometricamente
    ultima_estrazione = sorted(archivio[-1])

    # 3. Estrazione delle sole coppie con DISTANZA ESATTA DI 1 (consecutivi)
    coppie_candidate = []
    for i in range(len(ultima_estrazione) - 1):
        n1 = ultima_estrazione[i]
        n2 = ultima_estrazione[i+1]
        distanza = n2 - n1
        
        if distanza == 1:  # Rigorosamente distanza 1
            punteggio_coppia = 0.0
            
            dec_n1, dec_n2 = (n1 - 1) // 10, (n2 - 1) // 10
            cad_n1, cad_n2 = n1 % 10, n2 % 10
            
            # Assegniamo punteggio se la coppia appartiene alla decina o cadenza dominante
            if dec_n1 == decina_calda or dec_n2 == decina_calda:
                punteggio_coppia += 3.0
            if cad_n1 == cadenza_calda or cad_n2 == cadenza_calda:
                punteggio_coppia += 3.0

            coppie_candidate.append({
                'coppia': (n1, n2),
                'score': punteggio_coppia
            })

    # Ordiniamo le coppie a distanza 1 in base al riscontro termico
    coppie_candidate.sort(key=lambda x: x['score'], reverse=True)

    numeri_selezionati = []
    num_coppie_necessarie = max(1, quantita_numeri // 2)

    # Prendiamo le coppie a distanza 1 migliori
    for item in coppie_candidate[:num_coppie_necessarie]:
        n1, n2 = item['coppia']
        if n1 not in numeri_selezionati: numeri_selezionati.append(n1)
        if n2 not in numeri_selezionati: numeri_selezionati.append(n2)

    # Se mancano numeri per completare la quantità scelta, peschiamo altri numeri sempre da coppie a distanza 1 disponibili
    if len(numeri_selezionati) < quantita_numeri:
        for item in coppie_candidate[num_coppie_necessarie:]:
            n1, n2 = item['coppia']
            if n1 not in numeri_selezionati and len(numeri_selezionati) < quantita_numeri:
                numeri_selezionati.append(n1)
            if n2 not in numeri_selezionati and len(numeri_selezionati) < quantita_numeri:
                numeri_selezionati.append(n2)
            if len(numeri_selezionati) == quantita_numeri:
                break

    # Se per esaurimento delle coppie a distanza 1 servisse altro, prendiamo il resto dall'estrazione ordinata
    if len(numeri_selezionati) < quantita_numeri:
        for num in ultima_estrazione:
            if num not in numeri_selezionati:
                numeri_selezionati.append(num)
                if len(numeri_selezionati) == quantita_numeri:
                    break

    migliori = sorted(numeri_selezionati[:quantita_numeri])
    salva_giocata(migliori)

    st.markdown(f"### 🤖 PREVISIONE COPPIE DISTANZA 1 ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"## **` {numeri_str} `**")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🔥 Decina Calda", value=f"Fascia {decina_calda*10+1}-{(decina_calda+1)*10}")
    with col2:
        st.metric(label="⚡ Cadenza Calda", value=f"N. {cadenza_calda}")
    with col3:
        st.metric(label="🔢 Numeri Scelti", value=f"{quantita_numeri}")

    st.info("📌 **Consiglio Operativo:** Il bot ha selezionato esclusivamente coppie a distanza geometrica 1 (consecutivi) filtrate sul trend attivo. Attiva sempre l'opzione **EXTRA**!")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - Coppie a Distanza 1")
st.write("Modello geometrico puro basato esclusivamente su coppie di numeri consecutivi (distanza 1) filtrati sul trend.")

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
        with st.spinner("Scraping e analisi coppie a distanza 1 in corso..."):
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
                elabora_previsione(quantita)
            else:
                st.error("Nessuna estrazione trovata sul web.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione da Archivio Locale", type="primary"):
        with st.spinner("Elaborazione previsione in corso..."):
            elabora_previsione(quantita)

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

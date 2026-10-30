import os
import json
import re
import urllib.request
import ssl
import numpy as np
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Markov Ultra-Chirurgico (PMI + Momentum)",
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
# ELABORAZIONE PREVISIONE (Markov + PMI + Accelerazione)
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    
    if len(archivio) < 25:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno 25 estrazioni per l'analisi ultra-chirurgica!")
        return

    st.info("Elaborazione avanzata con Catene di Markov, PMI e Accelerazione del Momentum...")

    archivio_recente = archivio[-50:] if len(archivio) >= 50 else archivio
    n_rec = len(archivio_recente)

    # 1. Matrici di Transizione Markov (1° e 2° Ordine con Decay)
    transizioni_1 = np.zeros((90, 90), dtype=np.float32)
    transizioni_2 = np.zeros((90, 90), dtype=np.float32)
    
    # 2. Strutture per PMI (Co-occorrenze e frequenze singole)
    conteggi_singoli = np.zeros(90, dtype=np.float32)
    cooccorrenze_grezze = np.zeros((90, 90), dtype=np.float32)
    totale_estrazioni_pmi = float(n_rec)

    for k in range(2, n_rec):
        peso_temporale = np.exp((k - n_rec) / 12.0)
        
        ext_t_minus_1 = archivio_recente[k-2]
        ext_t = archivio_recente[k-1]
        ext_next = archivio_recente[k]
        
        # Markov 1° Ordine
        for i in ext_t:
            if 1 <= i <= 90:
                for j in ext_next:
                    if 1 <= j <= 90:
                        transizioni_1[i-1][j-1] += peso_temporale
                        
        # Markov 2° Ordine
        for i in ext_t_minus_1:
            if 1 <= i <= 90:
                for j in ext_next:
                    if 1 <= j <= 90:
                        transizioni_2[i-1][j-1] += (peso_temporale * 0.5)

        # Raccolta dati per PMI
        for n in ext_next:
            if 1 <= n <= 90:
                conteggi_singoli[n-1] += 1.0
        for i in range(len(ext_next)):
            for j in range(i + 1, len(ext_next)):
                n1, n2 = ext_next[i], ext_next[j]
                if 1 <= n1 <= 90 and 1 <= n2 <= 90:
                    cooccorrenze_grezze[n1-1][n2-1] += 1.0
                    cooccorrenze_grezze[n2-1][n1-1] += 1.0

    # Calcolo della PMI (Pointwise Mutual Information)
    matrice_pmi = np.zeros((90, 90), dtype=np.float32)
    for i in range(90):
        for j in range(90):
            if i != j and cooccorrenze_grezze[i][j] > 0:
                p_xy = cooccorrenze_grezze[i][j] / totale_estrazioni_pmi
                p_x = conteggi_singoli[i] / totale_estrazioni_pmi
                p_y = conteggi_singoli[j] / totale_estrazioni_pmi
                if p_x > 0 and p_y > 0:
                    matrice_pmi[i][j] = np.log(p_xy / (p_x * p_y))

    # Smoothing e normalizzazione Markov
    transizioni_1 += 1.0
    transizioni_2 += 1.0
    matrice_prob_1 = transizioni_1 / transizioni_1.sum(axis=1, keepdims=True)
    matrice_prob_2 = transizioni_2 / transizioni_2.sum(axis=1, keepdims=True)

    ultima_estrazione = archivio[-1]
    penultima_estrazione = archivio[-2] if len(archivio) >= 2 else ultima_estrazione

    scores_raw = np.zeros(90, dtype=np.float32)
    for i in ultima_estrazione:
        if 1 <= i <= 90:
            scores_raw += 0.7 * matrice_prob_1[i-1]
            
    for i in penultima_estrazione:
        if 1 <= i <= 90:
            scores_raw += 0.3 * matrice_prob_2[i-1]

    # 3. Calcolo del Ritardo Esatto
    ritardi = {n: 999 for n in range(1, 91)}
    for idx_rev, ext in enumerate(reversed(archivio)):
        for n in ext:
            if 1 <= n <= 90 and ritardi[n] == 999:
                ritardi[n] = idx_rev

    # 4. Accelerazione del Momentum (Frequenza ultimi 2 concorsi vs precedenti 8)
    freq_ultimi_2 = {n: 0 for n in range(1, 91)}
    for ext in archivio[-2:]:
        for n in ext:
            if 1 <= n <= 90:
                freq_ultimi_2[n] += 1

    freq_precedenti_8 = {n: 0 for n in range(1, 91)}
    for ext in archivio[-10:-2]:
        for n in ext:
            if 1 <= n <= 90:
                freq_precedenti_8[n] += 1

    valutazioni = []
    for i in range(90):
        num = i + 1
        score_base = scores_raw[i]
        ritardo = ritardi[num]
        
        # Accelerazione: rapporto tra la spinta recente e la media passata
        momentum_acc = (freq_ultimi_2[num] * 2.0) - freq_precedenti_8[num]

        # Filtro Ritardo e Boost Momentum
        if ritardo > 15:  # Troppo in ritardo, penalizzazione prudenziale
            score_corretto = score_base * 0.5
        elif 2 <= ritardo <= 10:  # Finestra di ritardo ottimale
            score_corretto = score_base * 1.2
        else:
            score_corretto = score_base

        # Se c'è un'accelerazione di momentum positiva, potenziamo lo score
        if momentum_acc > 0:
            score_corretto *= (1.0 + (momentum_acc * 0.3))

        valutazioni.append({
            'numero': num,
            'score': score_corretto,
            'score_raw': score_base
        })

    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    # 5. Sinergia basata su PMI tra i top candidati
    top_candidati = [item['numero'] for item in valutazioni[:25]]
    bonus_pmi = np.zeros(90, dtype=np.float32)
    for c1 in top_candidati:
        for c2 in top_candidati:
            if c1 != c2:
                pmi_val = matrice_pmi[c1-1][c2-1]
                if pmi_val > 0:
                    bonus_pmi[c1-1] += pmi_val * 0.05

    for item in valutazioni:
        item['score'] += bonus_pmi[item['numero']-1]

    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    # 6. Filtro Anti-Clustering (Decine)
    max_per_decina = 1 if quantita_numeri <= 4 else 2
    conteggio_decine = {d: 0 for d in range(10)}
    valutazioni_filtrate = []

    for item in valutazioni:
        num = item['numero']
        decina = (num - 1) // 10
        if decina > 8:
            decina = 8

        if conteggio_decine[decina] < max_per_decina:
            conteggio_decine[decina] += 1
            valutazioni_filtrate.append(item)
        else:
            item['score'] *= 0.2
            valutazioni_filtrate.append(item)

    valutazioni_filtrate.sort(key=lambda x: x['score'], reverse=True)

    selezionati = valutazioni_filtrate[:quantita_numeri]
    migliori = [item['numero'] for item in selezionati]
    migliori.sort()

    salva_giocata(migliori)

    mean_raw_score = np.mean([item['score_raw'] for item in selezionati]) if selezionati else 0
    confidenza = round(min(float(mean_raw_score * 100 * 6.0), 95.0), 1)

    st.markdown(f"### 🤖 PREVISIONE ULTRA-CHIRURGICA ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"## **` {numeri_str} `**")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="🎯 Confidenza del Modello", value=f"{confidenza} %")
    with col2:
        st.metric(label="🔢 Numeri Selezionati", value=f"{quantita_numeri}")

    st.info("📌 **Consiglio Operativo:** Gioca questa combinazione aggiungendo l'opzione **EXTRA ATTIVA**.")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - Markov Ultra-Chirurgico")
st.write("Modello con Catene di Markov avanzate, PMI (Mutual Information) e derivata del Momentum.")

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
        with st.spinner("Scraping e calcolo ultra-chirurgico in corso..."):
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

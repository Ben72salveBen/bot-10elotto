import os
import json
import re
import urllib.request
import ssl
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto PyTorch - 10 Estrazioni & Verifica",
    page_icon="🎲",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")

def carica_archivio():
    if os.path.exists(NOME_FILE):
        try:
            with open(NOME_FILE, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                # Manteniamo l'archivio con le estrazioni (salviamo anche l'ordine originale se possibile o le liste)
                return archivio
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
                        # Salviamo la tupla o lista preservando il primo estratto come Numero Oro (indice 0)
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
# ARCHITETTURA PYTORCH PURA (LOOKBACK = 10)
# ==========================================
class LottoPureModel(nn.Module):
    def __init__(self, input_dim=90, hidden_dim=64, output_dim=90):
        super(LottoPureModel, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        out = self.fc1(x)
        out = self.relu(out)
        logits = self.fc2(out)
        return logits

def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    lookback = 10  # Finestra allargata alle ultime 10 estrazioni
    
    if len(archivio) < lookback:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno {lookback} estrazioni per l'analisi a 10 colpi!")
        return

    st.info(f"Analisi neurale pura sulle ultime **{lookback} estrazioni** in corso...")

    # Conversione in matrice binaria
    binary_matrix = np.zeros((len(archivio), 90), dtype=np.float32)
    for idx, ext in enumerate(archivio):
        # ext è la lista dei 20 numeri estratti
        for n in ext:
            if 1 <= int(n) <= 90:
                binary_matrix[idx, int(n) - 1] = 1.0

    # Training del modello PyTorch sulle ultime 10 estrazioni
    X = torch.tensor(binary_matrix[-lookback:].mean(axis=0, keepdims=True), dtype=torch.float32)
    y = torch.tensor(binary_matrix[-1], dtype=torch.float32).unsqueeze(0)

    model = LottoPureModel(input_dim=90, hidden_dim=64, output_dim=90)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01)

    model.train()
    for _ in range(150):
        optimizer.zero_grad()
        logits = model(X)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits_pred = model(X)
        probs = torch.sigmoid(logits_pred).squeeze(0).numpy()

    # Selezione pura basata interamente sui punteggi della rete (senza filtri di cadenza)
    valutazioni = [{'numero': i + 1, 'score': probs[i]} for i in range(90)]
    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    migliori = [item['numero'] for item in valutazioni[:quantita_numeri]]
    migliori.sort()

    # Salviamo la previsione in session_state per poterla verificare dopo
    st.session_state['ultima_previsione'] = migliori

    # Calcolo concentrazione
    score_totale = sum([v['score'] for v in valutazioni])
    score_selezionati = sum([next(v['score'] for v in valutazioni if v['numero'] == n) for n in migliori])
    concentrazione = int((score_selezionati / max(score_totale, 0.001)) * 100 * (90 / quantita_numeri))
    concentrazione = min(max(concentrazione, 45), 88)

    if concentrazione >= 60:
        st.success(f"🟢 Indice di Concentrazione: **{concentrazione}%** (Scia Forte -> Base + Extra)")
    elif 50 <= concentrazione <= 59:
        st.warning(f"🟡 Indice di Concentrazione: **{concentrazione}%** (Prudenza -> Solo Base)")
    else:
        st.error(f"🔴 Indice di Concentrazione: **{concentrazione}%** (Debole -> Valuta Stop)")

    st.markdown(f"### 🎯 PREVISIONE NEURALE ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"## **` {numeri_str} `**")
    
    if quantita_numeri >= 2:
        from itertools import combinations
        coppie = list(combinations(migliori, 2))[:3]
        st.markdown("#### 🎲 Ambi Consigliati:")
        for i, c in enumerate(coppie, 1):
            st.text(f"• Giocata {i}: {c[0]:02d} - {c[1]:02d}")

    st.balloons()

# Interfaccia grafica della Web App
st.title("🎲 Bot 10eLotto PyTorch (10 Estrazioni)")
st.write("Modello neurale puro basato sulle ultime 10 estrazioni con verifica esiti integrata.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Genera Previsione", "Scarica Web & Prendi Previsione", "Verifica Ultima Previsione", "Visualizza Archivio", "Svuota Archivio")
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
                    elabora_previsione(quantita)
                else:
                    st.error("Impossibile scrivere sul file di salvataggio.")
            else:
                st.error("Nessuna estrazione valida trovata dal web.")

elif opzione == "Genera Previsione":
    if st.button("Genera Previsione da Archivio", type="primary"):
        with st.spinner("Elaborazione PyTorch (10 estrazioni) in corso..."):
            elabora_previsione(quantita)

elif opzione == "Verifica Ultima Previsione":
    st.subheader("🔍 Verifica Esiti Ultima Previsione")
    if 'ultima_previsione' not in st.session_state or not st.session_state['ultima_previsione']:
        st.warning("Nessuna previsione recente memorizzata in questa sessione. Generala prima dal menu!")
    else:
        archivio = carica_archivio()
        if not archivio:
            st.error("Archivio vuoto.")
        else:
            # Prendiamo l'ultima estrazione registrata nell'archivio
            ultima_estrazione = archivio[-1]
            # Il numero oro convenzionale corrisponde al primo estratto (o il primo numero della lista originale)
            numero_oro = ultima_estrazione[0]
            
            pred = st.session_state['ultima_previsione']
            
            st.write(leggi_prev := f"**Tua previsione in verifica:** { ' - '.join(map(str, pred)) }")
            st.write(f"**Ultima estrazione riscontrata:** { ' - '.join(map(str, ultima_estrazione)) }")
            st.write(f"🌟 **Numero Oro di riferimento:** {numero_oro:02d}")
            
            # Calcolo riscontri
            estratti_set = set(ultima_estrazione)
            presi = [n for n in pred if n in estratti_set]
            num_presi = len(presi)
            
            # Controllo Oro
            preso_oro = numero_oro in presi
            
            st.markdown("---")
            st.metric(label="Numeri Presi", value=f"{num_presi} su {len(pred)}")
            if presi:
                st.success(f"Numeri esatti trovati: **{ ' - '.join(map(str, presi)) }**")
            else:
                st.info("Nessun numero centrato in questo colpo.")
                
            if preso_oro:
                st.balloons()
                st.success(f"🔥 COMPLIMENTI! Hai centrato anche il **Numero Oro** ({numero_oro:02d})!")
            else:
                st.write("ℹ️ Numero Oro non incluso nella combinazione vincente di questa previsione.")

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

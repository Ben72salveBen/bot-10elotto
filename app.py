import os
import json
import re
import urllib.request
import ssl
from collections import Counter
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import streamlit as st

# Configurazione della pagina per adattarsi bene ai dispositivi mobili
st.set_page_config(
    page_title="Bot 10eLotto PyTorch Equilibrato",
    page_icon="🎲",
    layout="centered"
)

# Percorso di salvataggio (compatibile con cloud e locale)
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

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ==========================================
# ARCHITETTURA PYTORCH EQUILIBRATA (1-90)
# ==========================================
class LottoBalancedModel(nn.Module):
    def __init__(self, input_dim=90, hidden_dim=64, output_dim=90):
        super(LottoBalancedModel, self).__init__()
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
    lookback = 3  # Finestra Hot 3 per il calcolo della tendenza
    
    if len(archivio) < lookback:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno {lookback} estrazioni!")
        return

    # 1. Rilevamento Cadenza Calda dalle ultime 3 estrazioni (per il bonus di spinta)
    ultime_tre = archivio[-lookback:]
    cadenze_totali = []
    for ext in ultime_tre:
        for n in ext:
            cadenze_totali.append(n % 10)

    conteggio_cadenze = Counter(cadenze_totali)
    cadenza_calda = conteggio_cadenze.most_common(1)[0][0]

    st.info(f"Analisi completata. **Cadenza Calda di riferimento: {cadenza_calda}** (con spinta bilanciata su tutto il tabellone 1-90)")

    # 2. Preparazione tensore PyTorch sull'intero archivio recente (o sulle ultime estrazioni)
    binary_matrix = np.zeros((len(archivio), 90), dtype=np.float32)
    for idx, ext in enumerate(archivio):
        for n in ext:
            if 1 <= n <= 90:
                binary_matrix[idx, n - 1] = 1.0

    X = torch.tensor(binary_matrix[-lookback:].mean(axis=0, keepdims=True), dtype=torch.float32)
    y = torch.tensor(binary_matrix[-1], dtype=torch.float32).unsqueeze(0)

    model = LottoBalancedModel(input_dim=90, hidden_dim=64, output_dim=90)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01)

    model.train()
    for _ in range(100):
        optimizer.zero_grad()
        logits = model(X)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits_pred = model(X)
        probs = torch.sigmoid(logits_pred).squeeze(0).numpy()

    # 3. Tutti i 90 numeri partono ad armi pari basandosi sulle probabilità della rete.
    # Aggiungiamo un leggero boost percentuale (+15%) solo ai numeri della cadenza calda per favorire la scia.
    valutazioni = []
    for i in range(90):
        num = i + 1
        score = probs[i]
        if (num % 10) == cadenza_calda:
            score *= 1.15  # Leggero bonus di spinta per la cadenza calda
        valutazioni.append({'numero': num, 'score': score})

    # Ordinamento globale su tutti i 90 numeri del lotto
    valutazioni.sort(key=lambda x: x['score'], reverse=True)
    migliori = [item['numero'] for item in valutazioni[:quantita_numeri]]
    migliori.sort()

    # Calcolo Indice di Concentrazione basato sui pesi reali
    score_totale = sum([v['score'] for v in valutazioni])
    score_selezionati = sum([next(v['score'] for v in valutazioni if v['numero'] == n) for n in migliori])
    concentrazione = int((score_selezionati / max(score_totale, 0.001)) * 100 * (90 / quantita_numeri))
    concentrazione = min(max(concentrazione, 45), 88)

    # Output Grafico Semaforo Cassa
    if concentrazione >= 60:
        st.success(f"🟢 Indice di Concentrazione: **{concentrazione}%** (Scia Rovente -> Base + Extra)")
    elif 50 <= concentrazione <= 59:
        st.warning(f"🟡 Indice di Concentrazione: **{concentrazione}%** (Prudenza -> Solo Base)")
    else:
        st.error(f"🔴 Indice di Concentrazione: **{concentrazione}%** (Debole -> Salta il turno / Stop)")

    st.markdown(f"### 🎯 GRUPPO CALDO ({quantita_numeri} NUMERI):")
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
st.title("🎲 Bot 10eLotto PyTorch Equilibrato")
st.write("Modello neurale aperto su tutti i 90 numeri con bonus dinamico per la Cadenza Calda.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=6, value=4)

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
                    elabora_previsione(quantita)
                else:
                    st.error("Impossibile scrivere sul file di salvataggio.")
            else:
                st.error("Nessuna estrazione valida trovata dal web.")

elif opzione == "Genera Previsione":
    if st.button("Genera Previsione da Archivio", type="primary"):
        with st.spinner("Elaborazione in corso..."):
            elabora_previsione(quantita)

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

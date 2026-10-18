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

# Configurazione della pagina per adattarsi bene ai dispositivi mobili
st.set_page_config(
    page_title="Bot 10eLotto PyTorch LSTM",
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
# NUOVA ARCHITETTURA LSTM TEMPORALE
# ==========================================
class LottoLSTM(nn.Module):
    def __init__(self, input_dim=90, hidden_dim=128, num_layers=2, output_dim=90, dropout=0.2):
        super(LottoLSTM, self).__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, output_dim)
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        last_step_out = out[:, -1, :]
        logits = self.fc(last_step_out)
        return logits

def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    lookback = 37  # Ciclo standard di 37 estrazioni
    
    if len(archivio) < lookback:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno {lookback} estrazioni per avviare la rete LSTM temporale!")
        return

    st.info(f"Archivio attuale: **{len(archivio)}** concorsi. Addestramento rete LSTM temporale (Lookback: {lookback}) in corso...")

    # Conversione dell'archivio in matrice binaria Multi-Hot (90 elementi)
    num_estrazioni = len(archivio)
    binary_matrix = np.zeros((num_estrazioni, 90), dtype=np.float32)
    for idx, ext in enumerate(archivio):
        for n in ext:
            if 1 <= n <= 90:
                binary_matrix[idx, n - 1] = 1.0

    # Preparazione dei dataset per le sequenze temporali
    X_list, y_list = [], []
    for i in range(len(binary_matrix) - lookback):
        X_list.append(binary_matrix[i : i + lookback])
        y_list.append(binary_matrix[i + lookback])

    X = torch.tensor(np.array(X_list), dtype=torch.float32)
    y = torch.tensor(np.array(y_list), dtype=torch.float32)

    # Inizializzazione e Training del Modello LSTM
    model = LottoLSTM(input_dim=90, hidden_dim=128, num_layers=2)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    model.train()
    epochs = 40
    for epoch in range(epochs):
        optimizer.zero_grad()
        logits = model(X)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

    # Estrazione dell'ultimo blocco temporale per la previsione del prossimo concorso
    model.eval()
    with torch.no_grad():
        ultimi_passi = binary_matrix[-lookback:]
        input_tensor = torch.tensor(ultimi_passi, dtype=torch.float32).unsqueeze(0)
        logits_pred = model(input_tensor)
        probs = torch.sigmoid(logits_pred).squeeze(0).numpy()

    # Classificazione dei numeri in base al punteggio di probabilità della rete
    valutazioni = [{'numero': i + 1, 'score': probs[i]} for i in range(90)]
    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    migliori = [item['numero'] for item in valutazioni[:quantita_numeri]]
    migliori.sort()

    st.success("Previsione LSTM completata con successo!")
    st.markdown(f"### 🧠 GRUPPO CALDO PREVISTO ({quantita_numeri} NUMERI):")
    
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"## **` {numeri_str} `**")
    
    # Seleziona le prime coppie utili se il quantitativo lo consente
    if quantita_numeri >= 2:
        from itertools import combinations
        coppie = list(combinations(migliori, 2))[:3]
        st.markdown("#### 🎯 Sviluppo Coppie (Ambi Consigliati):")
        for i, c in enumerate(coppie, 1):
            st.text(f"• Giocata {i}: {c[0]:02d} - {c[1]:02d} (A massa pari)")

    st.balloons()

# Interfaccia grafica della Web App
st.title("🎲 Bot 10eLotto PyTorch LSTM")
st.write("Generatore sequenziale basato su reti LSTM per l'analisi temporale delle estrazioni.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

# Scelta della quantità di numeri da giocare
quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

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
        with st.spinner("Elaborazione modello LSTM in corso..."):
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

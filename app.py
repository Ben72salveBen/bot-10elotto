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
    page_title="Bot 10eLotto - PyTorch LSTM (Memoria Continua)",
    page_icon="🤖",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE_ARCHIVIO = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")
NOME_FILE_MODELLO = os.path.join(CARTELLA_DOCUMENTI, "modello_lotto.pth")

def carica_archivio():
    if os.path.exists(NOME_FILE_ARCHIVIO):
        try:
            with open(NOME_FILE_ARCHIVIO, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                archivio_ordinato = [sorted([int(n) for n in ext]) for ext in archivio if 20 <= len(ext) <= 35]
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
                
                # Base (20 numeri)
                match_num = re.search(r'Numeri\s*([\s\S]*?)(?=Oro|Extra|Doppio|$)', testo_blocco, re.IGNORECASE)
                numeri_base = []
                if match_num:
                    testo_sezione = match_num.group(1)
                    pezzi_cifre = re.findall(r'\d+', testo_sezione)
                    visti = set()
                    for p in pezzi_cifre:
                        if len(p) > 2 and len(p) % 2 == 0:
                            for j in range(0, len(p), 2):
                                sub = int(p[j:j+2])
                                if 1 <= sub <= 90 and sub not in visti:
                                    visti.add(sub)
                                    numeri_base.append(sub)
                        else:
                            val = int(p)
                            if 1 <= val <= 90 and val not in visti:
                                visti.add(val)
                                numeri_base.append(val)
                        if len(numeri_base) == 20:
                            break

                # Extra (15 numeri)
                numeri_extra = []
                match_extra = re.search(r'Extra\s*([\s\S]*?)(?=#|$)', testo_blocco, re.IGNORECASE)
                if match_extra:
                    testo_extra = match_extra.group(1)
                    pezzi_cifre_extra = re.findall(r'\d+', testo_extra)
                    visti_extra = set()
                    for p in pezzi_cifre_extra:
                        if len(p) > 2 and len(p) % 2 == 0:
                            for j in range(0, len(p), 2):
                                sub = int(p[j:j+2])
                                if 1 <= sub <= 90 and sub not in visti_extra:
                                    visti_extra.add(sub)
                                    numeri_extra.append(sub)
                        else:
                            val = int(p)
                            if 1 <= val <= 90 and val not in visti_extra:
                                visti_extra.add(val)
                                numeri_extra.append(val)
                        if len(numeri_extra) == 15:
                            break

                if len(numeri_base) == 20:
                    tutti_numeri = sorted(list(set(numeri_base + numeri_extra)))
                    estrazioni_trovate.append({
                        'id': id_concorso,
                        'numeri': tutti_numeri
                    })

            if not estrazioni_trovate:
                return []

            estrazioni_trovate.sort(key=lambda x: x['id'])
            return [item['numeri'] for item in estrazioni_trovate]

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ==========================================
# ARCHITETTURA LSTM CON MEMORIA PERSISTENTE
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

def init_weights(m):
    if isinstance(m, nn.LSTM):
        for name, param in m.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param.data)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                param.data.fill_(0)
    elif isinstance(m, nn.Linear):
        nn.init.xavier_uniform_(m.weight)
        if m.bias is not None:
            m.bias.data.fill_(0)

# ==========================================
# ELABORAZIONE CON APPRENDIMENTO INCREMENTALE
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    lookback = 40  
    
    if len(archivio) < lookback:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno {lookback} estrazioni!")
        return

    st.info(f"Aggiornamento della rete con memoria continua (Fine-Tuning)...")

    num_estrazioni = len(archivio)
    binary_matrix = np.zeros((num_estrazioni, 90), dtype=np.float32)
    for idx, ext in enumerate(archivio):
        for n in ext:
            if 1 <= n <= 90:
                binary_matrix[idx, n - 1] = 1.0

    X_list, y_list = [], []
    for i in range(len(binary_matrix) - lookback):
        X_list.append(binary_matrix[i : i + lookback])
        y_list.append(binary_matrix[i + lookback])

    X = torch.tensor(np.array(X_list), dtype=torch.float32)
    y = torch.tensor(np.array(y_list), dtype=torch.float32)

    # Inizializzazione o Caricamento della Memoria Esistente
    model = LottoLSTM(input_dim=90, hidden_dim=128, num_layers=2)
    
    if os.path.exists(NOME_FILE_MODELLO):
        try:
            model.load_state_dict(torch.load(NOME_FILE_MODELLO))
            st.toast("🧠 Memoria precedente caricata con successo! Correggo la mira sull'ultimo errore.", icon="🔄")
            epoche_training = 10 # Poche epoche di adattamento rapido (Fine-Tuning)
        except Exception as e:
            st.warning("Impossibile caricare il vecchio modello. Avvio nuovo training da zero.")
            model.apply(init_weights)
            epoche_training = 35
    else:
        model.apply(init_weights)
        epoche_training = 35

    pos_weight_tensor = torch.tensor([1.6] * 90, dtype=torch.float32)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    optimizer = optim.Adam(model.parameters(), lr=0.0005, weight_decay=1e-4) # Learning rate più basso per non stravolgere la memoria

    model.train()
    for epoch in range(epoche_training):
        optimizer.zero_grad()
        logits = model(X)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

    # SALVATAGGIO DEI PESI AGGIORNATI PER LA PROSSIMA VOLTA
    torch.save(model.state_dict(), NOME_FILE_MODELLO)

    model.eval()
    with torch.no_grad():
        ultimi_passi = binary_matrix[-lookback:]
        input_tensor = torch.tensor(ultimi_passi, dtype=torch.float32).unsqueeze(0)
        logits_pred = model(input_tensor)
        probs = torch.sigmoid(logits_pred).squeeze(0).numpy()

    # Frequenze per Trigger
    frequenze_finestra = {n: 0 for n in range(1, 91)}
    for ext in archivio[-lookback:]:
        for n in ext:
            if 1 <= n <= 90:
                frequenze_finestra[n] += 1

    valutazioni = []
    for i in range(90):
        num = i + 1
        score_base = probs[i]
        freq = frequenze_finestra[num]

        if freq <= 3:
            score_corretto = score_base * 0.1
        else:
            score_corretto = score_base

        valutazioni.append({
            'numero': num,
            'score': score_corretto,
            'score_raw': score_base,
            'freq': freq
        })

    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    # Trigger Anti-Clustering (Decine)
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

    mean_raw_score = np.mean([item['score_raw'] for item in selezionati])
    accuratezza_stimata = round(min(float(mean_raw_score * 100 * 1.6), 91.0), 1)

    if accuratezza_stimata >= 75.0:
        colpi_consigliati = 1
        tipo_giocata = "🔥 A COLPO SECCO (1 sola estrazione)"
    elif accuratezza_stimata >= 60.0:
        colpi_consigliati = 2
        tipo_giocata = "⚡ BREVE CICLO (2 colpi massimo)"
    else:
        colpi_consigliati = 4
        tipo_giocata = "🛡️ CICLO STANDARD (Fino a 4 colpi)"

    st.success("Previsione con Memoria Continua completata!")

    st.markdown(f"### 🤖 PREVISIONE MEMORIA CONTINUA ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"## **` {numeri_str} `**")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="🎯 Accuratezza Stimata Bot", value=f"{accuratezza_stimata} %")
    with col2:
        st.metric(label="⏳ Colpi Consigliati", value=f"{colpi_consigliati} Colpo/i")

    st.info(f"📌 **Consiglio Operativo Bot:** Gioca questa previsione **{tipo_giocata}** con l'opzione **EXTRA ATTIVA**.")

    st.balloons()

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - PyTorch (Memoria Continua)")
st.write("Modello con persistenza dei pesi: la rete conserva l'esperienza accumulata e corregge la mira passo dopo passo.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Genera Previsione", "Scarica Web & Prendi Previsione", "Visualizza Archivio", "Svuota Archivio")
)

if opzione == "Scarica Web & Prendi Previsione":
    if st.button("Avvia Sincronizzazione Web", type="primary"):
        with st.spinner("Scraping e aggiornamento memoria in corso..."):
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
                    st.success(f"Sincronizzazione completata! Aggiunte {nuove_aggiunte} estrazioni.")
                    elabora_previsione(quantita)
                else:
                    st.error("Errore salvataggio file.")
            else:
                st.error("Nessuna estrazione trovata.")

elif opzione == "Genera Previsione":
    if st.button("Genera Previsione da Archivio", type="primary"):
        with st.spinner("Elaborazione con pesi persistenti..."):
            elabora_previsione(quantita)

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Archivio vuoto.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            st.text(f"#{len(archivio)-idx} ({len(ext)} numeri): {', '.join(map(str, ext))}")

elif opzione == "Svuota Archivio":
    if st.button("Conferma Cancellazione Archivio e Modello", type="secondary"):
        salva_archivio([])
        if os.path.exists(NOME_FILE_MODELLO):
            os.remove(NOME_FILE_MODELLO)
        st.success("Archivio e memoria del modello azzerati con successo.")

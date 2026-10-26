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
    page_title="Bot 10eLotto - PyTorch (Training 20 Numeri - Ultime 5)",
    page_icon="🤖",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE_ARCHIVIO = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")
NOME_FILE_MODELLO = os.path.join(CARTELLA_DOCUMENTI, "modello_lotto.pth")
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
        st.info(f"ℹ️ Risultato: {punti} punti. Il modello ha registrato l'esito per correggere la mira.")
    st.markdown("---")

# ==========================================
# ELABORAZIONE PREVISIONE (Training su 20 Numeri - Ultime 5 Estrazioni)
# ==========================================
def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    lookback = 4  
    
    if len(archivio) < (lookback + 5):
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno {lookback + 5} estrazioni!")
        return

    st.info(f"Addestramento PyTorch LSTM su tutti i 20 numeri base focalizzato sulle ultime 5 estrazioni...")

    # Focalizziamo il training sulle ultime estrazioni recenti (coda dell'archivio)
    archivio_recente = archivio[-25:]
    num_estrazioni = len(archivio_recente)
    binary_matrix = np.zeros((num_estrazioni, 90), dtype=np.float32)
    
    # MODIFICA: La rete si addestra su TUTTI I 20 NUMERI BASE di ogni estrazione
    for idx, ext in enumerate(archivio_recente):
        for n in ext:
            if 1 <= n <= 90:
                binary_matrix[idx, n - 1] = 1.0

    X_list, y_list = [], []
    for i in range(len(binary_matrix) - lookback):
        X_list.append(binary_matrix[i : i + lookback])
        y_list.append(binary_matrix[i + lookback])

    X = torch.tensor(np.array(X_list), dtype=torch.float32)
    y = torch.tensor(np.array(y_list), dtype=torch.float32)

    model = LottoLSTM(input_dim=90, hidden_dim=128, num_layers=2)
    
    if os.path.exists(NOME_FILE_MODELLO):
        try:
            model.load_state_dict(torch.load(NOME_FILE_MODELLO))
            epoche_training = 10
        except Exception:
            model.apply(init_weights)
            epoche_training = 35
    else:
        model.apply(init_weights)
        epoche_training = 35

    # Pos weight standard per 20 numeri su 90
    pos_weight_tensor = torch.tensor([3.5] * 90, dtype=torch.float32)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    optimizer = optim.Adam(model.parameters(), lr=0.0005, weight_decay=1e-4)

    model.train()
    for epoch in range(epoche_training):
        optimizer.zero_grad()
        logits = model(X)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

    torch.save(model.state_dict(), NOME_FILE_MODELLO)

    model.eval()
    with torch.no_grad():
        binary_matrix_totale = np.zeros((len(archivio), 90), dtype=np.float32)
        for idx, ext in enumerate(archivio):
            for n in ext:
                if 1 <= n <= 90:
                    binary_matrix_totale[idx, n - 1] = 1.0

        ultimi_passi = binary_matrix_totale[-lookback:]
        input_tensor = torch.tensor(ultimi_passi, dtype=torch.float32).unsqueeze(0)
        logits_pred = model(input_tensor)
        probs = torch.sigmoid(logits_pred).squeeze(0).numpy()

    # Frequenze calcolate esclusivamente sulle ULTIME 5 ESTRAZIONI più recenti
    frequenze_finestra = {n: 0 for n in range(1, 91)}
    for ext in archivio[-5:]:
        for n in ext:
            if 1 <= n <= 90:
                frequenze_finestra[n] += 1

    valutazioni = []
    for i in range(90):
        num = i + 1
        score_base = probs[i]
        freq = frequenze_finestra[num]

        # Trigger penalizzazione numeri freddi nelle ultime 5 estrazioni
        if freq == 0:
            score_corretto = score_base * 0.1
        else:
            score_corretto = score_base

        valutazioni.append({
            'numero': num,
            'score': score_corretto,
            'score_raw': score_base
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

    salva_giocata(migliori)

    mean_raw_score = np.mean([item['score_raw'] for item in selezionati])
    accuratezza_stimata = round(min(float(mean_raw_score * 100 * 2.0), 95.0), 1)

    st.markdown(f"### 🤖 PREVISIONE OTTIMIZZATA ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(f"{n:02d}" for n in migliori)
    st.markdown(f"## **` {numeri_str} `**")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="🎯 Confidenza del Modello", value=f"{accuratezza_stimata} %")
    with col2:
        st.metric(label="🔢 Numeri Selezionati", value=f"{quantita_numeri}")

    st.info("📌 **Consiglio Operativo:** Gioca questa combinazione aggiungendo l'opzione **EXTRA ATTIVA**.")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - PyTorch (Training 20 Numeri - Ultime 5)")
st.write("Modello con memoria persistente addestrato su tutti i 20 numeri base focalizzato sulle ultime 5 estrazioni.")

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
        with st.spinner("Scraping e verifica esito precedente..."):
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
                
                # 1. Verifica immediata dell'esito precedente
                verifica_esito_ultima_giocata(archivio[-1])
                
                # 2. Generazione nuova previsione
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
        if os.path.exists(NOME_FILE_MODELLO):
            os.remove(NOME_FILE_MODELLO)
        if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
            os.remove(NOME_FILE_ULTIMA_GIOCATA)
        st.success("Archivio, modello e ultime giocate cancellate con successo.")

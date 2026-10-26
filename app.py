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
    page_title="Bot 10eLotto - PyTorch (Sistema 5 Decine)",
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

def salva_giocata(sistema_decine):
    try:
        with open(NOME_FILE_ULTIMA_GIOCATA, "w", encoding="utf-8") as f:
            json.dump(sistema_decine, f, ensure_ascii=False, indent=4)
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
    
    vincite_trovate = False

    for idx, decina in enumerate(ultima_giocata):
        presi = set(decina).intersection(set_estratto)
        punti = len(presi)
        
        if punti >= 5:
            vincite_trovate = True
            st.success(f"🎉 **DECINA {idx+1}: VINCENTE! {punti} PUNTI REALIZZATI!** (Numeri indovinati: {sorted(list(presi))})")
        else:
            st.write(f"• Decina {idx+1}: {punti} punti su 10 (Indovinati: {sorted(list(presi)) if punti > 0 else 'Nessuno'})")

    if vincite_trovate:
        st.balloons()
    else:
        st.info("ℹ️ Nessuna decina ha raggiunto la soglia minima di vincita (5 punti). Il modello ha registrato l'errore per correggere la mira.")
    st.markdown("---")

# ==========================================
# ELABORAZIONE PREVISIONE CON SISTEMA 5 DECINE
# ==========================================
def elabora_previsione():
    archivio = carica_archivio()
    lookback = 40  
    
    if len(archivio) < lookback:
        st.warning(f"L'archivio contiene {len(archivio)} estrazioni. Servono almeno {lookback} estrazioni!")
        return

    st.info(f"Addestramento PyTorch LSTM solo su Base + Generazione Sistema 5 Decine...")

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
            'score_raw': score_base
        })

    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    # Trigger Anti-Clustering (Decine max 3 numeri sui 20 totali)
    max_per_decina = 3
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

    # Selezioniamo i TOP 20 NUMERI scelti dall'IA
    top_20 = [item['numero'] for item in valutazioni_filtrate[:20]]

    # ==========================================
    # SVILUPPO SISTEMA RIDOTTO (PROPOSTA 1: 5 DECINE)
    # ==========================================
    N = top_20
    d1 = sorted([N[0], N[1], N[2], N[3], N[4], N[5], N[6], N[7], N[8], N[9]])
    d2 = sorted([N[10], N[11], N[12], N[13], N[14], N[15], N[16], N[17], N[18], N[19]])
    d3 = sorted([N[0], N[1], N[2], N[3], N[4], N[10], N[11], N[12], N[13], N[14]])
    d4 = sorted([N[5], N[6], N[7], N[8], N[9], N[15], N[16], N[17], N[18], N[19]])
    d5 = sorted([N[0], N[2], N[4], N[6], N[8], N[10], N[12], N[14], N[16], N[18]])

    sistema_5_decine = [d1, d2, d3, d4, d5]
    salva_giocata(sistema_5_decine)

    st.markdown("### 🎯 NUOVO SISTEMA RIDOTTO (5 DECINE PROPOSTA 1):")
    st.write("I 20 migliori numeri selezionati da PyTorch sono stati sviluppati nelle seguenti 5 schedine:")

    for idx, dec in enumerate(sistema_5_decine):
        dec_str = " - ".join(f"{n:02d}" for n in dec)
        st.markdown(f"**Decina #{idx+1}:** ` {dec_str} `")

    st.info("📌 **Nota Operativa:** Gioca queste 5 decine aggiungendo l'opzione **EXTRA ATTIVA** per massimizzare le probabilità di vincita.")

# Interfaccia Grafica Streamlit
st.title("🤖 Bot 10eLotto - PyTorch (Sistema 5 Decine)")
st.write("Addestramento basato unicamente sull'archivio BASE con sviluppo automatico in sistema ridotto a 5 decine.")

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
                
                # 1. Verifica immediata dell'esito della giocata precedente
                verifica_esito_ultima_giocata(archivio[-1])
                
                # 2. Generazione della nuova previsione
                elabora_previsione()
            else:
                st.error("Nessuna estrazione trovata sul web.")

elif opzione == "Genera Solamente Previsione":
    if st.button("Genera Previsione da Archivio Locale", type="primary"):
        with st.spinner("Elaborazione sistema in corso..."):
            elabora_previsione()

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni (Solo Base)")
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

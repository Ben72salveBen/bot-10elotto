import os
import json
import re
import ssl
import cloudscraper
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import streamlit as st

# Configurazione della pagina per adattarsi bene ai dispositivi mobili
st.set_page_config(
    page_title="Bot 10eLotto PyTorch",
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
    
    # Sfruttiamo cloudscraper per bypassare le protezioni anti-bot sul cloud
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'firefox',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    try:
        response = scraper.get(url, timeout=15)
        if response.status_code != 200:
            st.error(f"Errore HTTP: {response.status_code}")
            return []
            
        html = response.text
        
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

class Net10eLotto(nn.Module):
    def __init__(self):
        super(Net10eLotto, self).__init__()
        self.fc1 = nn.Linear(3, 32)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.1)
        self.fc2 = nn.Linear(32, 16)
        self.fc3 = nn.Linear(16, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out = self.fc1(x)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        out = self.relu(out)
        out = self.fc3(out)
        out = self.sigmoid(out)
        return out

def elabora_previsione(quantita_numeri):
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.warning("L'archivio è vuoto. Scarica prima le estrazioni!")
        return

    st.info(f"Archivio attuale: **{len(archivio)}** estrazioni registrate. Addestramento modello PyTorch in corso...")

    freq_totale = np.zeros(91)
    freq_recente = np.zeros(91)
    ritardi = np.zeros(91)
    ultimo_visto = np.full(91, -1)

    sessioni_recente = archivio[-10:]

    for idx, ext in enumerate(archivio):
        for n in ext:
            if 1 <= n <= 90:
                freq_totale[n] += 1
                ultimo_visto[n] = idx

    for ext in sessioni_recente:
        for n in ext:
            if 1 <= n <= 90:
                freq_recente[n] += 1

    tot_archivio = len(archivio)
    for i in range(1, 91):
        ritardi[i] = tot_archivio if ultimo_visto[i] == -1 else (tot_archivio - 1 - ultimo_visto[i])

    max_f_tot = max(freq_totale.max(), 1.0)
    max_f_rec = max(freq_recente.max(), 1.0)
    max_r = max(ritardi.max(), 1.0)

    X_data = []
    y_data = []

    for i in range(1, 91):
        f_tot_norm = freq_totale[i] / max_f_tot
        f_rec_norm = freq_recente[i] / max_f_rec
        ritardo_norm = ritardi[i] / max_r

        x_feat = [f_tot_norm, f_rec_norm, ritardo_norm]
        target_score = (0.5 * f_rec_norm) + (0.3 * f_tot_norm) + (0.2 * (1.0 - ritardo_norm))
        target_score = max(0.0, min(1.0, target_score))
        
        X_data.append(x_feat)
        y_data.append([target_score])

    X = torch.tensor(X_data, dtype=torch.float32)
    y = torch.tensor(y_data, dtype=torch.float32)

    model = Net10eLotto()
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.015)

    model.train()
    for epoch in range(150):
        optimizer.zero_grad()
        outputs = model(X)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        preds = model(X).numpy().flatten()

    valutazioni = [{'numero': i + 1, 'score': preds[i]} for i in range(90)]
    valutazioni.sort(key=lambda x: x['score'], reverse=True)

    migliori = [item['numero'] for item in valutazioni[:quantita_numeri]]
    migliori.sort()

    st.success("Previsione completata con successo!")
    st.markdown(f"### 🧠 PREVISIONE PYTORCH ({quantita_numeri} NUMERI):")
    
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"## **` {numeri_str} `**")
    st.balloons()

# Interfaccia grafica della Web App
st.title("🎲 Bot 10eLotto PyTorch")
st.write("Generatore intelligente di previsioni statistiche per il 10eLotto ogni 5 minuti.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.sidebar.slider("Quanti numeri vuoi giocare?", min_value=1, max_value=10, value=4)

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
        with st.spinner("Elaborazione modello in corso..."):
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

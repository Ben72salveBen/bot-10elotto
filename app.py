import os
import json
import re
import urllib.request
import ssl
import math
from itertools import combinations
from collections import Counter
import streamlit as st
import torch
import torch.nn as nn
import torch.optim as optim

st.set_page_config(
    page_title="Bot 10eLotto - Doppia Strategia & Cassa",
    page_icon="⚡",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else "."
NOME_FILE = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")

def carica_archivio():
    if os.path.exists(NOME_FILE):
        try:
            with open(NOME_FILE, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                return [sorted([int(n) for n in ext]) for ext in archivio if len(ext) >= 10]
        except Exception as e:
            st.error(f"Errore lettura archivio: {e}")
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
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
            if "Domande Frequenti" in html: html = html.split("Domande Frequenti")[0]
            if "Seleziona Numeri" in html: html = html.split("Seleziona Numeri")[-1]
            
            estrazioni_trovate = []
            blocchi = re.split(r'#(\d+)', html)
            for i in range(1, len(blocchi), 2):
                id_concorso = int(blocchi[i])
                testo_blocco = blocchi[i+1]
                if "Numeri" not in testo_blocco and "numeri" not in testo_blocco: continue
                match_num = re.search(r'Numeri\s*([\s\S]*?)(?=Oro|Extra|Doppio|$)', testo_blocco, re.IGNORECASE)
                if match_num:
                    testo_sezione = match_num.group(1)
                    pezzi_cifre = re.findall(r'\d+', testo_sezione)
                    numeri_validi, visti = [], set()
                    for p in pezzi_cifre:
                        if len(p) > 2 and len(p) % 2 == 0:
                            for j in range(0, len(p), 2):
                                sub = int(p[j:j+2])
                                if 1 <= sub <= 90 and sub not in visti:
                                    visti.add(sub); numeri_validi.append(sub)
                        else:
                            val = int(p)
                            if 1 <= val <= 90 and val not in visti:
                                visti.add(val); numeri_validi.append(val)
                        if len(numeri_validi) == 20: break
                    if len(numeri_validi) >= 10:
                        numeri_validi.sort()
                        estrazioni_trovate.append({'id': id_concorso, 'numeri': numeri_validi})
            if not estrazioni_trovate: return []
            estrazioni_trovate.sort(key=lambda x: x['id'])
            return [item['numeri'] for item in estrazioni_trovate]
    except Exception as e:
        st.error(f"Errore di connessione: {e}")
        return []

# Calcolo Sollecitazione
def calcola_sollecitazione(archivio, quantita):
    tot_estrazioni = len(archivio)
    freq_globale = Counter()
    for ext in archivio:
        for n in ext: freq_globale[n] += 1

    finestra_corta = min(15, tot_estrazioni)
    ultime_15 = archivio[-finestra_corta:]
    freq_recente = Counter()
    for ext in ultime_15:
        for n in ext: freq_recente[n] += 1

    p = 20 / 90.0
    media_attesa = finestra_corta * p
    dev_std = math.sqrt(finestra_corta * p * (1 - p)) if finestra_corta > 0 else 1

    punteggi = {}
    for n in range(1, 91):
        f_rec = freq_recente[n]
        z_score = (f_rec - media_attesa) / dev_std if dev_std > 0 else 0
        f_globale = freq_globale[n]
        media_globale_attesa = tot_estrazioni * p
        trend_storico = (f_globale - media_globale_attesa) / (math.sqrt(tot_estrazioni * p * (1 - p)) + 1e-5)
        punteggi[n] = (z_score * 0.7) + (trend_storico * 0.3)

    numeri_ordinati = sorted(punteggi.items(), key=lambda x: x[1], reverse=True)
    return sorted([int(item[0]) for item in numeri_ordinati[:quantita]])

# Calcolo PyTorch Gruppi
class LottoGroupOptimizer(nn.Module):
    def __init__(self):
        super(LottoGroupOptimizer, self).__init__()
        self.weights = nn.Parameter(torch.randn(3, 1, dtype=torch.float32) * 0.1)
        self.bias = nn.Parameter(torch.zeros(1, dtype=torch.float32))

    def forward(self, x):
        return torch.matmul(x, self.weights).squeeze() + self.bias

def calcola_pytorch_gruppi(archivio, quantita):
    tot_estrazioni = len(archivio)
    if tot_estrazioni < 10:
        return sorted([int(n) for n in list(range(1, quantita + 1))])

    f_recenti = Counter()
    finestra = min(15, tot_estrazioni)
    for ext in archivio[-finestra:]:
        for n in ext: f_recenti[n] += 1
        
    candidati_base = [n for n, f in f_recenti.most_common(30)]
    if len(candidati_base) < quantita:
        candidati_base = list(range(1, 40))

    tutte_comb = list(combinations(candidati_base, quantita))
    if len(tutte_comb) > 100:
        tutte_comb = tutte_comb[:100]

    features_list = []
    finestra_co_1 = min(10, tot_estrazioni)
    finestra_co_2 = min(30, tot_estrazioni)
    
    for comb in tutte_comb:
        cset = set(comb)
        co_rec = sum(1 for ext in archivio[-finestra_co_1:] if len(cset.intersection(ext)) >= 2)
        co_med = sum(1 for ext in archivio[-finestra_co_2:] if len(cset.intersection(ext)) >= 2)
        trend_comp = sum(f_recenti[n] for n in comb) / float(quantita)
        features_list.append([float(co_rec), float(co_med), float(trend_comp)])

    x_tensor = torch.tensor(features_list, dtype=torch.float32)
    model = LottoGroupOptimizer()
    optimizer = optim.Adam(model.parameters(), lr=0.05)

    for epoch in range(40):
        optimizer.zero_grad()
        scores = model(x_tensor)
        ultima_estrazione = set(archivio[-1])
        targets = torch.tensor([float(len(set(c).intersection(ultima_estrazione))) for c in tutte_comb], dtype=torch.float32)
        loss = nn.MSELoss()(scores, targets)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        final_scores = model(x_tensor)
        best_idx = torch.argmax(final_scores).item()
        
    return sorted([int(n) for n in tutte_comb[best_idx]])

# Interfaccia Streamlit
st.title("⚡ Bot 10eLotto - Doppia Strategia")
archivio = carica_archivio()

st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio))
st.sidebar.markdown("---")

if st.sidebar.button("Sincronizza Archivio da Web"):
    with st.spinner("Scaricamento estrazioni..."):
        estrazioni = scarica_estrazioni_con_bypass()
        if estrazioni:
            set_esistenti = {tuple(ext) for ext in archivio}
            aggiunte = 0
            for ext in estrazioni:
                if tuple(ext) not in set_esistenti:
                    archivio.append(ext); aggiunte += 1
            salva_archivio(archivio)
            st.success(f"Archivio aggiornato! Aggiunte {aggiunte} estrazioni.")
        else:
            st.error("Impossibile scaricare dal web.")

strategia_scelta = st.radio("Seleziona Strategia:", ("📈 Indice di Sollecitazione", "🔥 PyTorch Neurale (Gruppi)"))
quantita_numeri = st.slider("Quanti numeri vuoi giocare?", min_value=2, max_value=6, value=3, step=1)

if strategia_scelta == "📈 Indice di Sollecitazione":
    st.subheader("📈 Strategia 1: Indice di Sollecitazione")
    if st.button("Genera Previsione Sollecitata", type="primary"):
        if len(archivio) < 5:
            st.warning("Carica prima l'archivio dal menu laterale!")
        else:
            numeri = calcola_sollecitazione(archivio, quantita_numeri)
            st.success("Previsione pronta:")
            st.markdown(f"## **` {', '.join([f'{n:02d}' for n in numeri])} `**")
else:
    st.subheader("🔥 Strategia 2: PyTorch Neurale (Gruppi)")
    if st.button("Avvia Ottimizzazione PyTorch", type="primary"):
        if len(archivio) < 5:
            st.warning("Carica prima l'archivio dal menu laterale!")
        else:
            numeri = calcola_pytorch_gruppi(archivio, quantita_numeri)
            st.success("Combinazione ottimizzata pronta:")
            st.markdown(f"## **` {', '.join([f'{n:02d}' for n in numeri])} `**")

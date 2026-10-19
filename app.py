import os
import json
import re
import urllib.request
import ssl
import math
from collections import Counter
import streamlit as st
import torch
import torch.nn as nn
import torch.optim as optim

# Configurazione della pagina per dispositivi mobili
st.set_page_config(
    page_title="Bot 10eLotto Multi-Sistema",
    page_icon="⚡",
    layout="centered"
)

# Percorso di salvataggio
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
# METODO 1: INDICE DI SOLLECITAZIONE (STATISTICA)
# ==========================================
def calcola_sollecitazione(archivio, quantita):
    tot_estrazioni = len(archivio)
    freq_globale = Counter()
    for ext in archivio:
        for n in ext: freq_globale[n] += 1

    finestra_corta = 15
    ultime_15 = archivio[-finestra_corta:]
    freq_recente = Counter()
    for ext in ultime_15:
        for n in ext: freq_recente[n] += 1

    p = 20 / 90.0
    media_attesa = finestra_corta * p
    dev_std = math.sqrt(finestra_corta * p * (1 - p))

    punteggi = {}
    for n in range(1, 91):
        f_rec = freq_recente[n]
        z_score = (f_rec - media_attesa) / dev_std
        f_globale = freq_globale[n]
        media_globale_attesa = tot_estrazioni * p
        trend_storico = (f_globale - media_globale_attesa) / math.sqrt(tot_estrazioni * p * (1 - p))
        indice = (z_score * 0.7) + (trend_storico * 0.3)
        punteggi[n] = (indice, f_rec, f_globale)

    numeri_ordinati = sorted(punteggi.items(), key=lambda x: x[1][0], reverse=True)
    top_numeri = sorted([item[0] for item in numeri_ordinati[:quantita]])
    return top_numeri, punteggi

# ==========================================
# METODO 2: OTTIMIZZATORE NEURALE PYTORCH
# ==========================================
class LottoOptimizerNet(nn.Module):
    def __init__(self):
        super(LottoOptimizerNet, self).__init__()
        self.weights = nn.Parameter(torch.randn(3, 1, dtype=torch.float32) * 0.1)
        self.bias = nn.Parameter(torch.zeros(1, dtype=torch.float32))

    def forward(self, x):
        return torch.matmul(x, self.weights).squeeze() + self.bias

def estrai_features(archivio, idx_corrente):
    storico = archivio[:idx_corrente]
    f_5, f_15, f_tot = Counter(), Counter(), Counter()
    for ext in storico[-5:]: 
        for n in ext: f_5[n] += 1
    for ext in storico[-15:]: 
        for n in ext: f_15[n] += 1
    for ext in storico: 
        for n in ext: f_tot[n] += 1
        
    tot = len(storico)
    p = 20.0 / 90.0
    features = []
    for n in range(1, 91):
        v5 = f_5[n] / 5.0
        v15 = f_15[n] / 15.0
        v_storico = (f_tot[n] - (tot * p)) / (math.sqrt(tot * p * (1 - p)) + 1e-5)
        features.append([v5, v15, v_storico])
    return torch.tensor(features, dtype=torch.float32)

def calcola_pytorch(archivio, quantita):
    tot_estrazioni = len(archivio)
    model = LottoOptimizerNet()
    optimizer = optim.Adam(model.parameters(), lr=0.05)
    finestra_train = min(50, tot_estrazioni - 20)
    
    for epoch in range(120):
        optimizer.zero_grad()
        loss = 0.0
        start_idx = tot_estrazioni - finestra_train
        for idx in range(start_idx, tot_estrazioni - 1):
            x = estrai_features(archivio, idx)
            scores = model(x)
            target_ext = archivio[idx]
            target_tensor = torch.zeros(90, dtype=torch.float32)
            for n in target_ext: target_tensor[n-1] = 1.0
            probs = torch.sigmoid(scores)
            bce_loss = -(target_tensor * torch.log(probs + 1e-6) + (1 - target_tensor) * torch.log(1 - probs + 1e-6)).mean()
            loss = loss + bce_loss
        loss = loss / finestra_train
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        x_current = estrai_features(archivio, tot_estrazioni)
        final_scores = torch.sigmoid(model(x_current))
        
    _, indici = torch.sort(final_scores, descending=True)
    top_numeri = sorted([int(indici[i].item()) + 1 for i in range(quantita)])
    pesi = model.weights.detach().numpy().flatten()
    return top_numeri, pesi

# ==========================================
# INTERFACCIA STREAMLIT
# ==========================================
st.title("⚡ Bot 10eLotto Multi-Sistema")
st.write("Scegli il motore di calcolo o confronta le previsioni in tempo reale.")

archivio = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio))

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

scelta_sistema = st.sidebar.radio(
    "Seleziona Modalità:",
    (
        "📈 Indice di Sollecitazione", 
        "🔥 Ottimizzatore PyTorch", 
        "⚔️ Confronto Entrambi i Sistemi",
        "📥 Sincronizza da Web", 
        "📁 Visualizza Archivio", 
        "🗑️ Svuota Archivio"
    )
)

# Slider dinamico per scegliere quanti numeri generare (da 2 a 6)
st.sidebar.markdown("---")
quantita_numeri = st.sidebar.slider("Quanti numeri vuoi giocare?", min_value=2, max_value=6, value=3, step=1)

# ESECUZIONE AZIONI
if scelta_sistema == "📈 Indice di Sollecitazione":
    if st.button("Calcola Previsione Sollecitata", type="primary"):
        if len(archivio) < 20:
            st.warning("Servono almeno 20 estrazioni nell'archivio!")
        else:
            with st.spinner("Analisi statistica in corso..."):
                top, dettagli = calcola_sollecitazione(archivio, quantita_numeri)
                st.success("Previsione completata!")
                st.markdown(f"### 📈 PREVISIONE INDICE DI SOLLECITAZIONE ({quantita_numeri} NUMERI):")
                st.markdown(f"## **` {', '.join([f'{n:02d}' for n in top])} `**")
                
                st.markdown("---")
                st.markdown("#### 🔍 Dettaglio Valori:")
                for n in top:
                    ind, f_rec, f_glob = dettagli[n]
                    st.write(f"- **Numero {n:02d}**: Indice Sollecitazione = `{ind:.2f}` (Ultime 15: {f_rec}, Totali: {f_glob})")

elif scelta_sistema == "🔥 Ottimizzatore PyTorch":
    if st.button("Avvia Training PyTorch & Predici", type="primary"):
        if len(archivio) < 30:
            st.warning("Servono almeno 30 estrazioni nell'archivio!")
        else:
            with st.spinner("Addestramento della rete neurale in corso..."):
                top, pesi = calcola_pytorch(archivio, quantita_numeri)
                st.success("Ottimizzazione completata!")
                st.markdown(f"### 🔥 PREVISIONE NEURALE PYTORCH ({quantita_numeri} NUMERI):")
                st.markdown(f"## **` {', '.join([f'{n:02d}' for n in top])} `**")
                
                st.markdown("---")
                st.markdown("#### 🧠 Pesi Assegnati dal Modello:")
                st.write(f"- Peso Trend Brevissimo (5 concorsi): `{pesi[0]:.3f}`")
                st.write(f"- Peso Trend Medio (15 concorsi): `{pesi[1]:.3f}`")
                st.write(f"- Peso Regolarità Storica: `{pesi[2]:.3f}`")

elif scelta_sistema == "⚔️ Confronto Entrambi i Sistemi":
    if st.button("Esegui Analisi Comparativa", type="primary"):
        if len(archivio) < 30:
            st.warning("Servono almeno 30 estrazioni per il confronto!")
        else:
            with st.spinner("Calcolo combinato in corso..."):
                top_sol, _ = calcola_sollecitazione(archivio, quantita_numeri)
                top_py, _ = calcola_pytorch(archivio, quantita_numeri)
                
                # Calcolo della convergenza
                comuni = set(top_sol).intersection(set(top_py))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📈 Sollecitazione")
                    st.markdown(f"### `{', '.join([f'{n:02d}' for n in top_sol])}`")
                with col2:
                    st.markdown("### 🔥 PyTorch")
                    st.markdown(f"### `{', '.join([f'{n:02d}' for n in top_py])}`")
                
                st.markdown("---")
                if comuni:
                    st.success(f"🎯 **CONVERGENZA TROVATA!** I due sistemi concordano su questi numeri: **` {', '.join([f'{n:02d}' for n in sorted(list(comuni))])} `**")
                else:
                    st.info("I due sistemi hanno individuato numeri differenti. Puoi scegliere quale seguire o prendere 1 numero da ciascuno.")

elif scelta_sistema == "📥 Sincronizza da Web":
    if st.button("Avvia Sincronizzazione Web", type="primary"):
        with st.spinner("Connessione a Lottologia in corso..."):
            estrazioni = scarica_estrazioni_con_bypass()
            if len(estrazioni) > 0:
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
                else:
                    st.error("Impossibile salvare l'archivio.")
            else:
                st.error("Nessuna estrazione trovata.")

elif scelta_sistema == "📁 Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni Salvate")
    if len(archivio) == 0:
        st.info("Nessuna estrazione salvata.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            st.text(f"#{len(archivio)-idx}: {', '.join(map(str, ext))}")

elif scelta_sistema == "🗑️ Svuota Archivio":
    st.warning("Vuoi cancellare tutto l'archivio salvato?")
    if st.button("Conferma Cancellazione", type="secondary"):
        salva_archivio([])
        st.success("Archivio svuotato.")

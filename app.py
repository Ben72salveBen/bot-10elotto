import streamlit as st
import torch
import torch.nn as nn
import torch.optim as optim
from collections import Counter
from itertools import combinations

# ==========================================
# 1. ARCHITETTURA NEURALE PYTORCH (HOT 3)
# ==========================================
class MicroLottoNetHot3(nn.Module):
    def __init__(self, input_dim):
        super(MicroLottoNetHot3, self).__init__()
        self.fc1 = nn.Linear(input_dim, 8)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(8, 1)
        
    def forward(self, x):
        out = self.fc1(x)
        out = self.relu(out)
        return self.fc2(out).squeeze(-1)

# ==========================================
# 2. MOTORE DI CALCOLO SU ULTIME 3 ESTRAZIONI
# ==========================================
def calcola_previsione_hot3(archivio_completo, quantita):
    if len(archivio_completo) < 3:
        return [], 0.0, 0
    
    ultime_3 = archivio_completo[-3:]
    freq_3 = Counter()
    cadenze_3 = Counter()
    
    for ext in ultime_3:
        for n in ext:
            freq_3[n] += 1
            cadenze_3[n % 10] += 1
            
    cadenza_calda = cadenze_3.most_common(1)[0][0] if cadenze_3 else 0
    
    pool_caldi = set()
    for ext in ultime_3:
        for n in ext:
            pool_caldi.add(n)
            
    candidati = list(pool_caldi)
    if len(candidati) < quantita * 2:
        freq_10 = Counter()
        for ext in archivio_completo[-10:]:
            for n in ext: freq_10[n] += 1
        for n, f in freq_10.most_common(20):
            if n not in candidati:
                candidati.append(n)

    tutte_comb = list(combinations(candidati, quantita))
    if len(tutte_comb) > 60:
        tutte_comb = tutte_comb[:60]

    if not tutte_comb:
        fallback = [n for n, f in freq_3.most_common(quantita)]
        return sorted(fallback), 0.0, cadenza_calda

    ultima_est = set(ultime_3[-1])
    penultima_est = set(ultime_3[-2])
    
    features_list = []
    for comb in tutte_comb:
        cset = set(comb)
        pres_ultima = len(cset.intersection(ultima_est))
        pres_penultima = len(cset.intersection(penultima_est))
        score_freq = sum(freq_3[n] for n in comb)
        bonus_cadenza = sum(1 for n in comb if n % 10 == cadenza_calda)
        
        features_list.append([
            float(pres_ultima),
            float(pres_penultima),
            float(score_freq),
            float(bonus_cadenza)
        ])

    x_tensor = torch.tensor(features_list, dtype=torch.float32)
    model = MicroLottoNetHot3(input_dim=4)
    optimizer = optim.Adam(model.parameters(), lr=0.03, weight_decay=1e-3)
    criterion = nn.MSELoss()

    model.train()
    targets = torch.tensor([float(len(set(c).intersection(ultima_est))) for c in tutte_comb], dtype=torch.float32)
    for epoch in range(30):
        optimizer.zero_grad()
        scores = model(x_tensor)
        loss = criterion(scores, targets)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        final_scores = model(x_tensor)
        best_idx = torch.argmax(final_scores).item()
        
    quartina_scelta = sorted([int(n) for n in tutte_comb[best_idx]])
    punti_totali_scia = sum(freq_3[n] for n in quartina_scelta)
    max_possibile = 3 * quantita
    concentrazione = min(100.0, round((punti_totali_scia / max_possibile) * 100, 1))
    
    return quartina_scelta, concentrazione, cadenza_calda

# ==========================================
# 3. INTERFACCIA UTENTE STREAMLIT
# ==========================================
st.set_page_config(page_title="10eLotto Bot PyTorch Hot3", layout="centered")

st.title("🔥 Bot 10eLotto - Focus Ultime 3")
st.caption("Micro-Rete PyTorch + Filtro Cadenze + Tracciatore Esiti")

# Session state per archivio e storico previsioni
if 'archivio' not in st.session_state:
    st.session_state.archivio = []
if 'storico_previsioni' not in st.session_state:
    st.session_state.storico_previsioni = []

# Section Input Estrazioni
st.subheader("1. Inserimento Nuova Estrazione")
input_estrazione = st.text_input("Inserisci 20 numeri (separati da spazio o virgola):", placeholder="Es: 1 5 12 18 22 ...")

if st.button("➕ Aggiungi Estrazione"):
    try:
        numeri = [int(n) for n in input_estrazione.replace(",", " ").split() if n.strip().isdigit()]
        if len(numeri) == 20:
            st.session_state.archivio.append(numeri)
            
            # Controllo automatico dell'ultima previsione in attesa
            if st.session_state.storico_previsioni and st.session_state.storico_previsioni[-1]['esito'] is None:
                ultima_prev = set(st.session_state.storico_previsioni[-1]['numeri'])
                estratti_set = set(numeri)
                punti = len(ultima_prev.intersection(estratti_set))
                st.session_state.storico_previsioni[-1]['esito'] = punti
                st.toast(f"Verifica completata per l'ultima previsione: {punti} Punti presi!", icon="🎯")
                
            st.success(f"Estrazione aggiunta con successo! Totale in archivio: {len(st.session_state.archivio)}")
        else:
            st.error("Un'estrazione del 10eLotto deve contenere esattamente 20 numeri.")
    except Exception as e:
        st.error(f"Errore nell'inserimento: {e}")

# Info e Gestione Archivio
col_arch1, col_arch2 = st.columns(2)
with col_arch1:
    st.info(f"📊 **Estrazioni in archivio:** {len(st.session_state.archivio)}")

with col_arch2:
    if len(st.session_state.archivio) >= 50:
        if st.button("✂️ Resetta a 40 Estrazioni"):
            st.session_state.archivio = st.session_state.archivio[-40:]
            st.warning("Archivio tagliato: mantenute le ultime 40 estrazioni!")

# Section Previsione
st.subheader("2. Genera Previsione Bot")
quantita_numeri = st.selectbox("Quanti numeri vuoi giocare?", [2, 3, 4, 5, 6], index=2)

if st.button("🚀 Genera Previsione (Ultime 3 Estrazioni)"):
    if len(st.session_state.archivio) < 3:
        st.error("Servono almeno 3 estrazioni nell'archivio per calcolare la previsione!")
    else:
        previsione, concentrazione, cadenza_calda = calcola_previsione_hot3(st.session_state.archivio, quantita_numeri)
        
        # Salviamo la previsione nello storico in attesa dell'estrazione successiva
        st.session_state.storico_previsioni.append({
            'numeri': previsione,
            'concentrazione': concentrazione,
            'cadenza': cadenza_calda,
            'esito': None
        })
        
        st.markdown("---")
        st.markdown(f"### 🎯 Combinazione Consigliata: **{ ' - '.join(map(str, previsione)) }**")
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric(label="🔥 Indice di Concentrazione", value=f"{concentrazione}%")
        with c2:
            st.metric(label="🎯 Cadenza Calda", value=f"Finale {cadenza_calda}")
            
        if concentrazione >= 50.0:
            st.success("🟢 **Scia rovente:** Buona convergenza sulle ultime 3 estrazioni.")
        else:
            st.warning("🟡 **Scia debole:** Numeri frammentati. Valuta prudenza con l'Extra.")

# Section Storico Previsioni
if st.session_state.storico_previsioni:
    st.subheader("3. Storico Previsioni e Verifiche")
    with st.expander("📜 Registro delle Previsioni Inserite", expanded=True):
        for idx, item in enumerate(reversed(st.session_state.storico_previsioni), 1):
            str_num = " - ".join(map(str, item['numeri']))
            esito_str = item['esito']
            
            if esito_str is None:
                badge = "⏳ In attesa della prossima estrazione..."
            elif esito_str >= 3:
                badge = f"🔥 **{esito_str} PUNTI** (Vincita Importante!)"
            elif esito_str == 2:
                badge = f"🟢 **{esito_str} PUNTI** (Recupero / Ambo)"
            else:
                badge = f"🔴 **{esito_str} Punti** (Non vincente)"
                
            st.markdown(f"**Colpo {len(st.session_state.storico_previsioni) - idx + 1}:** `{str_num}` | {badge}")

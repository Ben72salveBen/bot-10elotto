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
    page_title="Bot 10eLotto - Hot3 MicroLottoNet",
    page_icon="🔥",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else "."
NOME_FILE = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")
NOME_STORICO = os.path.join(CARTELLA_DOCUMENTI, "storico_previsioni.json")

def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def carica_archivio():
    if os.path.exists(NOME_FILE):
        try:
            with open(NOME_FILE, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                archivio_pulito = []
                for ext in archivio:
                    if isinstance(ext, list) and len(ext) >= 10:
                        nums = sorted([int(n) for n in ext if str(n).isdigit() and 1 <= int(n) <= 90])
                        if len(nums) >= 10:
                            archivio_pulito.append(nums)
                return archivio_pulito
        except Exception as e:
            st.error(f"Errore nella lettura dell'archivio salvato: {e}")
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore nel salvataggio dell'archivio: {e}")
        return False

def carica_storico():
    if os.path.exists(NOME_STORICO):
        try:
            with open(NOME_STORICO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def salva_storico(storico):
    try:
        with open(NOME_STORICO, "w", encoding="utf-8") as f:
            json.dump(storico, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

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
        st.error(f"Errore di connessione durante lo scaricamento: {e}")
        return []

# ==========================================
# ARCHITETTURA NEURALE PYTORCH (HOT 3)
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
# MOTORE DI CALCOLO CON FORZATURA CADENZA CALDA
# ==========================================
def calcola_previsione_hot3(archivio_completo, quantita):
    if len(archivio_completo) < 3:
        return [], 0.0, 0
    
    # FOCUS ASSOLUTO SULLE ULTIME 3
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
    if len(tutte_comb) > 80:
        tutte_comb = tutte_comb[:80]

    if not tutte_comb:
        fallback = [n for n, f in freq_3.most_common(quantita)]
        return sorted(fallback), 0.0, cadenza_calda

    ultima_est = set(ultime_3[-1])
    penultima_est = set(ultime_3[-2])
    
    features_list = []
    comb_valide = []
    
    # FORZATURA CADENZA: Filtriamo o diamo priorità assoluta alle combinazioni con la cadenza calda
    for comb in tutte_comb:
        cset = set(comb)
        bonus_cadenza = sum(1 for n in comb if n % 10 == cadenza_calda)
        
        # Selezioniamo combinazioni che contengono almeno un numero della cadenza calda
        if bonus_cadenza >= 1:
            pres_ultima = len(cset.intersection(ultima_est))
            pres_penultima = len(cset.intersection(penultima_est))
            score_freq = sum(freq_3[n] for n in comb)
            
            features_list.append([
                float(pres_ultima),
                float(pres_penultima),
                float(score_freq),
                float(bonus_cadenza * 2.0)
            ])
            comb_valide.append(comb)

    # Fallback se il filtro restrittivo non trova abbastanza combinazioni
    if not comb_valide:
        comb_valide = tutte_comb
        for comb in tutte_comb:
            cset = set(comb)
            features_list.append([
                float(len(cset.intersection(ultima_est))),
                float(len(cset.intersection(penultima_est))),
                float(sum(freq_3[n] for n in comb)),
                0.0
            ])

    x_tensor = torch.tensor(features_list, dtype=torch.float32)
    model = MicroLottoNetHot3(input_dim=4)
    optimizer = optim.Adam(model.parameters(), lr=0.03, weight_decay=1e-3)
    criterion = nn.MSELoss()

    model.train()
    targets = torch.tensor([float(len(set(c).intersection(ultima_est))) for c in comb_valide], dtype=torch.float32)
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
        
    quartina_scelta = sorted([int(n) for n in comb_valide[best_idx]])
    
    # Indice di Concentrazione (%)
    punti_totali_scia = sum(freq_3[n] for n in quartina_scelta)
    max_possibile = 3 * quantita
    concentrazione = min(100.0, round((punti_totali_scia / max_possibile) * 100, 1))
    
    return quartina_scelta, concentrazione, cadenza_calda

# ==========================================
# INTERFACCIA WEB (STREAMLIT)
# ==========================================
st.title("🔥 Bot 10eLotto - Hot3 MicroLottoNet")
st.caption("Focus rigoroso sulle ultime 3 estrazioni + Forzatura Cadenze + Concentrazione + Tracciatore Esiti")

archivio = carica_archivio()
storico = carica_storico()

st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio))
st.sidebar.markdown("---")

# Sincronizzazione Web
if st.sidebar.button("🔄 Sincronizza Archivio da Web"):
    with st.spinner("Scaricamento estrazioni..."):
        estrazioni_nuove = scarica_estrazioni_con_bypass()
        if estrazioni_nuove:
            set_esistenti = {tuple(ext) for ext in archivio}
            aggiunte = 0
            for ext in estrazioni_nuove:
                if tuple(ext) not in set_esistenti:
                    archivio.append(ext)
                    aggiunte += 1
            if aggiunte > 0:
                salva_archivio(archivio)
                
                # Controllo automatico esito ultima previsione in sospeso
                if storico and storico[-1]['esito'] is None:
                    ultima_prev = set(storico[-1]['numeri'])
                    ultima_estrazione_reale = set(archivio[-1])
                    punti = len(ultima_prev.intersection(ultima_estrazione_reale))
                    storico[-1]['esito'] = punti
                    salva_storico(storico)
                    st.toast(f"Verifica automatica completata: {punti} Punti presi!", icon="🎯")

                st.success(f"Archivio aggiornato! Aggiunte {aggiunte} nuove estrazioni.")
                safe_rerun()
            else:
                st.info("L'archivio è già aggiornato.")
        else:
            st.error("Impossibile scaricare dal web.")

# RESET / TRIMMING A 40 ESTRAZIONI
if st.sidebar.button("✂️ Resetta a 40 Estrazioni"):
    if len(archivio) > 40:
        archivio = archivio[-40:]
        salva_archivio(archivio)
        st.sidebar.success("Archivio ridotto alle ultime 40 estrazioni!")
        safe_rerun()
    else:
        st.sidebar.info("L'archivio ha già 40 o meno estrazioni.")

st.sidebar.markdown("---")
st.sidebar.subheader("💾 Gestione Backup Archivio")

if archivio:
    json_str = json.dumps(archivio, ensure_ascii=False, indent=4)
    st.sidebar.download_button(
        label="📥 Esporta Archivio (JSON)",
        data=json_str,
        file_name="archivio_lotto_backup.json",
        mime="application/json"
    )

caricato_file = st.sidebar.file_uploader("📤 Importa Backup (JSON)", type=["json"])
if caricato_file is not None:
    try:
        dati_caricati = json.load(caricato_file)
        if isinstance(dati_caricati, list) and len(dati_caricati) > 0:
            archivio = [sorted([int(n) for n in ext]) for ext in dati_caricati if len(ext) >= 10]
            salva_archivio(archivio)
            st.sidebar.success(f"Backup caricato con successo! ({len(archivio)} estrazioni)")
            safe_rerun()
        else:
            st.sidebar.error("Il file caricato non è valido.")
    except Exception as e:
        st.sidebar.error(f"Errore nell'importazione: {e}")

st.markdown("---")

# Sezione Previsione
st.subheader("🚀 Genera Previsione (Focus Ultime 3 Estrazioni)")
quantita_numeri = st.slider("Quanti numeri vuoi giocare?", min_value=2, max_value=6, value=4, step=1)

if st.button("🔥 Genera Previsione Hot3", type="primary"):
    if len(archivio) < 3:
        st.warning("Servono almeno 3 estrazioni in archivio! Sincronizza o importa i dati.")
    else:
        previsione, concentrazione, cadenza_calda = calcola_previsione_hot3(archivio, quantita_numeri)
        
        storico.append({
            'numeri': previsione,
            'concentrazione': concentrazione,
            'cadenza': cadenza_calda,
            'esito': None
        })
        salva_storico(storico)
        
        st.success("Previsione ottimizzata pronta:")
        st.markdown(f"## **` {', '.join([f'{n:02d}' for n in previsione])} `**")
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric(label="🔥 Indice di Concentrazione", value=f"{concentrazione}%")
        with c2:
            st.metric(label="🎯 Cadenza Calda", value=f"Finale {cadenza_calda}")
            
        if concentrazione >= 50.0:
            st.success("🟢 **Scia rovente:** Ottima convergenza sulle ultime 3 estrazioni.")
        else:
            st.warning("🟡 **Scia debole:** Numeri frammentati. Prudenza.")

# Sezione Storico e Verifiche
if storico:
    st.markdown("---")
    st.subheader("📜 Storico Previsioni e Verifiche")
    with st.expander("👁️ Visualizza Registro Esiti", expanded=True):
        for idx, item in enumerate(reversed(storico), 1):
            str_num = " - ".join([f"{n:02d}" for n in item['numeri']])
            esito = item['esito']
            
            if esito is None:
                badge = "⏳ In attesa della prossima sincronizzazione..."
            elif esito >= 3:
                badge = f"🔥 **{esito} PUNTI** (TERNO / OTTIMO!)"
            elif esito == 2:
                badge = f"🟢 **{esito} PUNTI** (AMBO / RECUPERO)"
            else:
                badge = f"🔴 **{esito} Punti** (Non vincente)"
                
            st.markdown(f"**Colpo {len(storico) - idx + 1}:** `{str_num}` | {badge}")

# Visualizzazione rapida delle 3 estrazioni attualmente usate dal bot
if len(archivio) >= 3:
    st.markdown("---")
    with st.expander("👁️ Controlla le 3 estrazioni attuali analizzate dal Bot"):
        for i, ext in enumerate(archivio[-3:], 1):
            st.write(f"**Estrazione -{3 - i + 1}:** {sorted(ext)}")

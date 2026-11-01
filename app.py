import os
import json
import re
import urllib.request
import ssl
import numpy as np
import streamlit as st

# ==========================================
# CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(
    page_title="10eLotto Neural Bot - 19 Estrazioni",
    page_icon="🤖",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE_ARCHIVIO = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto.json")
NOME_FILE_ULTIMA_GIOCATA = os.path.join(CARTELLA_DOCUMENTI, "ultima_giocata.json")

def carica_archivio():
    if os.path.exists(NOME_FILE_ARCHIVIO):
        try:
            with open(NOME_FILE_ARCHIVIO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salva_archivio(archivio):
    try:
        with open(NOME_FILE_ARCHIVIO, "w", encoding="utf-8") as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

# ==========================================
# RETE NEURALE MULTI-STRATO (270-64-90) + RMSPROP
# ==========================================
class NeuralNetworkRMSprop:
    def __init__(self, input_size=270, hidden_size=64, output_size=90):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        # Inizializzazione pesi
        self.W1 = np.random.randn(input_size, hidden_size) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden_size))
        self.W2 = np.random.randn(hidden_size, output_size) * np.sqrt(2.0 / hidden_size)
        self.b2 = np.zeros((1, output_size))
        
        # Accumulatori RMSprop
        self.v_W1 = np.zeros_like(self.W1)
        self.v_b1 = np.zeros_like(self.b1)
        self.v_W2 = np.zeros_like(self.W2)
        self.v_b2 = np.zeros_like(self.b2)

    def forward(self, X):
        z1 = np.dot(X, self.W1) + self.b1
        a1 = np.maximum(0, z1)  # ReLU
        z2 = np.dot(a1, self.W2) + self.b2
        
        exp_z = np.exp(z2 - np.max(z2, axis=1, keepdims=True))
        probs = exp_z / np.sum(exp_z, axis=1, keepdims=True)
        return z1, a1, probs

    def train_fast(self, X, Y, epochs=70, lr=0.001, beta=0.9, eps=1e-8):
        if X is None or len(X) == 0:
            return 0.0
        
        m = X.shape[0]
        
        for _ in range(epochs):
            z1, a1, probs = self.forward(X)
            
            dz2 = probs - Y
            dW2 = np.dot(a1.T, dz2) / m
            db2 = np.sum(dz2, axis=0, keepdims=True) / m
            
            da1 = np.dot(dz2, self.W2.T)
            dz1 = da1 * (z1 > 0)
            dW1 = np.dot(X.T, dz1) / m
            db1 = np.sum(dz1, axis=0, keepdims=True) / m
            
            self.v_W1 = beta * self.v_W1 + (1 - beta) * (dW1 ** 2)
            self.v_b1 = beta * self.v_b1 + (1 - beta) * (db1 ** 2)
            self.v_W2 = beta * self.v_W2 + (1 - beta) * (dW2 ** 2)
            self.v_b2 = beta * self.v_b2 + (1 - beta) * (db2 ** 2)
            
            self.W1 -= (lr / (np.sqrt(self.v_W1) + eps)) * dW1
            self.b1 -= (lr / (np.sqrt(self.v_b1) + eps)) * db1
            self.W2 -= (lr / (np.sqrt(self.v_W2) + eps)) * dW2
            self.b2 -= (lr / (np.sqrt(self.v_b2) + eps)) * db2
            
        loss = -np.mean(np.sum(Y * np.log(probs + 1e-8), axis=1))
        return loss

    def predict_top_k(self, last_3, k=4):
        if len(last_3) < 3:
            return []
            
        x_onehot = np.zeros(270)
        for idx, num in enumerate(last_3):
            if 1 <= num <= 90:
                x_onehot[idx * 90 + (num - 1)] = 1.0
            
        X = x_onehot.reshape(1, -1)
        _, _, probs = self.forward(X)
        
        top_k_indices = np.argsort(probs[0])[-k:]
        return sorted((top_k_indices + 1).tolist())

# ==========================================
# SCRAPING ESTREMA PRECISIONE
# ==========================================
def estrai_numeri_da_testo(testo, limite):
    pezzi = re.findall(r'\d+', testo)
    numeri_validi = []
    visti = set()
    for p in pezzi:
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
        if len(numeri_validi) == limite:
            break
    return numeri_validi

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
                
                match_num = re.search(r'Numeri[:\s]*([\s\S]*?)(?=Extra|Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                numeri_base = []
                if match_num:
                    numeri_base = estrai_numeri_da_testo(match_num.group(1), 20)
                
                if len(numeri_base) < 20:
                    numeri_base = estrai_numeri_da_testo(testo_blocco, 20)

                numeri_extra = []
                match_extra = re.search(r'Extra[:\s]*([\s\S]*?)(?=Doppio|Oro|$)', testo_blocco, re.IGNORECASE)
                if match_extra:
                    numeri_extra = estrai_numeri_da_testo(match_extra.group(1), 15)
                else:
                    pos_extra = testo_blocco.lower().find('extra')
                    if pos_extra != -1:
                        testo_dopo_extra = testo_blocco[pos_extra:]
                        numeri_extra = estrai_numeri_da_testo(testo_dopo_extra, 15)

                if len(numeri_base) == 20:
                    tutti_35 = sorted(list(set(numeri_base + numeri_extra)))
                    estrazioni_trovate.append({
                        'id': id_concorso,
                        'base': sorted(numeri_base),
                        'extra': sorted(numeri_extra),
                        'tutti': tutti_35
                    })

            if not estrazioni_trovate:
                return []

            estrazioni_trovate.sort(key=lambda x: x['id'])
            return estrazioni_trovate

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ==========================================
# INTERFACCIA STREAMLIT
# ==========================================
st.title("🤖 10eLotto Neural Bot (19 Estrazioni)")
st.write("Rete Neurale One-Hot RMSprop addestrata dinamicamente sulle ultime 19 estrazioni online.")

if 'nn' not in st.session_state:
    st.session_state.nn = NeuralNetworkRMSprop()

quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

if st.button("🔄 Sincronizza & Addestra (Ultime 19)", type="primary"):
    with st.spinner("Scaricamento estrazioni online in corso..."):
        estrazioni_web = scarica_estrazioni_con_bypass()
        if len(estrazioni_web) > 0:
            archivio = carica_archivio()
            set_esistenti = {ext['id'] for ext in archivio}
            for ext in estrazioni_web:
                if ext['id'] not in set_esistenti:
                    archivio.append(ext)
            
            archivio.sort(key=lambda x: x['id'])
            salva_archivio(archivio)
            st.success(f"Sincronizzazione completata! Totale in archivio: {len(archivio)}")
            
            # Preleviamo esattamente le ultime 19 estrazioni più recenti
            ultime_19 = archivio[-19:]
            
            if len(ultime_19) >= 3:
                sequenza_numeri = []
                for ext in ultime_19:
                    sequenza_numeri.extend(ext['base'])
                
                X_list, Y_list = [], []
                for i in range(len(sequenza_numeri) - 3):
                    seq = sequenza_numeri[i:i+3]
                    target = sequenza_numeri[i+3]
                    
                    x_onehot = np.zeros(270)
                    for idx, num in enumerate(seq):
                        if 1 <= num <= 90:
                            x_onehot[idx * 90 + (num - 1)] = 1.0
                    X_list.append(x_onehot)
                    
                    y_onehot = np.zeros(90)
                    if 1 <= target <= 90:
                        y_onehot[target - 1] = 1.0
                    Y_list.append(y_onehot)
                
                X = np.array(X_list)
                Y = np.array(Y_list)
                
                with st.spinner("Addestramento della rete neurale sulle ultime 19 estrazioni..."):
                    loss = st.session_state.nn.train_fast(X, Y, epochs=70, lr=0.001)
                
                st.success(f"✅ Rete addestrata con successo sulle ultime {len(ultime_19)} estrazioni! (Loss: {loss:.4f})")
            else:
                st.warning("Ci sono meno di 3 estrazioni totali per avviare il training.")
        else:
            st.error("Nessuna estrazione trovata online.")

st.markdown("---")
st.subheader("🎯 Genera Previsione Corrente")

archivio_corrente = carica_archivio()
if len(archivio_corrente) > 0:
    ultima = archivio_corrente[-1]
    st.write(f"Ultimo Concorso in archivio: **#{ultima['id']}**")
    st.write(f"Numeri Base: `{ultima['base']}`")
    
    if st.button("Genera Previsione Ora"):
        last_3 = ultima['base'][-3:]
        top_k = st.session_state.nn.predict_top_k(last_3, k=quantita)
        
        # Formattazione richiesta: stringa senza spazi dopo la virgola e virgola finale
        risultato_str = ",".join(map(str, top_k)) + ","
        
        st.markdown("### Previsione Neurale:")
        st.code(risultato_str, language="")
else:
    st.warning("L'archivio è vuoto. Clicca su 'Sincronizza & Addestra' per scaricare i dati.")

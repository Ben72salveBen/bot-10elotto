import os
import json
import re
import urllib.request
import ssl
import numpy as np
import streamlit as st

# ==========================================
# CONFIGURAZIONE PAGINA (Mobile-Friendly)
# ==========================================
st.set_page_config(
    page_title="10eLotto Neural Bot - 19 Estrazioni",
    page_icon="🤖",
    layout="centered"
)

# ==========================================
# RETE NEURALE MULTI-STRATO (270-64-90) + RMSPROP
# ==========================================
class NeuralNetworkRMSprop:
    def __init__(self, input_size=270, hidden_size=64, output_size=90):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        # Inizializzazione pesi (He / Xavier)
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
# SCRAPING ONLINE DA LOTTOLOGIA (CORRETTO E PROFONDO)
# ==========================================
def estrai_numeri_da_testo(testo, limite=20):
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

def scarica_estrazioni_lottologia():
    # URL multipli per forzare lo scaricamento completo dell'archivio esteso
    urls = [
        "https://lottologia.com/10elotto5minuti/archivio-estrazioni/?lang=it",
        "https://lottologia.com/10elotto5minuti/estrazioni"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://lottologia.com/'
    }
    
    estrazioni_mappa = {}
    
    for u in urls:
        try:
            req = urllib.request.Request(u, headers=headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
                html = response.read().decode('utf-8', 'ignore')
                
                # Scomponiamo la pagina in base ai concorsi identificati dal cancelletto o tag analoghi
                blocchi = re.split(r'#(\d+)', html)
                
                for i in range(1, len(blocchi), 2):
                    id_concorso = int(blocchi[i])
                    testo_blocco = blocchi[i+1]
                    
                    # Filtriamo ID di concorso reali ed evitiamo numeri anomali
                    if id_concorso < 100 or id_concorso > 9999999:
                        continue

                    match_num = re.search(r'Numeri[:\s]*([\s\S]*?)(?=Extra|Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                    numeri_base = []
                    if match_num:
                        numeri_base = estrai_numeri_da_testo(match_num.group(1), 20)
                    if len(numeri_base) < 20:
                        numeri_base = estrai_numeri_da_testo(testo_blocco, 20)

                    if len(numeri_base) == 20:
                        estrazioni_mappa[id_concorso] = {
                            'id': id_concorso,
                            'base': sorted(numeri_base)
                        }
        except Exception:
            continue

    if estrazioni_mappa:
        # Ordiniamo per ID concorso e prendiamo tutte quelle disponibili
        lista_ordinata = sorted(estrazioni_mappa.values(), key=lambda x: x['id'])
        return lista_ordinata
        
    return []

# ==========================================
# INTERFACCIA STREAMLIT MOBILE
# ==========================================
st.title("🤖 10eLotto Neural Bot")
st.write("Scraping profondo da Lottologia e addestramento sulle **ultime 19 estrazioni**.")

if 'nn' not in st.session_state:
    st.session_state.nn = NeuralNetworkRMSprop()
if 'estrazioni' not in st.session_state:
    st.session_state.estrazioni = []

target_count = st.sidebar.slider("Numeri da generare", min_value=2, max_value=10, value=4)

st.markdown("---")
if st.button("🔄 Scarica Online & Addestra (Ultime 19)", type="primary"):
    with st.spinner("Scaricamento estrazioni in corso da Lottologia..."):
        dati_web = scarica_estrazioni_lottologia()
        
        if len(dati_web) >= 19:
            # Prendiamo esattamente le ultime 19 estrazioni più recenti in fondo alla lista ordinata
            st.session_state.estrazioni = dati_web[-19:]
            
            sequenza_numeri = []
            for ext in st.session_state.estrazioni:
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
            
            with st.spinner("Addestramento della rete sulle ultime 19 estrazioni..."):
                loss = st.session_state.nn.train_fast(X, Y, epochs=70, lr=0.001)
            
            st.success(f"✅ Sincronizzate e addestrate le ultime 19 estrazioni! (Loss: {loss:.4f})")
            st.info(f"Ultimo Concorso in archivio: #{st.session_state.estrazioni[-1]['id']}")
        else:
            st.error(f"Trovate solo {len(dati_web)} estrazioni. Riprova tra qualche istante.")

st.markdown("---")
st.subheader("🎯 Calcola Previsione Corrente")

if st.session_state.estrazioni:
    ultima_ext = st.session_state.estrazioni[-1]['base']
    st.write(f"Ultimi numeri base (#{st.session_state.estrazioni[-1]['id']}): `{ultima_ext}`")
    
    last_3 = ultima_ext[-3:]
    
    if st.button("Genera Previsione Ora"):
        top_k = st.session_state.nn.predict_top_k(last_3, k=target_count)
        
        # Formattazione richiesta: senza spazi dopo la virgola e virgola finale
        risultato_str = ",".join(map(str, top_k)) + ","
        
        st.markdown("### Previsione Generata:")
        st.code(risultato_str, language="")
else:
    st.warning("Premi il pulsante in alto per scaricare le estrazioni online e avviare il bot.")

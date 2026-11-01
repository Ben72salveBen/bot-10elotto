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
    page_title="10eLotto Neural & Ciclometry Bot",
    page_icon="🧬",
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
    except Exception:
        pass

# ==========================================
# MODULO CICLOMETRIA (Distanze e Diametrali)
# ==========================================
def distanza_ciclometrica(a, b):
    diff = abs(a - b)
    return min(diff, 90 - diff)

def get_diametrale(n):
    diam = (n + 45) % 90
    return 90 if diam == 0 else diam

def analizza_ciclometria(ultimi_numeri):
    candidati_ciclometrici = set()
    
    for n in ultimi_numeri:
        diam = get_diametrale(n)
        candidati_ciclometrici.add(diam)
        
    for i in range(len(ultimi_numeri)):
        for j in range(i + 1, len(ultimi_numeri)):
            n1 = ultimi_numeri[i]
            n2 = ultimi_numeri[j]
            dist = distanza_ciclometrica(n1, n2)
            
            if dist in [15, 30, 45]:
                comp1 = (n1 + dist) % 90
                comp2 = (n2 - dist) % 90
                if comp1 == 0: comp1 = 90
                if comp2 == 0: comp2 = 90
                candidati_ciclometrici.add(comp1)
                candidati_ciclometrici.add(comp2)
                
    return sorted(list(candidati_ciclometrici))

# ==========================================
# RETE NEURALE MULTI-STRATO (270-64-90) + RMSPROP
# ==========================================
class NeuralNetworkRMSprop:
    def __init__(self, input_size=270, hidden_size=64, output_size=90):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        self.W1 = np.random.randn(input_size, hidden_size) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden_size))
        self.W2 = np.random.randn(hidden_size, output_size) * np.sqrt(2.0 / hidden_size)
        self.b2 = np.zeros((1, output_size))
        
        self.v_W1 = np.zeros_like(self.W1)
        self.v_b1 = np.zeros_like(self.b1)
        self.v_W2 = np.zeros_like(self.W2)
        self.v_b2 = np.zeros_like(self.b2)

    def forward(self, X):
        z1 = np.dot(X, self.W1) + self.b1
        a1 = np.maximum(0, z1)
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
# SCRAPING DATI LOTTOLOGIA
# ==========================================
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
        st.error(f"Errore di connessione durante lo scraping:

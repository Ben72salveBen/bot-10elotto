import streamlit as st
import numpy as np

# ==========================================
# CONFIGURAZIONE PAGINA (Ottimizzata per Mobile)
# ==========================================
st.set_page_config(
    page_title="10eLotto Neural Bot",
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

    def train_fast(self, X, Y, epochs=50, lr=0.001, beta=0.9, eps=1e-8):
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
# INTERFACCIA STREAMLIT (Mobile Friendly)
# ==========================================
st.title("🤖 10eLotto Neural Bot")
st.write("Propagazione One-Hot & RMSprop ottimizzata per smartphone.")

# Inizializzazione stato sessione per mantenere la rete attiva
if 'nn' not in st.session_state:
    st.session_state.nn = NeuralNetworkRMSprop()
if 'trained' not in st.session_state:
    st.session_state.trained = False

st.markdown("---")
st.subheader("1. Carica Storico / Botstorico (1-90)")
storico_text = st.text_area("Incolla i numeri separati da virgola o spazio:", height=120)

target_count = st.slider("Quanti numeri vuoi generare in previsione?", min_value=2, max_value=10, value=4)

if st.button("Carica e Addestra Ora", type="primary"):
    if not storico_text.strip():
        st.warning("Inserisci prima lo storico dei numeri.")
    else:
        try:
            numeri = [int(n.strip()) for n in storico_text.replace("\n", ",").split(",") if n.strip().isdigit()]
            numeri = [n for n in numeri if 1 <= n <= 90]
            
            if len(numeri) < 4:
                st.error("Inserisci almeno 4 numeri validi (1-90) nello storico.")
            else:
                X_list, Y_list = [], []
                for i in range(len(numeri) - 3):
                    seq = numeri[i:i+3]
                    target = numeri[i+3]
                    
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
                
                with st.spinner("Addestramento della rete neurale in corso..."):
                    loss = st.session_state.nn.train_fast(X, Y, epochs=60, lr=0.001)
                
                st.session_state.trained = True
                st.success(f"Addestramento completato! Loss: {loss:.4f}")
        except Exception as e:
            st.error(f"Errore nella lettura dello storico: {e}")

st.markdown("---")
st.subheader("2. Genera Previsione")
ultimi_input = st.text_input("Inserisci gli ultimi 3 numeri estratti (es. 12, 45, 89):")

if st.button("Genera Previsione Corrente"):
    if not st.session_state.trained:
        st.warning("Prima devi caricare lo storico e cliccare su 'Carica e Addestra Ora'!")
    else:
        try:
            ultimi = [int(n.strip()) for n in ultimi_input.replace(" ", ",").split(",") if n.strip().isdigit()]
            if len(ultimi) < 3:
                st.warning("Inserisci almeno 3 numeri per effettuare la previsione.")
            else:
                last_3 = ultimi[-3:]
                top_k = st.session_state.nn.predict_top_k(last_3, k=target_count)
                
                # Formattazione richiesta: stringa di numeri senza spazi dopo la virgola e virgola finale
                risultato_str = ",".join(map(str, top_k)) + ","
                
                st.markdown("### Risultato:")
                st.code(risultato_str, language="")
        except Exception as e:
            st.error(f"Errore durante la previsione: {e}")

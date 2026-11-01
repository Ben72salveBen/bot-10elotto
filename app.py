import os
import json
import re
import random
import urllib.request
import ssl
from datetime import datetime
import multiprocessing as mp
import streamlit as st

# ==========================================
# CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(
    page_title="Bot 10eLotto Genetico - Multi-Core",
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
# UTILITY GEOMETRICHE GRIGLIA 10x9 (1-90)
# ==========================================
def get_cadenza(numero):
    return numero % 10

def get_decina(numero):
    return (numero - 1) // 10

def get_vicini_griglia(numero, raggio=1):
    if not (1 <= numero <= 90):
        return []
    
    r = (numero - 1) // 10
    c = (numero - 1) % 10
    vicini = []
    
    for dr in range(-raggio, raggio + 1):
        for dc in range(-raggio, raggio + 1):
            nr = r + dr
            nc = c + dc
            if 0 <= nr <= 8 and 0 <= nc <= 9:
                num_vicino = nr * 10 + nc + 1
                if 1 <= num_vicino <= 90:
                    vicini.append(num_vicino)
                    
    return list(dict.fromkeys(vicini))

# ==========================================
# CLASSE CROMOSOMA (REGOLE DI TRANSIZIONE 10eLotto)
# ==========================================
class CromosomaRegola10eLotto:
    def __init__(self):
        self.usa_innesco_cadenza = random.choice([True, False])
        self.usa_innesco_decina = random.choice([True, False])
        self.usa_innesco_ritardo = random.choice([True, False])
        
        if not (self.usa_innesco_cadenza or self.usa_innesco_decina or self.usa_innesco_ritardo):
            self.usa_innesco_cadenza = True

        self.window_cad = random.randint(5, 15)
        self.min_freq_cad = random.randint(3, 7)
        
        self.window_decina = random.randint(5, 12)
        self.min_densita_decina = random.choice([20.0, 30.0, 40.0])
        
        self.max_ritardo_rientro = random.randint(2, 6)

        self.tipo_output = random.choice([
            "EXPAND_CADENZA",
            "EXPAND_VICINI_GRIGLIA",
            "HYBRID_CAD_VICINI"
        ])

    def check_innesco(self, history_draws):
        if len(history_draws) < 15:
            return False

        ultima_estrazione = history_draws[-1].get('base', [])
        if not ultima_estrazione:
            return False
        riferimento = ultima_estrazione[0]
        
        esiti = []

        if self.usa_innesco_cadenza:
            cad_rif = get_cadenza(riferimento)
            sub_finestra = history_draws[-self.window_cad:-1]
            freq = sum(1 for ext in sub_finestra for n in ext.get('base', []) if get_cadenza(n) == cad_rif)
            esiti.append(freq >= self.min_freq_cad)

        if self.usa_innesco_decina:
            dec_rif = get_decina(riferimento)
            sub_finestra = history_draws[-self.window_decina:-1]
            tot_numeri = sum(len(ext.get('base', [])) for ext in sub_finestra)
            presenze = sum(1 for ext in sub_finestra for n in ext.get('base', []) if get_decina(n) == dec_rif)
            pct = (presenze / tot_numeri) * 100.0 if tot_numeri > 0 else 0
            esiti.append(pct >= self.min_densita_decina)

        if self.usa_innesco_ritardo:
            sub_finestra = history_draws[-self.max_ritardo_rientro-1:-1]
            presente_recente = any(riferimento in ext.get('base', []) for ext in sub_finestra)
            esiti.append(presente_recente)

        return all(esiti) if esiti else False

    def genera_output(self, ultima_estrazione_obj, target_n):
        base = ultima_estrazione_obj.get('base', [])
        if not base:
            return list(range(1, target_n + 1))
            
        ultimo_num = base[0]
        numeri = []

        if self.tipo_output == "EXPAND_CADENZA":
            cad = get_cadenza(ultimo_num)
            numeri = [n for n in range(1, 91) if n % 10 == cad]

        elif self.tipo_output == "EXPAND_VICINI_GRIGLIA":
            numeri = get_vicini_griglia(ultimo_num, raggio=2)

        elif self.tipo_output == "HYBRID_CAD_VICINI":
            cad = get_cadenza(ultimo_num)
            cad_nums = [n for n in range(1, 91) if n % 10 == cad]
            vicini = get_vicini_griglia(ultimo_num, raggio=1)
            numeri = list(dict.fromkeys(cad_nums + vicini))

        raggio = 1
        while len(numeri) < target_n and raggio <= 5:
            extra = get_vicini_griglia(ultimo_num, raggio)
            for e in extra:
                if e not in numeri:
                    numeri.append(e)
            raggio += 1

        for n in range(1, 91):
            if len(numeri) >= target_n:
                break
            if n not in numeri:
                numeri.append(n)

        return sorted([int(x) for x in numeri[:target_n]])

    def mutazione(self):
        if random.random() < 0.2:
            self.usa_innesco_cadenza = not self.usa_innesco_cadenza
        if random.random() < 0.2:
            self.usa_innesco_decina = not self.usa_innesco_decina
        if random.random() < 0.2:
            self.usa_innesco_ritardo = not self.usa_innesco_ritardo
            
        if not (self.usa_innesco_cadenza or self.usa_innesco_decina or self.usa_innesco_ritardo):
            self.usa_innesco_cadenza = True

        self.window_cad = max(3, self.window_cad + random.choice([-1, 1]))
        self.min_freq_cad = max(1, self.min_freq_cad + random.choice([-1, 1]))
        
        if random.random() < 0.15:
            self.tipo_output = random.choice(["EXPAND_CADENZA", "EXPAND_VICINI_GRIGLIA", "HYBRID_CAD_VICINI"])

    def to_dict(self):
        return {
            "usa_innesco_cadenza": self.usa_innesco_cadenza,
            "usa_innesco_decina": self.usa_innesco_decina,
            "usa_innesco_ritardo": self.usa_innesco_ritardo,
            "window_cad": int(self.window_cad),
            "min_freq_cad": int(self.min_freq_cad),
            "window_decina": int(self.window_decina),
            "min_densita_decina": float(self.min_densita_decina),
            "max_ritardo_rientro": int(self.max_ritardo_rientro),
            "tipo_output": self.tipo_output
        }

    @staticmethod
    def from_dict(d):
        c = CromosomaRegola10eLotto()
        c.usa_innesco_cadenza = d["usa_innesco_cadenza"]
        c.usa_innesco_decina = d["usa_innesco_decina"]
        c.usa_innesco_ritardo = d["usa_innesco_ritardo"]
        c.window_cad = d["window_cad"]
        c.min_freq_cad = d["min_freq_cad"]
        c.window_decina = d["window_decina"]
        c.min_densita_decina = d["min_densita_decina"]
        c.max_ritardo_rientro = d["max_ritardo_rientro"]
        c.tipo_output = d["tipo_output"]
        return c

# ==========================================
# FITNESS & VALUTAZIONE PARALLELA
# ==========================================
def eval_cromosoma(cro, history_draws, target_n):
    totale_estrazioni = len(history_draws)
    inneschi_totali = 0
    vincite = 0
    punti_totali_realizzati = 0
    
    for i in range(15, totale_estrazioni - 1):
        sub_history = history_draws[:i+1]
        if cro.check_innesco(sub_history):
            inneschi_totali += 1
            ultima = sub_history[-1]
            previsione = set(cro.genera_output(ultima, target_n))
            
            estrazione_successiva = history_draws[i+1].get('base', [])
            intersezione = previsione.intersection(estrazione_successiva)
            punti = len(intersezione)
            punti_totali_realizzati += punti
            
            if punti >= 2:
                vincite += 1

    if inneschi_totali == 0:
        return 0.0, 0, 0.0

    win_rate = (vincite / inneschi_totali) * 100.0
    media_punti = punti_totali_realizzati / inneschi_totali

    fitness_finale = (win_rate * 10) + (media_punti * 50) + inneschi_totali
    return fitness_finale, inneschi_totali, win_rate

def _eval_wrapper(args):
    cro, history_draws, target_n = args
    return eval_cromosoma(cro, history_draws, target_n)

def addestra_modello_genetico(history_draws, pop_size, max_gen, target_n, progress_bar=None):
    num_cores = max(1, mp.cpu_count() - 1)
    popolazione = [CromosomaRegola10eLotto() for _ in range(pop_size)]
    miglior_fitness = -1.0
    miglior_regola = popolazione[0]

    with mp.Pool(processes=num_cores) as pool:
        for gen in range(1, max_gen + 1):
            tasks = [(c, history_draws, target_n) for c in popolazione]
            risultati = pool.map(_eval_wrapper, tasks)

            pop_valutata = []
            for i, cro in enumerate(popolazione):
                fit, inneschi, wr = risultati[i]
                if fit > miglior_fitness:
                    miglior_fitness = fit
                    miglior_regola = cro
                pop_valutata.append((fit, inneschi, wr, cro))
            
            pop_valutata.sort(key=lambda x: x[0], reverse=True)

            if progress_bar:
                progress_bar.progress(gen / max_gen, text=f"Generazione {gen}/{max_gen} - Miglior Fitness: {miglior_fitness:.1f}")

            nuova_pop = [pop_valutata[0][3]]
            while len(nuova_pop) < pop_size:
                cand1, cand2, cand3 = random.sample(popolazione, 3)
                f1 = risultati[popolazione.index(cand1)][0]
                f2 = risultati[popolazione.index(cand2)][0]
                f3 = risultati[popolazione.index(cand3)][0]
                
                vincitore = cand1 if f1 >= f2 and f1 >= f3 else (cand2 if f2 >= f3 else cand3)
                figlio = CromosomaRegola10eLotto.from_dict(vincitore.to_dict())
                figlio.mutazione()
                nuova_pop.append(figlio)

            popolazione = nuova_pop

    return miglior_regola

# ==========================================
# SCRAPING ESTESO DALL'ARCHIVIO UFFICIALE
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
    # Puntiamo direttamente all'archivio esteso di Lottologia per prelevare più concorsi
    url = "https://lottologia.com/10elotto5minuti/archivio-estrazioni/?lang=it"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://lottologia.com/'
    }
    
    estrazioni_trovate = []
    
    # Tentativo su pagina archivio estesa e fallback sulla pagina live se necessario
    urls_da_provare = [url, "https://lottologia.com/10elotto5minuti/estrazioni"]
    
    for target_url in urls_da_provare:
        try:
            req = urllib.request.Request(target_url, headers=headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
                html = response.read().decode('utf-8', 'ignore')
                
                blocchi = re.split(r'#(\d+)', html)
                for i in range(1, len(blocchi), 2):
                    id_concorso = int(blocchi[i])
                    testo_blocco = blocchi[i+1]
                    
                    tutti_pezzi_grezzi = re.findall(r'\d+', testo_blocco)
                    if len(tutti_pezzi_grezzi) < 25:
                        continue
                    
                    match_num = re.search(r'Numeri[:\s]*([\s\S]*?)(?=Extra|Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                    numeri_base = []
                    if match_num:
                        numeri_base = estrai_numeri_da_testo(match_num.group(1), 20)
                    if len(numeri_base) < 20:
                        numeri_base = estrai_numeri_da_testo(testo_blocco, 20)

                    match_extra = re.search(r'Extra[:\s]*([\s\S]*?)(?=Doppio|Oro|$)', testo_blocco, re.IGNORECASE)
                    numeri_extra = []
                    if match_extra:
                        numeri_extra = estrai_numeri_da_testo(match_extra.group(1), 15)

                    if len(numeri_base) == 20:
                        tutti_35 = sorted(list(set(numeri_base + numeri_extra)))
                        # Evitiamo duplicati se l'id è già presente
                        if not any(e['id'] == id_concorso for e in estrazioni_trovate):
                            estrazioni_trovate.append({
                                'id': id_concorso,
                                'base': sorted(numeri_base),
                                'extra': sorted(numeri_extra),
                                'tutti': tutti_35
                            })
        except Exception:
            continue
            
        if len(estrazioni_trovate) >= 30:
            break

    if estrazioni_trovate:
        estrazioni_trovate.sort(key=lambda x: x['id'])
        return estrazioni_trovate
        
    return []

# ==========================================
# INTERFACCIA STREAMLIT
# ==========================================
st.title("🧬 Bot 10eLotto Genetico - Multi-Core")
st.write("Sistema evolutivo integrato con l'archivio esteso e unificato.")

menu = st.sidebar.selectbox("Menu", ["Previsione & Verifica", "Addestra Nuovo Modello", "Gestione Archivio"])

archivio = carica_archivio()

if menu == "Addestra Nuovo Modello":
    st.subheader("🏋️ Addestramento Modello Genetico")
    pop_size = st.slider("Dimensione Popolazione", 50, 300, 100)
    max_gen = st.slider("Generazioni", 20, 200, 50)
    target_n = st.slider("Numeri da prevedere (Target)", 2, 10, 4)
    
    if st.button("Avvia Sincronizzazione Web & Addestramento", type="primary"):
        with st.spinner("Scaricamento archivio esteso in corso..."):
            estrazioni_web = scarica_estrazioni_con_bypass()
            if len(estrazioni_web) > 10:
                # Uniamo o aggiorniamo l'archivio esistente preservando lo storico
                esistenti = {e['id']: e for e in archivio}
                for ext in estrazioni_web:
                    esistenti[ext['id']] = ext
                archivio = list(esistenti.values())
                archivio.sort(key=lambda x: x['id'])
                salva_archivio(archivio)
                st.success(f"Sincronizzazione completata! Totale concorsi in archivio: {len(archivio)}")
            else:
                st.warning("Impossibile scaricare dal web. Uso l'archivio locale disponibile.")
                
        if len(archivio) > 25:
            prog_bar = st.empty()
            modello_ottimizzato = addestra_modello_genetico(archivio, pop_size, max_gen, target_n, prog_bar)
            
            nome_modello = f"modello_10elotto_N{target_n}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            salvataggio = {
                "target_n": target_n,
                "regola": modello_ottimizzato.to_dict()
            }
            with open(nome_modello, "w") as f:
                json.dump(salvataggio, f, indent=4)
            st.success(f"Modello addestrato e salvato in '{nome_modello}'!")
        else:
            st.error(f"Servono almeno 30 estrazioni in archivio per l'addestramento (attualmente ce ne sono {len(archivio)}).")

elif menu == "Previsione & Verifica":
    st.subheader("🎯 Previsione Dinamica 10eLotto")
    
    file_modelli = [f for f in os.listdir(".") if f.startswith("modello_10elotto") and f.endswith(".json")]
    
    if not file_modelli:
        st.warning("Nessun modello addestrato trovato. Vai su 'Addestra Nuovo Modello' per crearne uno.")
    else:
        modello_scelto = st.selectbox("Seleziona Modello", file_modelli)
        if modello_scelto:
            with open(modello_scelto, "r") as f:
                data_mod = json.load(f)
                target_n = data_mod["target_n"]
                regola = CromosomaRegola10eLotto.from_dict(data_mod["regola"])
            
            st.info(f"Modello caricato correttamente. Genera previsioni per {target_n} numeri.")
            
            if len(archivio) > 0:
                ultima = archivio[-1]
                st.write(f"Ultima estrazione in archivio (Concorso #{ultima.get('id', 'N/D')}) - Base: `{ultima.get('base', [])}`")
                
                if st.button("Genera Previsione Corrente", type="primary"):
                    innescato = regola.check_innesco(archivio)
                    if innescato:
                        prev = regola.genera_output(ultima, target_n)
                        st.success(f"🔥 INNESCO ATTIVO! Gioca questi {target_n} numeri:")
                        st.markdown(f"### `{' - '.join(f'{x:02d}' for x in prev)}`")
                        with open(NOME_FILE_ULTIMA_GIOCATA, "w") as f:
                            json.dump(prev, f)
                    else:
                        st.warning("⏳ Nessun innesco attivo in questa estrazione. Attendi la successiva.")
            else:
                st.warning("Archivio vuoto. Sincronizza dalla sezione Archivio.")

elif menu == "Gestione Archivio":
    st.subheader("📁 Gestione Storico Estrazioni")
    if st.button("Sincronizza Estrazioni da Lottologia"):
        with st.spinner("Scaricamento archivio esteso..."):
            estraz = scarica_estrazioni_con_bypass()
            if estraz:
                esistenti = {e['id']: e for e in archivio}
                for ext in estraz:
                    esistenti[ext['id']] = ext
                archivio = list(esistenti.values())
                archivio.sort(key=lambda x: x['id'])
                salva_archivio(archivio)
                st.success(f"Archivio aggiornato! Concorsi totali salvati: {len(archivio)}")
            else:
                st.error("Errore durante lo scaricamento.")
                
    if archivio:
        st.write(f"Concorsi totali in archivio: {len(archivio)}")
        for ext in reversed(archivio[-5:]):
            st.text(f"Concorso #{ext.get('id')} - Base: {ext.get('base', [])}")

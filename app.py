import os
import json
import re
import urllib.request
import ssl
from collections import defaultdict
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Compensazione Incrociata",
    page_icon="⚡",
    layout="centered"
)

CARTELLA_DOCUMENTI = os.path.join(os.path.expanduser("~"), "Documents")
if not os.path.exists(CARTELLA_DOCUMENTI):
    CARTELLA_DOCUMENTI = os.path.expanduser("~")

NOME_FILE = os.path.join(CARTELLA_DOCUMENTI, "archivio_lotto_extra.json")

def carica_archivio():
    if os.path.exists(NOME_FILE):
        try:
            with open(NOME_FILE, "r", encoding="utf-8") as f:
                archivio = json.load(f)
                archivio_normalizzato = []
                for item in archivio:
                    if isinstance(item, list):
                        archivio_normalizzato.append({
                            'numeri': sorted([int(n) for n in item]),
                            'extra': []
                        })
                    elif isinstance(item, dict):
                        archivio_normalizzato.append({
                            'numeri': sorted([int(n) for n in item.get('numeri', [])]),
                            'extra': sorted([int(n) for n in item.get('extra', [])])
                        })
                return [ext for ext in archivio_normalizzato if len(ext['numeri']) >= 20]
        except Exception as e:
            st.error(f"Errore nella lettura dell'archivio: {e}")
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
                
                match_num = re.search(r'Numeri\s*([\s\S]*?)(?=Extra|Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                match_extra = re.search(r'Extra\s*([\s\S]*?)(?=Oro|Doppio|$)', testo_blocco, re.IGNORECASE)
                
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
                    
                    extra_validi = []
                    if match_extra:
                        testo_ext = match_extra.group(1)
                        pezzi_ext = re.findall(r'\d+', testo_ext)
                        visti_ext = set()
                        for p in pezzi_ext:
                            val = int(p)
                            if 1 <= val <= 90 and val not in visti_ext:
                                visti_ext.add(val)
                                extra_validi.append(val)
                            if len(extra_validi) == 15:
                                break

                    if len(numeri_validi) == 20:
                        numeri_validi.sort()
                        extra_validi.sort()
                        estrazioni_trovate.append({
                            'id': id_concorso,
                            'numeri': numeri_validi,
                            'extra': extra_validi
                        })

            if not estrazioni_trovate:
                return []

            estrazioni_trovate.sort(key=lambda x: x['id'])
            return estrazioni_trovate

    except Exception as e:
        st.error(f"Errore di connessione durante lo scraping: {e}")
        return []

# ====================================================================
# STRATEGIA COMPENSAZIONE INCROCIATA (BASE vs EXTRA)
# ====================================================================
def elabora_previsione(quantita_numeri):
    archivio_completo = carica_archivio()
    lookback = 15  # Finestra di analisi di 15 estrazioni per valutare i ritardi di compensazione
    
    if len(archivio_completo) < lookback:
        st.warning(f"Servono almeno {lookback} estrazioni in archivio!")
        return

    st.info("⚡ Calcolo Compensazione Incrociata Base/Extra in corso...")

    ultime = archivio_completo[-lookback:]

    # Calcolo ritardo specifico per la Base e per l'Extra
    ritardo_base = {n: lookback for n in range(1, 91)}
    ritardo_extra = {n: lookback for n in range(1, 91)}

    for idx, ext in enumerate(reversed(ultime)):
        distanza = idx  # 0 = ultimissima estrazione
        
        for n in ext['numeri']:
            if ritardo_base[int(n)] == lookback:
                ritardo_base[int(n)] = distanza
                
        for n in ext.get('extra', []):
            if ritardo_extra[int(n)] == lookback:
                ritardo_extra[int(n)] = distanza

    punteggio = {}
    for num in range(1, 91):
        rb = ritardo_base[num]
        re_val = ritardo_extra[num]
        
        # 1. Punteggio Compensazione: un numero che manca da un lato ma è uscito di recente dall'altro
        differenziale = abs(rb - re_val)
        
        # 2. Punteggio Maturità: numeri che mancano da 3 a 8 colpi da entrambi i lati (pronti al rientro)
        maturita = 0
        if 3 <= rb <= 8 and 3 <= re_val <= 8:
            maturita = 15.0
            
        punteggio[num] = (differenziale * 2.0) + maturita

    # Ordinamento decrescente dei punteggi
    classifica = sorted(
        range(1, 91),
        key=lambda i: (-punteggio[i], i)
    )

    migliori = classifica[:quantita_numeri]
    migliori.sort()

    st.session_state['ultima_previsione'] = migliori

    st.markdown(f"### ⚡ PREVISIONE COMPENSAZIONE INCROCIATA ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"## **` {numeri_str} `**")
    
    st.caption("Numeri selezionati incrociando i ritardi e le presenze sbilanciate tra Base ed Extra per il ciclo di 4 colpi.")
    st.balloons()

# Tabelle Premi Ufficiali
tabelle_base = {
    2: {2: 14}, 3: {3: 45, 2: 2}, 4: {4: 90, 3: 10, 2: 1},
    5: {5: 140, 4: 15, 3: 4, 2: 1}, 6: {6: 1000, 5: 100, 4: 10, 3: 2},
    10: {10: 1000000, 9: 20000, 8: 1000, 7: 150, 6: 15, 5: 2, 0: 2}
}

tabelle_extra = {
    2: {2: 25}, 3: {3: 100, 2: 5}, 4: {4: 200, 3: 20, 2: 2},
    5: {5: 300, 4: 30, 3: 8, 2: 2}, 6: {6: 2000, 5: 200, 4: 20, 3: 4},
    10: {10: 2000000, 9: 40000, 8: 2000, 7: 300, 6: 30, 5: 4, 0: 4}
}

# Interfaccia
st.title("⚡ Bot 10eLotto - Compensazione Base/Extra")
st.write("Analisi incrociata per intercettare i rientri imminenti sbilanciati tra Base ed Extra.")

archivio_corrente = carica_archivio()
st.sidebar.metric(label="Estrazioni in Archivio", value=len(archivio_corrente))

quantita = st.sidebar.slider("Quanti numeri vuoi selezionare?", min_value=2, max_value=10, value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("Menu Operazioni")

opzione = st.sidebar.radio(
    "Scegli un'azione:",
    ("Genera Previsione", "Scarica Web & Prendi Previsione", "Verifica Ultima Previsione", "Visualizza Archivio", "Svuota Archivio")
)

if opzione == "Scarica Web & Prendi Previsione":
    if st.button("Avvia Sincronizzazione Web", type="primary"):
        with st.spinner("Connessione in corso..."):
            estrazioni_scaricate = scarica_estrazioni_con_bypass()
            if len(estrazioni_scaricate) > 0:
                archivio = carica_archivio()
                set_esistenti = {tuple(ext['numeri']) for ext in archivio}
                nuove_aggiunte = 0
                for ext in estrazioni_scaricate:
                    chiave = tuple(ext['numeri'])
                    if chiave not in set_esistenti:
                        archivio.append(ext)
                        set_esistenti.add(chiave)
                        nuove_aggiunte += 1
                
                if salva_archivio(archivio):
                    st.success(f"Sincronizzazione completata! Aggiunte {nuove_aggiunte} estrazioni.")
                    elabora_previsione(quantita)
                else:
                    st.error("Errore salvataggio file.")
            else:
                st.error("Nessuna estrazione trovata.")

elif opzione == "Genera Previsione":
    if st.button("Genera Previsione da Archivio", type="primary"):
        with st.spinner("Calcolo Compensazione in corso..."):
            elabora_previsione(quantita)

elif opzione == "Verifica Ultima Previsione":
    st.subheader("🔍 Verifica Esiti Ultima Previsione")
    if 'ultima_previsione' not in st.session_state or not st.session_state['ultima_previsione']:
        st.warning("Nessuna previsione memorizzata.")
    else:
        archivio = carica_archivio()
        if not archivio:
            st.error("Archivio vuoto.")
        else:
            ultima_estrazione = archivio[-1]
            numeri_base = ultima_estrazione['numeri']
            numeri_extra = ultima_estrazione['extra']
            pred = st.session_state['ultima_previsione']
            
            st.write(f"**Tua previsione in verifica:** { ' - '.join(map(str, pred)) }")
            st.write(f"**Ultima estrazione BASE:** { ' - '.join(map(str, numeri_base)) }")
            if numeri_extra:
                st.write(f"🌟 **Ultima estrazione EXTRA:** { ' - '.join(map(str, numeri_extra)) }")
            
            gioca_extra = st.checkbox("Modalità EXTRA attiva (+1€)", value=True)
            
            set_base = set(numeri_base)
            presi_base = [n for n in pred if n in set_base]
            num_presi_base = len(presi_base)
            premio_base = tabelle_base.get(len(pred), {}).get(num_presi_base, 0)
            
            set_extra = set(numeri_extra) if numeri_extra else set()
            presi_extra = [n for n in pred if n in set_extra]
            num_presi_extra = len(presi_extra)
            premio_extra = tabelle_extra.get(len(pred), {}).get(num_presi_extra, 0) if gioca_extra else 0
            
            costo_totale = 2 if gioca_extra else 1
            premio_totale = premio_base + (premio_extra if gioca_extra else 0)
            netto = premio_totale - costo_totale
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="Presi in BASE", value=f"{num_presi_base} su {len(pred)}")
                if presi_base:
                    st.success(f"Base: { ' - '.join(map(str, presi_base)) } ({premio_base}€)")
            with col2:
                if gioca_extra:
                    st.metric(label="Presi in EXTRA", value=f"{num_presi_extra} su {len(pred)}")
                    if presi_extra:
                        st.success(f"Extra: { ' - '.join(map(str, presi_extra)) } ({premio_extra}€)")
            
            st.markdown("---")
            st.markdown(f"### Bilancio Netto Colpo: **{'+' if netto > 0 else ''}{netto} €**")
            
            if premio_totale > 0:
                st.balloons()

elif opzione == "Visualizza Archivio":
    st.subheader("📁 Storico Estrazioni Salvate")
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.info("Archivio vuoto.")
    else:
        for idx, ext in enumerate(reversed(archivio)):
            nums = ', '.join(map(str, ext['numeri']))
            exts = ', '.join(map(str, ext['extra'])) if ext['extra'] else "N/D"
            st.text(f"#{len(archivio)-idx} | Base: [{nums}] | Extra: [{exts}]")

elif opzione == "Svuota Archivio":
    if st.button("Conferma Cancellazione Archivio", type="secondary"):
        salva_archivio([])
        st.success("Archivio pulito.")

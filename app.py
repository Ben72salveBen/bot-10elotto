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

# Configurazione della pagina per dispositivi mobili
st.set_page_config(
    page_title="Bot 10eLotto - Doppia Strategia (Gruppi)",
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
                    if len(numeri_validi) == 20:
                        numeri_validi.sort()
                        estrazioni_trovate.append({'id': id_concorso, 'numeri': numeri_validi})
            if not estrazioni_trovate: return []
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
        z_score = (f_rec - media_attesa) / dev_std if dev_std > 0 else 0
        f_globale = freq_globale[n]
        media_globale_attesa = tot_estrazioni * p
        trend_storico = (f_globale - media_globale_attesa) / (math.sqrt(tot_estrazioni * p * (1 - p)) + 1e-5)
        punteggi[n] = (z_score * 0.7) + (trend_storico * 0.3)

    numeri_ordinati = sorted(punteggi.

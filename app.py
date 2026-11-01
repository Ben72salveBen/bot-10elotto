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
    page_title="10eLotto Ciclometry Bot",
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
                archivio_strutturato = []
                for ext in archivio:
                    if isinstance(ext, dict) and 'numeri' in ext:
                        nums = [int(n) for n in ext['numeri'] if 1 <= int(n) <= 90]
                        if len(nums) == 20:
                            archivio_strutturato.append({
                                'id': ext.get('id', 'N/D'),
                                'data': ext.get('data', ''),
                                'ora': ext.get('ora', ''),
                                'numeri': sorted(nums)
                            })
                    elif isinstance(ext, list):
                        nums = [int(n) for n in ext if 1 <= int(n) <= 90]
                        if len(nums) == 20:
                            archivio_strutturato.append({
                                'id': 'N/D',
                                'data': '',
                                'ora': '',
                                'numeri': sorted(nums)
                            })
                return archivio_strutturato
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

def salva_giocata(numeri_scelti):
    try:
        with open(NOME_FILE_ULTIMA_GIOCATA, "w", encoding="utf-8") as f:
            json.dump(numeri_scelti, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

def carica_giocata():
    if os.path.exists(NOME_FILE_ULTIMA_GIOCATA):
        try:
            with open(NOME_FILE_ULTIMA_GIOCATA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

# ==========================================
# MODULO CICLOMETRIA ARMONICA
# ==========================================
def distanza_ciclometrica(a, b):
    diff = abs(a - b)
    return min(diff, 90 - diff)

def get_diametrale(n):
    diam = (n + 45) % 90
    return 90 if diam == 0 else diam

def analizza_ciclometria(ultimi_numeri, quantita_richiesta):
    candidati = []
    
    for n in ultimi_numeri:
        diam = get_diametrale(int(n))
        if diam not in candidati:
            candidati.append(diam)
        
    for i in range(len(ultimi_numeri)):
        for j in range(i + 1, len(ultimi_numeri)):
            n1 = int(ultimi_numeri[i])
            n2 = int(ultimi_numeri[j])
            dist = distanza_ciclometrica(n1, n2)
            
            if dist in [15, 30, 45]:
                comp1 = (n1 + dist) % 90
                comp2 = (n2 - dist) % 90
                if comp1 == 0: comp1 = 90
                if comp2 == 0: comp2 = 90
                
                if comp1 not in candidati: candidati.append(comp1)
                if comp2 not in candidati: candidati.append(comp2)
                
    for n in ultimi_numeri:
        val = int(n)
        if val not in candidati:
            candidati.append(val)
            
    for n in range(1, 91):
        if n not in candidati:
            candidati.append(n)
            
    candidati.sort()
    return candidati[:quantita_richiesta]

# ==========================================
# SCRAPING STRUTTURATO
# ==========================================
def scarica_estrazioni_con_bypass():
    urls = [
        "https://www.10elotto5minuti.it/estrazioni-10-e-lotto-ogni-5-minuti-di-oggi/",
        "https://www.10elotto5minuti.it/10elotto-5-minuti.php"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    html = ""
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                html = response.read().decode('utf-8', 'ignore')
                if len(html) > 500:
                    break
        except Exception:
            continue

    if not html:
        return []

    try:
        estrazioni_trovate = []
        righe_testo = html.split('\n')
        
        for riga in righe_testo:
            match_info = re.search(r'(\d+)\s+(\d{2}/\d{2})\s+(\d{2}:\d{2})', riga)
            token_numerici = re.findall(r'\b([1-9]|[1-8][0-9]|90)\b', riga)
            if len(token_numerici) >= 20:
                interi = [int(t) for t in token_numerici]
                finestra = []
                visti = set()
                for n in interi:
                    if 1 <= n <= 90 and n not in visti:
                        visti.add(n)
                        finestra.append(n)
                    if len(finestra) == 20:
                        break
                
                if len(finestra) == 20:
                    id_conc = match_info.group(1) if match_info else "N/D"
                    data_conc = match_info.group(2) if match_info else ""
                    ora_conc = match_info.group(3) if match_info else ""
                    
                    estrazione_obj = {
                        'id': id_conc,
                        'data': data_conc,
                        'ora': ora_conc,
                        'numeri': finestra
                    }
                    
                    if estrazione_obj not in estrazioni_trovate:
                        estrazioni_trovate.append(estrazione_obj)

        return estrazioni_trovate[-15:] if len(estrazioni_trovate) >= 15 else estrazioni_trovate

    except Exception:
        return []

# ==========================================
# VERIFICA ESITO ULTIMA GIOCATA
# ==========================================
def verifica_esito_ultima_giocata(ultima_estrazione):
    ultima_giocata = carica_giocata()
    if not ultima_giocata:
        return

    st.markdown("### 📊 VERIFICA ESITO GIOCATA PRECEDENTE:")
    set_estratto = set(ultima_estrazione)
    set_giocati = set(ultima_giocata)
    
    presi = set_giocati.intersection(set_estratto)
    punti = len(presi)
    
    st.write(f"• Numeri giocati: {sorted(list(set_

import os
import json
import re
import urllib.request
import ssl
import streamlit as st

# Configurazione della pagina
st.set_page_config(
    page_title="Bot 10eLotto - Intersezione Voti Pura",
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
            if "Seleziona Numeri" in html:
                html = html.split("Seleziona Numeri")[-1]
            
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

                match_extra = re.search(r'Extra[:\s]*([\s\S]*?)(?=Doppio|Oro|$)', testo_blocco, re.IGNORECASE)
                numeri_extra = []
                if match_extra:
                    numeri_extra = estrai_numeri_da_testo(match_extra.group(1), 15)

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
        st.error(f"Errore di connessione: {e}")
        return []

def verifica_esito_ultima_giocata(ultima_estrazione_obj):
    ultima_giocata = carica_giocata()
    if not ultima_giocata:
        return

    st.markdown("### 📊 VERIFICA ESITO GIOCATA PRECEDENTE:")
    set_giocati = set(ultima_giocata)
    set_base = set(ultima_estrazione_obj.get('base', []))
    presi_base = set_giocati.intersection(set_base)
    punti_base = len(presi_base)
    
    set_extra = set(ultima_estrazione_obj.get('extra', []))
    presi_extra = set_giocati.intersection(set_extra)
    punti_extra = len(presi_extra)
    
    st.write(f"• **Numeri giocati:** `{sorted(list(set_giocati))}`")
    st.markdown(f"• **Base ({punti_base} punti):** {sorted(list(presi_base)) if punti_base > 0 else 'Nessuno'}")
    st.markdown(f"• **Extra ({punti_extra} punti):** {sorted(list(presi_extra)) if punti_extra > 0 else 'Nessuno'}")
    st.markdown("---")

def elabora_previsione(quantita_desiderata):
    archivio = carica_archivio()
    if len(archivio) == 0:
        st.warning("Nessuna estrazione in archivio!")
        return

    ultima_estrazione = archivio[-1]
    numeri_base = set(ultima_estrazione.get('base', []))
    
    righe_vuote = []
    colonne_vuote = []

    # 1. Individuazione Righe Vuote (9 righe da 10 numeri)
    for r in range(9):
        inizio = r * 10 + 1
        fine = (r + 1) * 10
        numeri_riga = set(range(inizio, fine + 1))
        if len(numeri_base.intersection(numeri_riga)) == 0:
            righe_vuote.append(r)

    # 2. Individuazione Colonne Vuote (10 colonne)
    for c in range(10):
        if c == 9:
            col_nums = [10 + i * 10 for i in range(9)]
        else:
            col_nums = [c + 1 + i * 10 for i in range(9) if (c + 1 + i * 10) <= 90]
        numeri_colonna = set(col_nums)
        if len(numeri_base.intersection(numeri_colonna)) == 0:
            colonne_vuote.append(c)

    st.write(f"• **Righe vuote trovate (indici 0-8):** {righe_vuote}")
    st.write(f"• **Colonne vuote trovate (indici 0-9):** {colonne_vuote}")

    # 3. Estrazione PURA del numero dall'intersezione (Riga x Colonna)
    intersezioni_pure = []
    for r in righe_vuote:
        for c in colonne_vuote:
            if c == 9:
                num = (r + 1) * 10
            else:
                num = r * 10 + (c + 1)
            if 1 <= num <= 90:
                intersezioni_pure.append(num)

    fulcri = set(intersezioni_pure)

    if fulcri:
        st.success(f"🎯 **Numero/i esatto/i dall'intersezione (Riga x Colonna vuote):** {sorted(list(fulcri))}")
    else:
        st.warning("⚠️ Nessuna intersezione pulita riga/colonna vuota in questa estrazione. Prendo i numeri delle righe vuote.")
        for r in righe_vuote:
            for i in range(1, 11):
                n = r * 10 + i
                if n <= 90: fulcri.add(n)
        if not fulcri:
            fulcri = {15, 30, 45, 60} # Fallburn di sicurezza

    # 4. Ricostruzione dei vicini (Croce: fulcro + sopra, sotto, sinistra, destra)
    vicini_finali = set()
    for f in fulcri:
        vicini_finali.add(f)
        r_f = (f - 1) // 10
        c_f = (f - 1) % 10
        
        if c_f > 0: vicini_finali.add(

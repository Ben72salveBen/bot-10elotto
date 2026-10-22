def elabora_previsione(quantita_numeri):
    archivio_completo = carica_archivio()
    lookback = 9  # Prendiamo 9 estrazioni totali
    
    if len(archivio_completo) < lookback:
        st.warning(f"Servono almeno {lookback} estrazioni in archivio!")
        return

    st.info(f"🔥 Analisi Micro-Trend (ESCLUSA l'ultimissima estrazione) in corso...")

    # ESCLUDIAMO l'ultima estrazione ([-1]) e prendiamo le 8 precedenti
    ultime_otto_senza_ultima = [ext['numeri'] for ext in archivio_completo[-lookback:-1]]

    punteggio_fiammata = defaultdict(float)
    frequenza_recentissima = defaultdict(int)
    distanza_concorso = {}

    # Scansione dell'intervallo con offset
    for idx, ext in enumerate(ultime_otto_senza_ultima):
        # idx 7 = estrazione di 1 colpo fa, idx 6 = 2 colpi fa, ecc.
        distanza = (len(ultime_otto_senza_ultima) - 1) - idx  
        
        for n in ext:
            num = int(n)
            frequenza_recentissima[num] += 1
            distanza_concorso[num] = distanza

            # Assegniamo i pesi partendo da 1 colpo fa (non da zero)
            if distanza == 0:     # 1 colpo fa
                punteggio_fiammata[num] += 2.5
            elif distanza == 1:   # 2 colpi fa
                punteggio_fiammata[num] += 2.0
            elif distanza == 2:   # 3 colpi fa
                punteggio_fiammata[num] += 1.5
            else:
                punteggio_fiammata[num] += 0.5

    # Bonus fiammata per presenze multiple nell'intervallo
    for num in range(1, 91):
        if frequenza_recentissima[num] >= 2:
            punteggio_fiammata[num] += (frequenza_recentissima[num] * 2.0)
            
        if num not in distanza_concorso:
            distanza_concorso[num] = 99

    classifica = sorted(
        range(1, 91),
        key=lambda i: (
            -punteggio_fiammata[i],
            -frequenza_recentissima[i],
            distanza_concorso[i],
            i
        )
    )

    migliori = classifica[:quantita_numeri]
    migliori.sort()

    st.session_state['ultima_previsione'] = migliori

    st.markdown(f"### 🔥 PREVISIONE OFFSET ({quantita_numeri} NUMERI):")
    numeri_str = " - ".join(map(str, migliori))
    st.markdown(f"## **` {numeri_str} `**")
    st.caption("Previsione elaborata ignorando l'ultima estrazione e analizzando il rientro dei trend recenti.")
    st.balloons()

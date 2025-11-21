# ai_analyzer_gui.py
# Interfaccia grafica Streamlit per:
# - caricare una traccia audio
# - vedere la forma d'onda
# - ascoltare l'audio
# - selezionare un intervallo (start/end) da analizzare
# - chiamare il backend multi-agente (analyze_track) SOLO sul pezzo selezionato

import streamlit as st          # importa streamlit per creare l'interfaccia web
import tempfile                 # importa tempfile per creare file temporanei
import os                       # importa os per lavorare con i percorsi dei file
import io                       # importa io per gestire i byte in memoria
import librosa                  # importa librosa per analizzare l'audio
import librosa.display          # importa librosa.display per visualizzare la waveform
import matplotlib.pyplot as plt # importa matplotlib per disegnare i grafici
import soundfile as sf          # importa soundfile per salvare file audio (wav)
import plotly.graph_objs as go  # importa plotly per waveform interattiva

from ai_analyzer_backend import analyze_track  # importa la funzione di analisi dal backend


# ==========================
# FUNZIONI DI SUPPORTO
# ==========================

def salva_bytes_temporanei(audio_bytes: bytes, suffix: str) -> str:
    """
    Salva dei byte audio grezzi (già letti dall'upload) in un file temporaneo su disco.

    Parametri:
    - audio_bytes: contenuto binario del file audio
    - suffix: estensione da usare (es. ".wav", ".mp3")

    Ritorna:
    - path_file: percorso assoluto del file temporaneo creato
    """
    # Crea un file temporaneo con delete=False così non viene cancellato subito
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    # Scrive i byte audio nel file
    temp.write(audio_bytes)
    # Forza la scrittura su disco
    temp.flush()
    # Chiude il file (il path resta valido)
    temp.close()
    # Ritorna il percorso del file temporaneo
    return temp.name


def salva_segmento_wav(y_segment, sr: int) -> str:
    """
    Salva un segmento audio (array numpy y_segment) in un file WAV temporaneo.

    Parametri:
    - y_segment: array numpy con il pezzo di audio selezionato
    - sr: sample rate del segnale

    Ritorna:
    - path_wav: percorso del file wav temporaneo
    """
    # Crea un file temporaneo con estensione .wav
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_path = temp.name
    temp.close()  # chiudiamo subito, poi soundfile scrive

    # Usa soundfile.sf.write per scrivere i campioni su disco in formato wav
    sf.write(temp_path, y_segment, sr)

    # Ritorna il path del wav creato
    return temp_path


# ==========================
# INTERFACCIA STREAMLIT
# ==========================

# Titolo in alto
st.title("🎧 AI Music Analyzer – Multi-Agent (Ollama)")

# Descrizione breve
st.write(
    "Carica una traccia audio, visualizza la forma d'onda, seleziona il pezzo che ti interessa "
    "e lascia che l'AI analizzi solo quell'intervallo. "
    "Riceverai feedback di mix, accordi, idee melodiche e un piano d'azione finale."
)

# Sezione upload traccia utente
st.subheader("1. Carica la tua traccia")

# Uploader per la traccia utente
user_file = st.file_uploader(
    "Traccia utente (obbligatoria)",
    type=["wav", "mp3", "aiff", "flac"],
    key="user_file"
)

# Contenitori per waveform e selezione
y = None          # array audio della traccia
sr = None         # sample rate
duration = None   # durata in secondi

audio_bytes = None  # conterrà i byte originali del file caricato

# Quando l'utente carica un file, lo elaboriamo
if user_file is not None:
    # Legge tutti i byte del file una sola volta
    audio_bytes = user_file.read()

    # Mostra un player per ascoltare la traccia
    st.audio(audio_bytes, format="audio/" + user_file.type.split("/")[-1])

    # Carica l'audio con librosa a partire dai byte in memoria
    # Crea un buffer BytesIO per far credere a librosa che sia un file
    buffer = io.BytesIO(audio_bytes)

    # Carica il segnale audio in mono a 44.1 kHz
    y, sr = librosa.load(buffer, sr=44100, mono=True)

    # Calcola la durata del file in secondi
    duration = librosa.get_duration(y=y, sr=sr)

    # Mostra info di base
    st.write(f"Durata traccia: **{duration:.1f} s** – Sample rate: **{sr} Hz**")

    # Disegna la forma d'onda completa
    st.subheader("2. Forma d'onda e selezione intervallo")

        # ==========================
    # WAVEFORM COMPLETA INTERATTIVA (PLOTLY)
    # ==========================

    # Crea un array di tempi (in secondi) per ogni campione
    times = librosa.times_like(y, sr=sr)

    # Per non avere troppi punti (audio lungo), facciamo un leggero downsampling
    max_points = 5000  # massimo numero di punti da mostrare
    step = max(1, len(y) // max_points)  # calcola ogni quanti campioni prendere un punto

    # Applichiamo il downsampling sia al segnale che ai tempi
    y_ds = y[::step]         # prende un campione ogni 'step'
    times_ds = times[::step] # stessi campioni per l'asse del tempo

    # Crea una figura Plotly
    fig = go.Figure()

    # Aggiunge la traccia della waveform come linea
    fig.add_trace(
        go.Scatter(
            x=times_ds,         # asse x = tempo in secondi
            y=y_ds,             # asse y = ampiezza
            mode="lines",       # disegna una linea continua
            name="Waveform"     # nome della traccia (leggenda)
        )
    )

    # Personalizza layout del grafico
    fig.update_layout(
        title="Waveform completa (zoomabile)",  # titolo
        xaxis_title="Tempo (s)",                # label asse x
        yaxis_title="Ampiezza",                 # label asse y
        showlegend=False,                       # nasconde legenda (non fondamentale qui)
        margin=dict(l=40, r=20, t=40, b=40)     # margini del grafico
    )

    # Mostra il grafico interattivo in Streamlit (zoom, pan, ecc.)
    st.plotly_chart(fig, use_container_width=True)

    # Slider per selezionare l'intervallo da analizzare
    st.write("Seleziona l'intervallo da analizzare (in secondi):")

    # Slider doppio: start e end
    start_sec, end_sec = st.slider(
        "Intervallo (start - end)",
        min_value=0.0,
        max_value=float(max(duration, 0.1)),  # garantisce che max > 0
        value=(0.0, float(min(duration, 30.0))),  # default: primi 30 secondi o tutta se più corta
        step=0.1
    )

    # Mostra i valori selezionati
    st.write(f"Intervallo selezionato: **{start_sec:.1f} s** → **{end_sec:.1f} s**")

    # Controllo che start < end
    if start_sec >= end_sec:
        st.error("L'intervallo selezionato non è valido (start deve essere < end).")
        y_segment = None
    else:
        # Calcola gli indici dei campioni corrispondenti all'intervallo selezionato
        start_sample = int(start_sec * sr)
        end_sample = int(end_sec * sr)

        # Taglia il segmento di audio
        y_segment = y[start_sample:end_sample]

        # Info sul segmento
        seg_duration = (end_sample - start_sample) / sr
        st.write(f"Durata segmento selezionato: **{seg_duration:.1f} s**")

        # Waveform del segmento (facoltativa, ma utile)
                # ==========================
        # WAVEFORM SEGMENTO INTERATTIVA (PLOTLY)
        # ==========================

        # Crea un array tempo relativo solo per il segmento (parte da 0)
        times_seg = librosa.times_like(y_segment, sr=sr)

        # Downsampling anche per il segmento (stesso criterio)
        max_points_seg = 3000                     # limite punti per il segmento
        step_seg = max(1, len(y_segment) // max_points_seg)

        y_seg_ds = y_segment[::step_seg]          # downsample sul segnale
        times_seg_ds = times_seg[::step_seg]      # downsample sui tempi

        # Crea figura Plotly per il segmento
        fig_seg = go.Figure()

        fig_seg.add_trace(
            go.Scatter(
                x=times_seg_ds,          # tempo relativo (0 → durata segmento)
                y=y_seg_ds,              # ampiezza
                mode="lines",
                name="Segmento"
            )
        )

        fig_seg.update_layout(
            title="Waveform segmento selezionato (zoomabile)",
            xaxis_title="Tempo segmento (s)",
            yaxis_title="Ampiezza",
            showlegend=False,
            margin=dict(l=40, r=20, t=40, b=40)
        )

        # Mostra waveform interattiva del segmento
        st.plotly_chart(fig_seg, use_container_width=True)

else:
    # Se non è stato caricato nulla, metti un messaggio
    st.info("Carica una traccia per vedere la forma d'onda e selezionare un intervallo.")


# Sezione per reference (opzionale)
st.subheader("3. (Opzionale) Carica una traccia di reference")

ref_file = st.file_uploader(
    "Traccia di reference (opzionale)",
    type=["wav", "mp3", "aiff", "flac"],
    key="ref_file"
)

# ==========================
# PULSANTE DI ANALISI
# ==========================

st.subheader("4. Avvia l'analisi AI sulla selezione")

# Pulsante per avviare l'analisi
if st.button("Analizza intervallo selezionato"):
    # Controlliamo che ci sia la traccia utente
    if user_file is None or audio_bytes is None or y is None or sr is None:
        st.error("Per favore carica prima una traccia utente.")
    else:
        # Controlliamo che l'intervallo sia valido e che y_segment esista
        try:
            y_segment  # verifica se esiste nel contesto
        except NameError:
            st.error("Selezione non valida. Controlla lo slider e riprova.")
            y_segment = None

        if y_segment is None or len(y_segment) == 0:
            st.error("Il segmento selezionato è vuoto. Controlla lo slider.")
        else:
            # Mostriamo uno spinner durante l'analisi
            with st.spinner("Analisi in corso... (audio + multi-agente su Ollama)"):
                # Salviamo il segmento selezionato in un WAV temporaneo
                segment_path = salva_segmento_wav(y_segment, sr)

                # Gestiamo la reference, se presente
                if ref_file is not None:
                    # Leggiamo i byte della reference
                    ref_bytes = ref_file.read()
                    # Determiniamo l'estensione dalla reference
                    ref_suffix = os.path.splitext(ref_file.name)[1]
                    # Salviamo i byte in un file temporaneo
                    ref_path = salva_bytes_temporanei(ref_bytes, suffix=ref_suffix)
                else:
                    ref_path = None

                # Chiamiamo la funzione di analisi del backend con:
                # - il path del segmento selezionato
                # - il path dell'eventuale reference
                results = analyze_track(
                    user_path=segment_path,
                    reference_path=ref_path
                )

            # Fine analisi
            st.success("Analisi completata!")

            # ==========================
            # MOSTRA RISULTATI
            # ==========================

            # Genere stimato
            st.markdown("### 🎵 Genere stimato")
            st.write(results.get("genre", "N/D"))

            # Contesto tecnico (opzionale)
            with st.expander("📊 Dettagli tecnici (contesto comune)"):
                st.code(results.get("context", ""), language="markdown")

            # Piano finale orchestrator
            st.markdown("### 🧠 Piano d'azione finale (Orchestrator)")
            st.markdown(results.get("final_plan", ""))

            # Dettagli agenti
            st.markdown("### 🔍 Dettaglio agenti")

            with st.expander("🎛 Mix Engineer"):
                st.markdown(results.get("mix_agent", ""))

            with st.expander("🎼 Music Theory / Accordi"):
                st.markdown(results.get("theory_agent", ""))

            with st.expander("🎹 Creative Producer (melodia / bassline)"):
                st.markdown(results.get("creative_agent", ""))
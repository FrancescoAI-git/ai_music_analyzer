# backend_server.py

# Importa FastAPI per creare API HTTP
from fastapi import FastAPI, UploadFile, File, Form
# Importa CORS per permettere richieste dal frontend (porta differente)
from fastapi.middleware.cors import CORSMiddleware

# Importa la funzione principale di analisi dal tuo backend esistente
from ai_analyzer_backend import analyze_track

# Moduli per file temporanei e gestione file
import tempfile
import shutil
import os

# Importa librerie audio per tagliare il file
import librosa            # per caricare l'audio in memoria
import soundfile as sf    # per salvare il segmento tagliato

# Crea l'app FastAPI
app = FastAPI()

# Configura CORS per accettare richieste da http://localhost:3000 (Node UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend Node
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def analyze_endpoint(
    # File audio caricato dal frontend (campo "file" del FormData)
    file: UploadFile = File(...),
    # Inizio selezione in secondi (stringa → float tramite Form)
    trim_start: float = Form(0.0),
    # Fine selezione in secondi (se -1 o 0 → usa fine traccia)
    trim_end: float = Form(-1.0),
):
    """
    Endpoint che:
    - riceve un file audio e l'intervallo di taglio (trim_start, trim_end)
    - salva il file in una cartella temporanea
    - se richiesto, taglia il segmento [trim_start, trim_end]
    - chiama analyze_track sul file (segmento o intero)
    - restituisce un JSON con i risultati principali
    """

    # Crea una directory temporanea che verrà cancellata automaticamente alla fine
    with tempfile.TemporaryDirectory() as tmpdir:
        # Costruisce il percorso del file temporaneo
        original_path = os.path.join(tmpdir, file.filename)

        # Scrive il contenuto del file uploadato su disco
        with open(original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Scegliamo il path che passeremo ad analyze_track
        segment_path = original_path

        # Se trim_end > 0 e trim_end > trim_start, procediamo con il taglio reale
        if trim_end > 0.0 and trim_end > trim_start:
            # Carica l'audio completo con librosa (mantiene sample rate originale)
            y, sr = librosa.load(original_path, sr=None, mono=True)

            # Calcola i campioni di inizio e fine in base ai secondi
            start_sample = int(trim_start * sr)
            end_sample = int(trim_end * sr)

            # Clamp sugli estremi per evitare crash
            start_sample = max(0, min(start_sample, len(y)))
            end_sample = max(0, min(end_sample, len(y)))

            # Se il segmento è valido (almeno qualche campione)
            if end_sample > start_sample:
                # Slice del segnale nell'intervallo [start_sample:end_sample]
                y_segment = y[start_sample:end_sample]

                # Nuovo path per il segmento
                segment_path = os.path.join(tmpdir, "segment.wav")

                # Salva il segmento come wav (mono, sr originale)
                sf.write(segment_path, y_segment, sr)
            # Altrimenti lascia segment_path = original_path

        # A questo punto segment_path punta:
        # - al file tagliato se trim_start/trim_end validi
        # - al file originale altrimenti

        # Chiama la funzione di analisi sul path selezionato
        results = analyze_track(
            user_path=segment_path,
            reference_path=None
        )

    # Ritorna un sottoinsieme dei risultati per il frontend
    return {
        "genre": results.get("genre"),
        "final_plan": results.get("final_plan"),
        "mix_agent": results.get("mix_agent"),
        "theory_agent": results.get("theory_agent"),
        "creative_agent": results.get("creative_agent"),
    }
    
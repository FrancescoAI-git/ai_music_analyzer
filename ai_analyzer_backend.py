# ============================================================
# AI MUSIC ANALYZER - MULTI-AGENTE CON RAG (NO GRAFICI)
# ============================================================
# Questo script:
# - Carica una traccia utente (e opzionale reference)
# - Analizza il contenuto audio (RMS, spettro, BPM, tonalità)
# - Stima automaticamente il genere in base a BPM + energia
# - Confronta con una reference, se presente
# - Usa RAG su una knowledge base (Chroma + Ollama embeddings)
# - Lancia una pipeline multi-agente con Ollama:
#     1) Mix Engineer (con RAG)
#     2) Music Theory (con RAG)
#     3) Creative Producer (con RAG + blocco MIDI)
#     4) Orchestrator (unisce tutto)
# - Ritorna un dizionario con tutti i testi e il piano finale.
# ============================================================

# Import librerie per audio e numerica
import io                  # Per eventuale uso futuro con file in memoria
import librosa             # Per analisi audio
import numpy as np         # Per calcoli numerici

# Import per LLM locale
import ollama              # Per chiamare il modello tramite Ollama

# Import per controllo esistenza file
import os                  # Per verificare se esiste la reference

# Import per RAG (vector store)
import chromadb            # Per usare Chroma come database vettoriale

import pyloudnorm as pyln  # per calcolare i LUFS e la loudness range
# ============================================================
# CONFIGURAZIONE DI BASE
# ============================================================

# Sample rate standard per l'analisi audio
DEFAULT_SR = 44100

# Parametri per STFT / RMS
DEFAULT_FRAME_LENGTH = 2048
DEFAULT_HOP_LENGTH = 512


# Modello Ollama: configurazione semplificata
# Usiamo sempre 'mistral' sia per chat che per embedding
# Assicurati di avere il modello: ollama pull mistral
OLLAMA_CHAT_MODEL = "mistral"      # modello per le chiamate di chat
OLLAMA_EMBED_MODEL = "mistral"     # modello per gli embedding RAG

# Limite massimo di token generati per ogni risposta del modello
# Valore più basso = risposta più veloce (ma più corta)
MAX_LLM_TOKENS = 512

# Config RAG / Chroma
CHROMA_DB_PATH = "chroma_db"      # Cartella dove è salvato il DB Chroma
KB_COLLECTION_NAME = "music_kb"   # Nome collezione knowledge base


# ============================================================
# 1. FUNZIONI DI CARICAMENTO AUDIO
# ============================================================

def load_audio(path, sr=DEFAULT_SR):
    """
    Carica un file audio da disco e lo converte in mono.
    Parametri:
        path: percorso del file audio (stringa)
        sr: sample rate desiderato per l'analisi
    Ritorna:
        y: array numpy con il segnale audio mono
        sr: sample rate effettivo
    """
    # Carica l'audio usando librosa (mono=True fonda i canali in uno)
    y, sr = librosa.load(path, sr=sr, mono=True)
    # Ritorna segnale e sample rate
    return y, sr


# ============================================================
# 2. FEATURE AUDIO (RMS, SPETTRO, BPM, KEY)
# ============================================================

def compute_features(y, sr,
                     frame_length=DEFAULT_FRAME_LENGTH,
                     hop_length=DEFAULT_HOP_LENGTH):
    """
    Calcola varie feature audio:
        - RMS nel tempo
        - spettrogramma (magnitudo)
        - spettro medio
        - frequenze (bin FFT)
        - durata del brano
        - BPM stimato
        - tonalità stimata (nota fondamentale) tramite chroma
    Parametri:
        y: array numpy del segnale audio
        sr: sample rate del segnale
    Ritorna:
        dizionario con tutte le feature
    """
    # Calcola RMS (energia media per frame)
    rms = librosa.feature.rms(y=y,
                              frame_length=frame_length,
                              hop_length=hop_length)[0]

    # Calcola i tempi (in secondi) associati a ciascun frame RMS
    times_rms = librosa.frames_to_time(np.arange(len(rms)),
                                       sr=sr,
                                       hop_length=hop_length)

    # Calcola STFT (trasformata di Fourier a breve termine)
    stft = librosa.stft(y,
                        n_fft=frame_length,
                        hop_length=hop_length)

    # Magnitudo dello spettrogramma (valori assoluti della STFT)
    spectrogram = np.abs(stft)

    # Spettro medio: media della magnitudo lungo l'asse del tempo (colonne)
    mean_spectrum = np.mean(spectrogram, axis=1)

    # Frequenze corrispondenti ai bin di FFT
    freqs = librosa.fft_frequencies(sr=sr, n_fft=frame_length)

    # Durata totale del brano in secondi
    duration = librosa.get_duration(y=y, sr=sr)

    # Stima del BPM con beat tracking
    tempo_array = librosa.beat.tempo(y=y, sr=sr)
    # Se l'array non è vuoto, prendi il primo valore
    bpm = float(tempo_array[0]) if len(tempo_array) > 0 else None

    # Calcolo del chroma (energia per ciascuna nota della scala cromatica)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    # Media nel tempo della matrice chroma (12 note)
    chroma_mean = chroma.mean(axis=1)

    # Indice della nota con energia media più alta
    idx_root = int(np.argmax(chroma_mean))

    # Mappa degli indici alle note
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F',
                  'F#', 'G', 'G#', 'A', 'A#', 'B']

    # Nota fondamentale stimata (senza distinzione maggiore/minore)
    key_root = note_names[idx_root]

    # Ritorna tutte le feature in un dizionario
    return {
        "rms": rms,
        "times_rms": times_rms,
        "spectrogram": spectrogram,
        "mean_spectrum": mean_spectrum,
        "freqs": freqs,
        "duration": duration,
        "bpm": bpm,
        "key_root": key_root
    }

def compute_advanced_analysis(y, sr):
    """
    Analisi audio avanzata:
    - LUFS integrato (pyloudnorm)
    - "Loudness range" approssimata (percentili sul segnale)
    - Crest factor (peak vs RMS)
    - Distribuzione energia per bande fini
    - Densità dei transienti

    Ritorna un dizionario usato poi in build_common_context.
    """

    # Assicuriamoci che il segnale sia float32
    y = y.astype(np.float32)

    # ============================
    # 1) LOUDNESS (LUFS) + RANGE APPROX
    # ============================
    meter = pyln.Meter(sr)  # misuratore EBU BS.1770
    integrated_loudness = meter.integrated_loudness(y)  # LUFS integrato

    # RMS e picco per crest factor
    rms_val = np.sqrt(np.mean(y**2))
    peak_val = np.max(np.abs(y))
    crest_factor = 20 * np.log10((peak_val + 1e-9) / (rms_val + 1e-9))

    # "Loudness range" approssimata:
    # usiamo percentili sul valore assoluto del segnale
    abs_y = np.abs(y)
    if len(abs_y) > 0:
        p95 = np.percentile(abs_y, 95)
        p5 = np.percentile(abs_y, 5)
        loudness_range = 20 * np.log10((p95 + 1e-9) / (p5 + 1e-9))
    else:
        loudness_range = 0.0

    # ============================
    # 2) SPETTRO PER BANDE
    # ============================
    stft = librosa.stft(y, n_fft=4096, hop_length=1024)
    mag = np.abs(stft)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

    def band_energy(freq_low, freq_high):
        """Energia media nella banda [freq_low, freq_high]."""
        mask = (freqs >= freq_low) & (freqs < freq_high)
        if not np.any(mask):
            return 0.0
        return float(np.mean(mag[mask, :]**2))

    raw_band_energies = {
        "sub_20_40": band_energy(20, 40),
        "bass_40_80": band_energy(40, 80),
        "bass_80_150": band_energy(80, 150),
        "lowmid_150_500": band_energy(150, 500),
        "mid_500_2000": band_energy(500, 2000),
        "highmid_2k_6k": band_energy(2000, 6000),
        "air_6k_20k": band_energy(6000, 20000),
    }

    total_bands_energy = sum(raw_band_energies.values()) + 1e-9
    band_percent = {
        k: (v / total_bands_energy) * 100.0
        for k, v in raw_band_energies.items()
    }

    # ============================
    # 3) DENSITÀ TRANSIENTI
    # ============================
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onsets_times = librosa.frames_to_time(onsets_frames, sr=sr)

    num_transients = len(onsets_times)
    duration_sec = librosa.get_duration(y=y, sr=sr)
    transient_density = num_transients / (duration_sec + 1e-9)

    # ============================
    # 4) PACK RISULTATI
    # ============================
    return {
        "loudness": {
            "integrated_lufs": float(integrated_loudness),
            "loudness_range": float(loudness_range),   # NOTA: approssimata
            "crest_factor_db": float(crest_factor),
        },
        "bands_energy_percent": band_percent,
        "transients": {
            "count": int(num_transients),
            "density_per_sec": float(transient_density),
        },
        "duration_sec": float(duration_sec),
    }
   

# ============================================================
# 3. RIASSUNTO NUMERICO (PER LLM)
# ============================================================

def band_energy(mean_spectrum, freqs, low, high):
    """
    Calcola l'energia (somma delle magnitudini) in una banda di frequenza.
    Parametri:
        mean_spectrum: spettro medio (array)
        freqs: array delle frequenze
        low: frequenza minima della banda
        high: frequenza massima della banda
    Ritorna:
        energia totale nella banda selezionata
    """
    # Crea una maschera booleana per selezionare le frequenze nella banda
    mask = (freqs >= low) & (freqs <= high)
    # Somma le magnitudini dello spettro medio solo nella banda
    return float(np.sum(mean_spectrum[mask]))


def summarize_track_features(features):
    """
    Crea un riassunto numerico leggibile per un LLM:
        - durata
        - RMS medio e massimo
        - BPM
        - nota fondamentale stimata
        - distribuzione energia in 5 bande:
            * sub (20-60)
            * bass (60-150)
            * lowmid (150-500)
            * highmid (500-4000)
            * high (4000-20000)
    Parametri:
        features: dizionario restituito da compute_features()
    Ritorna:
        summary: dizionario compatto con i dati principali
    """
    # Estrae componenti dal dizionario delle feature
    rms = features["rms"]
    freqs = features["freqs"]
    mean_spectrum = features["mean_spectrum"]

    # Calcola energia per ciascuna banda
    energy_sub = band_energy(mean_spectrum, freqs, 20, 60)
    energy_bass = band_energy(mean_spectrum, freqs, 60, 150)
    energy_lowmid = band_energy(mean_spectrum, freqs, 150, 500)
    energy_highmid = band_energy(mean_spectrum, freqs, 500, 4000)
    energy_high = band_energy(mean_spectrum, freqs, 4000, 20000)

    # Somma totale per normalizzare a percentuali
    total_energy = energy_sub + energy_bass + energy_lowmid + energy_highmid + energy_high
    if total_energy == 0:
        total_energy = 1.0  # Evita divisione per zero

    # Costruisce il riassunto
    summary = {
        "duration_sec": features["duration"],
        "rms_mean": float(np.mean(rms)),
        "rms_max": float(np.max(rms)),
        "bpm": features["bpm"],
        "key_root": features["key_root"],
        "energy_percent": {
            "sub": energy_sub / total_energy * 100.0,
            "bass": energy_bass / total_energy * 100.0,
            "lowmid": energy_lowmid / total_energy * 100.0,
            "highmid": energy_highmid / total_energy * 100.0,
            "high": energy_high / total_energy * 100.0,
        }
    }

    return summary


def compare_summaries(user_summary, ref_summary):
    """
    Confronta la traccia utente con la reference in termini di:
        - differenza RMS medio
        - differenze percentuali di energia per banda
    Parametri:
        user_summary: riassunto della traccia utente
        ref_summary: riassunto della reference
    Ritorna:
        dizionario con differenze RMS e di energia
    """
    # Differenza di RMS medio
    diff_rms = user_summary["rms_mean"] - ref_summary["rms_mean"]

    # Differenze di energia per ciascuna banda
    diff_energy = {}
    for band in user_summary["energy_percent"]:
        diff_energy[band] = (
            user_summary["energy_percent"][band] -
            ref_summary["energy_percent"][band]
        )

    # Ritorna il confronto
    return {
        "diff_rms_mean": diff_rms,
        "diff_energy_percent": diff_energy
    }


# ============================================================
# 4. STIMA GENERE IN BASE ALLE FEATURE
# ============================================================

def estimate_genre_from_summary(summary):
    """
    Stima il genere in base a:
        - BPM
        - distribuzione dell'energia per bande
    È un metodo euristico, utile per demo / progetti didattici.
    Parametri:
        summary: dizionario da summarize_track_features
    Ritorna:
        genre_label: stringa con il genere stimato
        reason: spiegazione testuale della stima
    """
    # Estrae BPM e distribuzione energia
    bpm = summary.get("bpm", 0) or 0
    energies = summary.get("energy_percent", {})

    sub = energies.get("sub", 0)
    bass = energies.get("bass", 0)
    lowmid = energies.get("lowmid", 0)
    highmid = energies.get("highmid", 0)
    high = energies.get("high", 0)

    # Valori di default
    genre_label = "Genere elettronico"
    reason = "Dati poco chiari, genere non classificato con certezza."

    # Hardstyle / Hard dance: BPM molto alto
    if bpm >= 145:
        genre_label = "Hardstyle / Hard Dance"
        reason = f"BPM molto alto (~{bpm:.1f}), tipico di hardstyle/hard dance."

    # Trance / Psytrance
    elif 135 <= bpm < 145:
        genre_label = "Trance / Psytrance"
        reason = f"BPM elevato (~{bpm:.1f}), tipico della trance / psy."

    # Big Room / EDM festival
    elif 128 <= bpm < 135:
        genre_label = "Big Room / EDM Festival"
        reason = f"BPM medio-alti (~{bpm:.1f}), tipici di EDM da festival."

    # Zona House / Progressive / Melodic Techno
    elif 122 <= bpm < 128:
        # Molta energia in sub+bass e pochi alti → più dark → melodic techno
        if (sub + bass) > 40 and high < 15:
            genre_label = "Melodic Techno"
            reason = (
                f"BPM ~{bpm:.1f} con molta energia in sub/bass "
                "e poca negli alti → sound scuro, tipo melodic techno."
            )
        # Molta energia in highmid/high → più bright → progressive house
        elif highmid > 20 and high > 15:
            genre_label = "Progressive House"
            reason = (
                f"BPM ~{bpm:.1f} e buona presenza in high-mid/high → sound aperto, progressive house."
            )
        else:
            genre_label = "House / EDM generica"
            reason = (
                f"BPM ~{bpm:.1f}, distribuzione energia non così caratteristica: area house/EDM generica."
            )

    # Future Bass / Pop elettronica
    elif 110 <= bpm < 122:
        genre_label = "Future Bass / Pop Elettronica"
        reason = f"BPM medio-bassi (~{bpm:.1f}), tipici di future bass o pop elettronica."

    # BPM bassi → downtempo / chill
    elif bpm < 110:
        genre_label = "Downtempo / Chill"
        reason = f"BPM bassi (~{bpm:.1f}), zona downtempo/chill."

    return genre_label, reason


# ============================================================
# 5. CONTESTO COMUNE PER GLI AGENTI
# ============================================================

def estimate_genre_ml(y, sr):
    """
    Stub per un futuro modello ML di classificazione del genere.
    Al momento ritorna (None, motivo), così il codice fa fallback
    all'euristica basata su BPM + distribuzione delle energie.
    """
    return None, "Modello ML non ancora addestrato: uso l'euristica (BPM + distribuzione energie)."

def build_common_context(user_summary,
                         comparison_summary=None,
                         y_audio=None,
                         sr=None,
                         adv_analysis=None):
    """
    Costruisce una descrizione testuale dei dati tecnici,
    riutilizzabile in tutti i prompt degli agenti.
    Usa:
      - summary (RMS, BPM, key, energy per bande)
      - eventuale confronto con reference
      - modello ML per il genere (se disponibile)
      - analisi avanzata (LUFS, LRA, crest factor, transienti, bande fini)
    """

    # 1) Genere: prova con modello ML, poi fallback a euristica
    auto_genre = None
    genre_reason = ""

    if y_audio is not None and sr is not None:
        ml_genre, ml_reason = estimate_genre_ml(y_audio, sr)
        if ml_genre is not None:
            auto_genre = ml_genre
            genre_reason = ml_reason

    if auto_genre is None:
        auto_genre, genre_reason = estimate_genre_from_summary(user_summary)

    # 2) Dati base dal summary
    e = user_summary["energy_percent"]

    lines = []
    lines.append(f"Genere stimato automaticamente: {auto_genre}.")
    lines.append(f"Motivo della stima: {genre_reason}")
    lines.append("")
    lines.append(f"Durata: {user_summary['duration_sec']:.1f} secondi")
    lines.append(f"BPM stimato: {user_summary.get('bpm', 0) or 0:.1f}")
    lines.append(f"Tonalità stimata (nota fondamentale): {user_summary.get('key_root', 'N/A')}")
    lines.append(f"RMS medio: {user_summary['rms_mean']:.5f}")
    lines.append(f"RMS massimo: {user_summary['rms_max']:.5f}")
    lines.append("")
    lines.append("Distribuzione energia (percentuale, banda larga):")
    lines.append(f"- Sub (20-60 Hz): {e['sub']:.1f}%")
    lines.append(f"- Bass (60-150 Hz): {e['bass']:.1f}%")
    lines.append(f"- Low-mid (150-500 Hz): {e['lowmid']:.1f}%")
    lines.append(f"- High-mid (500-4000 Hz): {e['highmid']:.1f}%")
    lines.append(f"- High (4k-20k Hz): {e['high']:.1f}%")

    # 3) Confronto con reference (se presente)
    if comparison_summary is not None:
        de = comparison_summary["diff_energy_percent"]
        lines.append("")
        lines.append("Confronto con traccia di reference (utente - reference):")
        lines.append(f"- Differenza RMS medio: {comparison_summary['diff_rms_mean']:.5f}")
        lines.append("Differenze energia (punti percentuali, positivo = utente più carico):")
        lines.append(f"  * Sub: {de['sub']:+.1f}")
        lines.append(f"  * Bass: {de['bass']:+.1f}")
        lines.append(f"  * Low-mid: {de['lowmid']:+.1f}")
        lines.append(f"  * High-mid: {de['highmid']:+.1f}")
        lines.append(f"  * High: {de['high']:+.1f}")

    # 4) Analisi avanzata (se disponibile)
    if adv_analysis is not None:
        loud = adv_analysis["loudness"]
        bands = adv_analysis["bands_energy_percent"]
        trans = adv_analysis["transients"]

        lines.append("")
        lines.append("Analisi avanzata di loudness e dinamica:")
        lines.append(f"- LUFS integrato: {loud['integrated_lufs']:.1f} LUFS")
        lines.append(f"- Loudness Range (LRA): {loud['loudness_range']:.1f} dB")
        lines.append(f"- Crest factor: {loud['crest_factor_db']:.1f} dB")

        lines.append("")
        lines.append("Distribuzione energia fine per bande (percentuale):")
        lines.append(f"- Sub 20–40 Hz: {bands['sub_20_40']:.1f}%")
        lines.append(f"- Bass 40–80 Hz: {bands['bass_40_80']:.1f}%")
        lines.append(f"- Bass 80–150 Hz: {bands['bass_80_150']:.1f}%")
        lines.append(f"- Low-mid 150–500 Hz: {bands['lowmid_150_500']:.1f}%")
        lines.append(f"- Mid 500–2000 Hz: {bands['mid_500_2000']:.1f}%")
        lines.append(f"- High-mid 2k–6k Hz: {bands['highmid_2k_6k']:.1f}%")
        lines.append(f"- Air 6k–20k Hz: {bands['air_6k_20k']:.1f}%")

        lines.append("")
        lines.append("Transienti:")
        lines.append(f"- Numero transiente stimati: {trans['count']}")
        lines.append(f"- Densità transienti: {trans['density_per_sec']:.2f} al secondo")

    context_text = "\n".join(lines)
    return auto_genre, context_text


# ============================================================
# 5B. FUNZIONI DI SUPPORTO PER RAG
# ============================================================

def genre_to_kb_key(auto_genre: str) -> str:
    """
    Converte il genere stimato in una chiave compatibile con la KB.
    Mappa solo i generi che abbiamo davvero in kb/, altrimenti torna 'all'.
    """
    if not auto_genre:
        return "all"

    g = auto_genre.lower().strip()

    # Progressive House
    if "progressive" in g:
        return "progressive_house"

    # Melodic Techno
    if "melodic" in g and "techno" in g:
        return "melodic_techno"

    # Future Bass / Pop Elettronica
    if "future bass" in g or "pop elettronica" in g:
        return "future_bass"
    
    if "hardstyle" in g:
        return "hardstyle"

    if "big room" in g or "edm festival" in g:
        return "big_room"

    if "trance" in g:
        return "trance"

    if "psy" in g:
        return "psytrance"



    # Tutto il resto (big room, hardstyle, trance, ecc.) → nessun filtro di genere
    return "all"


def rag_retrieve_context(query: str,
                         topic: str = "generic",
                         genre: str = "all",
                         top_k: int = 4) -> str:
    """
    Query RAG adattata per versioni di Chroma che vogliono:
    - un solo operatore in `where` (es. {"topic": "mix"}) OPPURE
    - nessun campo `where` se non ci sono filtri.
    """

    try:
        # Crea client persistente su cartella DB
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_collection(KB_COLLECTION_NAME)

        # Calcola embedding della query con Ollama usando il modello fisso
        emb_res = ollama.embeddings(model=OLLAMA_EMBED_MODEL, prompt=query)
        query_vec = emb_res["embedding"]

        # Decidiamo il filtro where
        where = None

        # 1) Se abbiamo un genere mappato → filtra per genere
        if genre != "all":
            where = {"genre": genre}

        # 2) Altrimenti, se abbiamo un topic specifico → filtra per topic
        elif topic != "generic":
            where = {"topic": topic}

        # 3) Altrimenti nessun filtro (where = None → NON viene passato)

        # Costruiamo i parametri per collection.query
        query_kwargs = {
            "query_embeddings": [query_vec],
            "n_results": top_k,
        }

        # Aggiungiamo where SOLO se esiste ed è non-vuoto
        if where:
            query_kwargs["where"] = where

        # Eseguiamo la query
        results = collection.query(**query_kwargs)

        # Estraiamo i documenti (lista di liste: [ [doc1, doc2, ...] ])
        docs = results.get("documents", [[]])[0]
        if not docs:
            return ""

        # Uniamo i documenti con separatori
        return "\n\n---\n\n".join(docs)

    except Exception as e:
        print("⚠️ Errore nel RAG / Chroma:", e)
        return ""


# ============================================================
# 6. FUNZIONE LLM GENERICA PER RUOLI (AGENTI)
# ============================================================

def call_llm_role(system_prompt: str,
                  user_prompt: str,
                  model_name: str = None) -> str:
    """
    Chiama il modello Ollama specificando:
        - system_prompt: ruolo e personalità dell'agente
        - user_prompt: dati tecnici + compito da svolgere
    Usa sempre il modello 'mistral' se model_name è None.
    Ritorna:
        testo della risposta del modello
    """
    # Se non è stato passato un modello, usiamo il modello di default
    if model_name is None:
        model_name = OLLAMA_CHAT_MODEL

    # Debug: stampa il tipo di ruolo chiamato
    print(
        f"👉 Chiamata LLM (modello={model_name}) | Ruolo: {system_prompt[:70]}..."
    )

    try:
        # Chiamata a Ollama in modalità chat
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # Opzioni per velocizzare la risposta (meno token generati)
            options={
                "num_predict": MAX_LLM_TOKENS
            },
        )

        # Estrae il contenuto testuale
        content = response["message"]["content"]

        print("✅ Risposta ricevuta dal modello.")
        return content

    except Exception as e:
        # In caso di errore, mostra l'errore e ritorna un messaggio di fallback
        print("❌ ERRORE chiamando Ollama:", e)
        return "Errore nella chiamata al modello LLM. Verifica che Ollama sia attivo e il modello sia installato."


# ============================================================
# 7. DEFINIZIONE DEI 4 AGENTI (CON RAG)
# ============================================================

def run_mix_agent(common_context: str, auto_genre: str) -> str:
    """
    Agente 1: Mix Engineer
    Usa RAG per:
        - recuperare linee guida di mix specifiche per il genere
        - integrare concetti generici (sidechain, mastering, ecc.)
        - confrontare la traccia con tali linee guida
    """
    # Prompt di sistema: definisce il ruolo dell'agente
    system = (
        "Sei un mix engineer esperto di musica elettronica. "
        "Ti concentri solo su EQ, dinamica, stereo e loudness. "
        "Dai consigli tecnici precisi, senza frasi vaghe."
    )

    # Chiave di genere compatibile con i metadati della KB
    genre_key = genre_to_kb_key(auto_genre)

    # Query per il RAG (specifica per il mix di questo genere)
    rag_query = (
        f"Linee guida di mixing per il genere {auto_genre}. "
        "Focus su kick, sub, bassi, high-mid, stereo e loudness (LUFS)."
    )

    # 1) Contesto specifico di mix per il genere
    rag_mix_context = rag_retrieve_context(
        query=rag_query,
        topic="mix",
        genre=genre_key,
        top_k=3
    )

    # 2) Contesto generico di sidechain / mastering (topic generic)
    rag_generic_context = rag_retrieve_context(
        query="linee guida generali su sidechain e mastering per musica elettronica",
        topic="generic",
        genre="all",   # nessun filtro sul genere: regole generali
        top_k=2
    )

    # Uniamo i contesti (mix + generic)
    combined_context_parts = []
    if rag_mix_context:
        combined_context_parts.append(rag_mix_context)
    if rag_generic_context:
        combined_context_parts.append(rag_generic_context)

    combined_context = "\n\n---\n\n".join(combined_context_parts)

    # Prompt utente: knowledge base + dati tecnici + compito
    user = (
        "CONOSCENZA DI RIFERIMENTO (knowledge base del producer per il MIX):\n"
        + (combined_context or "[Nessuna regola specifica trovata in KB, usa conoscenza generale di mix]\n")
        + "\n\n"
        + "DATI TECNICI DEL BRANO ANALIZZATO:\n"
        + common_context
        + "\n\n"
        + "COMPITO MIX ENGINEER:\n"
        "1) Descrivi i problemi principali di mix (bassi, medi, alti, loudness) del brano ANALIZZATO.\n"
        "2) Suggerisci azioni concrete in DAW (EQ, compressione, sidechain), "
        "indicando frequenze, direzione (boost/cut) e valori indicativi (dB, ratio, ecc.).\n"
        "3) Confronta, quando utile, la situazione del brano con le linee guida della knowledge base.\n"
    )

    # Chiama l'LLM con questo ruolo
    return call_llm_role(system, user)


def run_theory_agent(common_context: str, auto_genre: str) -> str:
    """
    Agente 2: Music Theory / Harmony
    Usa RAG per:
        - recuperare progressioni e concetti armonici tipici del genere
        - proporre accordi e varianti utilizzabili in produzione
    """
    # Prompt di sistema per teoria musicale
    system = (
        "Sei un esperto di teoria musicale e arrangiamento per musica elettronica. "
        "Il tuo lavoro è proporre accordi, progressioni e variazioni adatte al genere stimato. "
        "Usa linguaggio tecnico quando serve, ma sempre chiaro e orientato alla produzione moderna. "
        "Non divagare, non fare storytelling, non parlare di storia della musica. "
        "Concentrati su: tonalità, funzione armonica, ruolo degli accordi nel drop/breakdown, estensioni utili."
    )

    # Chiave di genere per la KB
    genre_key = genre_to_kb_key(auto_genre)

    # Query per il RAG (topic 'harmony')
    rag_query = (
        f"Progressioni di accordi tipiche e suggerimenti armonici per il genere {auto_genre}. "
        "Focus su progressioni adatte a drop, breakdown e intro."
    )

    # Recupera contesto armonico dalla knowledge base
    rag_context = rag_retrieve_context(
        query=rag_query,
        topic="harmony",
        genre=genre_key,
        top_k=3
    )

    # Prompt utente con conoscenza + dati tecnici + compito
    user = (
        "CONOSCENZA DI RIFERIMENTO (linee guida armoniche dalla knowledge base):\n"
        + (rag_context or "[Nessuna regola armonica specifica trovata, usa conoscenza generale di armonia]\n")
        + "\n\n"
        + "DATI TECNICI DEL BRANO ANALIZZATO:\n"
        + common_context
        + "\n\n"
        + "COMPITO MUSIC THEORY:\n"
        "1) Proponi una progressione di accordi di 8 battute coerente con:\n"
        "   - BPM\n"
        "   - tonalità del brano\n"
        "   - genere stimato\n"
        "   - caratteristiche timbriche del segmento analizzato\n\n"
        "   Usa questo formato esatto:\n"
        "   | Dm7 | Bb | C | F | ... |\n\n"
        "2) Spiega la funzione armonica degli accordi scelti:\n"
        "   - tonica / sottodominante / dominante\n"
        "   - tensioni usate (9, 11, 13)\n"
        "   - eventuali inversioni o voicing moderni\n\n"
        "3) Suggerisci una variante per:\n"
        "   - breakdown (più aperta e atmosferica)\n"
        "   - secondo drop (più energetica)\n\n"
        "4) Indica 1–2 tecniche specifiche del genere per rendere l’armonia più \"professionale\" "
        "(pedal note, modal mixture, accordi a 5 voci, parallelismi, ecc.).\n"
    )

    return call_llm_role(system, user)


def run_creative_agent(common_context: str, auto_genre: str) -> str:
    """
    Agente 3: Creative Producer
    Usa RAG per:
        - recuperare hook, pattern e idee creative tipiche del genere
        - proporre lead, bassline e variazioni
        - generare una melodia finale in formato MIDI testuale [MELODY_MIDI]
    """
    # Prompt di sistema per il producer creativo
    system = (
        "Sei un producer creativo di musica elettronica. "
        "Il tuo compito è generare idee melodiche, hook, pattern ritmici e bassline coerenti con il genere. "
        "Il tuo stile è moderno e orientato al club. "
        "Evita frasi generiche e rendi ogni suggerimento utilizzabile in DAW. "
        "Genera sempre melodie che rispettino la tonalità stimata."
    )

    # Chiave di genere per la KB
    genre_key = genre_to_kb_key(auto_genre)

    # Query per il RAG (topic 'creative')
    rag_query = (
        f"Idee di hook melodici, pattern ritmici e layering tipici per il genere {auto_genre}. "
        "In particolare per i drop."
    )

    # Recupera contesto creativo dalla knowledge base
    rag_context = rag_retrieve_context(
        query=rag_query,
        topic="creative",
        genre=genre_key,
        top_k=3
    )

    # Prompt utente con knowledge base + dati tecnici + compito, inclusa sezione MIDI
    user = (
        "CONOSCENZA DI RIFERIMENTO (hook, melodie e pattern tipici del genere dalla knowledge base):\n"
        + (rag_context or "[Nessuna informazione creativa specifica trovata, usa creatività generale per il genere]\n")
        + "\n\n"
        + "DATI TECNICI DEL BRANO ANALIZZATO:\n"
        + common_context
        + "\n\n"
        + "COMPITO CREATIVE PRODUCER:\n"
        "1) Proponi un’idea melodica per il lead del drop.\n"
        "   - Deve essere breve (1–2 battute)\n"
        "   - Deve rispettare tonalità e stile del genere\n"
        "   - Puoi descriverla in linguaggio naturale (note, intervalli, pattern).\n\n"
        "2) Suggerisci un pattern ritmico del lead (accenti, sincopi, durate).\n\n"
        "3) Proponi un pattern di bassline coerente con la progressione di accordi:\n"
        "   - indica su quali tempi della battuta cadono gli attacchi principali\n"
        "   - indica se il basso segue tonica, quinta o un semplice contrappunto melodico\n\n"
        "4) Descrivi brevemente una variazione del lead per il secondo drop.\n\n"
        "5) MOLTO IMPORTANTE – Formato MIDI:\n"
        "   Alla fine della risposta aggiungi SEMPRE un blocco in questo formato esatto:\n\n"
        "   [MELODY_MIDI]\n"
        "   C4 1\n"
        "   E4 0.5\n"
        "   G4 2\n"
        "   A4 1\n"
        "   [/MELODY_MIDI]\n\n"
        "   Dove ogni riga contiene:\n"
        "   - NOME_NOTA + OTTAVA (es: C4, D#5, G3)\n"
        "   - DURATA IN BATTITI (es: 1, 0.5, 2)\n\n"
        "   Questo blocco deve essere valido per generare un file MIDI.\n"
        "   NON aggiungere commenti dentro al blocco, solo linee NOME_NOTA DURATA.\n"
    )

    return call_llm_role(system, user)


def run_orchestrator_agent(auto_genre: str,
                           common_context: str,
                           mix_text: str,
                           theory_text: str,
                           creative_text: str) -> str:
    """
    Agente 4: Orchestrator
    Unisce le analisi degli altri 3 agenti in un piano d'azione unico e ordinato.
    """
    system = (
        "Sei un orchestratore di feedback per un producer di musica elettronica. "
        "Hai ricevuto tre analisi: mix engineer, teorico musicale e creative producer. "
        "Il tuo compito è unire tutto in un piano d'azione chiaro e ordinato per il producer."
    )

    # Costruisce il prompt utente con:
    # - contesto comune
    # - genere stimato
    # - analisi dei tre agenti
    # - compito finale
    lines = []
    lines.append(common_context)
    lines.append("")
    lines.append(f"Genere stimato: {auto_genre}")
    lines.append("")
    lines.append("=== ANALISI MIX ENGINEER ===")
    lines.append(mix_text)
    lines.append("")
    lines.append("=== ANALISI MUSIC THEORY ===")
    lines.append(theory_text)
    lines.append("")
    lines.append("=== ANALISI CREATIVE PRODUCER ===")
    lines.append(creative_text)
    lines.append("")
    lines.append("COMPITO ORCHESTRATOR:\n"
                 "1) Riassumi i punti chiave di ciascun agente.\n"
                 "2) Crea una lista di TODO per il producer, ordinata per priorità (1, 2, 3...).\n"
                 "3) Separa chiaramente le sezioni: MIX, ACCORDI/ARMONIA, MELODIA/BASSLINE.\n"
                 "4) Mantieni coerenza con il genere stimato.\n")

    user = "\n".join(lines)

    # Chiama l'LLM con il ruolo di orchestrator
    return call_llm_role(system, user)


# ============================================================
# 8. PIPELINE MULTI-AGENTE
# ============================================================

def run_multiagent_pipeline(user_summary,
                            comparison_summary=None,
                            y_audio=None,
                            sr=None,
                            adv_analysis=None):
    """
    Esegue la pipeline multi-agente:
        - costruisce il contesto comune
        - lancia i 3 agenti: mix, teoria, creativo (tutti con RAG)
        - lancia l'orchestrator per un piano finale
    Parametri:
        user_summary: riassunto della traccia utente
        comparison_summary: eventuale confronto con reference
    Ritorna:
        dizionario con:
            - genere stimato
            - testo degli agenti
            - piano finale
    """
    # Costruisce contesto comune e stima genere
    
    
    auto_genre, common_context = build_common_context(
        user_summary=user_summary,
        comparison_summary=comparison_summary,
        y_audio=y_audio,
        sr=sr,
        adv_analysis=adv_analysis
    )

    # Esegue agente Mix (con RAG)
    mix_text = run_mix_agent(common_context, auto_genre)

    # Esegue agente Teoria Musicale (con RAG)
    theory_text = run_theory_agent(common_context, auto_genre)

    # Esegue agente Creativo (con RAG + blocco MIDI)
    creative_text = run_creative_agent(common_context, auto_genre)

    # Esegue Orchestrator (unisce tutto)
    final_text = run_orchestrator_agent(
        auto_genre=auto_genre,
        common_context=common_context,
        mix_text=mix_text,
        theory_text=theory_text,
        creative_text=creative_text
    )

    # Ritorna tutti i risultati
    return {
        "genre": auto_genre,
        "context": common_context,
        "mix_agent": mix_text,
        "theory_agent": theory_text,
        "creative_agent": creative_text,
        "orchestrator_agent": final_text,
        "final_plan": final_text  # alias per compatibilità con la GUI
    }


# ============================================================
# 9. FUNZIONE PRINCIPALE: ANALISI COMPLETA SENZA GRAFICI
# ============================================================

def analyze_track(user_path,
                  reference_path=None):
    """
    Pipeline completa:
        - carica traccia utente
        - calcola feature audio
        - crea summary numerico
        - (opzionale) analizza reference e confronta
        - lancia pipeline multi-agente (con RAG)
    Parametri:
        user_path: percorso file audio utente
        reference_path: percorso file audio reference (o None)
    Ritorna:
        dizionario con risultati multi-agente (incluso piano finale)
    """
    print("🎧 Analisi traccia utente:", user_path)

    # Carica segnale audio utente
    y, sr = load_audio(user_path)

    # Calcola feature
    feats = compute_features(y, sr)

    # Crea riassunto numerico
    user_summary = summarize_track_features(feats)
    
    # Analisi avanzata (LUFS, bande fini, transiente, ecc.)
    adv_analysis = compute_advanced_analysis(y, sr)

    # Inizializza confronto come None
    comparison_summary = None

    # Gestione opzionale della reference
    if reference_path is not None:
        # Verifica che il file esista
        if os.path.exists(reference_path):
            print("🎧 Analisi traccia di reference:", reference_path)

            # Carica e analizza la reference
            y_ref, sr_ref = load_audio(reference_path)
            feats_ref = compute_features(y_ref, sr_ref)
            ref_summary = summarize_track_features(feats_ref)

            # Crea confronto utente vs reference
            comparison_summary = compare_summaries(user_summary, ref_summary)
        else:
            print(f"⚠️ Reference non trovata: {reference_path} (salto il confronto)")

    # Esegue pipeline multi-agente
    results = run_multiagent_pipeline(
        user_summary=user_summary,
        comparison_summary=comparison_summary,
        y_audio=y,
        sr=sr,
        adv_analysis=adv_analysis
    )

    # Stampa genere stimato
    print("\n================ GENERE STIMATO =================\n")
    print(results["genre"])

    # Stampa piano finale orchestrato
    print("\n================ PIANO FINALE ORCHESTRATOR =================\n")
    print(results["final_plan"])
    print("\n============================================================\n")

    # Ritorna il dizionario completo
    return results


# ============================================================
# 10. ENTRY POINT (ESEMPIO USO DA TERMINALE)
# ============================================================

if __name__ == "__main__":
    # Percorso della traccia utente (sostituisci con il tuo file)
    user_track_path = "mia_traccia.wav"

    # Percorso della reference (metti un file reale o None)
    reference_track_path = None  # es: "reference.wav"

    # Esegui la pipeline di analisi + multi-agente
    analyze_track(
        user_path=user_track_path,
        reference_path=reference_track_path
    )
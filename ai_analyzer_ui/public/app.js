// Seleziona l'input file dal DOM
const audioFileInput = document.getElementById("audioFileInput");
// Seleziona il pulsante play/pausa
const playPauseBtn = document.getElementById("playPauseBtn");
// Seleziona lo slider di posizione
const positionSlider = document.getElementById("positionSlider");
// Seleziona le etichette del tempo corrente e della durata
const currentTimeLabel = document.getElementById("currentTimeLabel");
const durationLabel = document.getElementById("durationLabel");
// Seleziona il canvas per lo spettro
const spectrumCanvas = document.getElementById("spectrumCanvas");
// Ottiene il contesto 2D per disegnare sul canvas
const canvasCtx = spectrumCanvas.getContext("2d");

// Seleziona gli slider di taglio e le etichette
const trimStartSlider = document.getElementById("trimStartSlider");
const trimEndSlider = document.getElementById("trimEndSlider");
const trimStartLabel = document.getElementById("trimStartLabel");
const trimEndLabel = document.getElementById("trimEndLabel");
// Checkbox per il loop della sola selezione
const loopSelectionCheckbox = document.getElementById("loopSelectionCheckbox");

// Seleziona il bottone di analisi AI e il box di output
const analyzeBtn = document.getElementById("analyzeBtn");
const analysisOutput = document.getElementById("analysisOutput");

// Variabili per l'audio
let audioContext = null;       // AudioContext del Web Audio API
let audioElement = null;       // Elemento <audio> nascosto
let sourceNode = null;         // Sorgente audio collegata al context
let analyserNode = null;       // Nodo Analyser per ottenere lo spettro
let dataArray = null;          // Array con i valori di intensità delle frequenze
let animationId = null;        // ID dell'animazione requestAnimationFrame
let isPlaying = false;         // Stato attuale del playback

// Variabili per memorizzare inizio/fine selezione (in secondi)
let trimStartSec = 0;
let trimEndSec = 0;

// Aggiunge un listener per quando l'utente seleziona un file audio
audioFileInput.addEventListener("change", async (event) => {
  // Estrae il file selezionato dalla lista dei file
  const file = event.target.files[0];

  // Se non c'è nessun file (utente annulla), esce
  if (!file) {
    return;
  }

  // Se esiste già un AudioContext, lo chiudiamo per pulire le risorse
  if (audioContext) {
    await audioContext.close(); // chiude il context precedente
    audioContext = null;        // resetta la variabile
  }

  // Crea un nuovo elemento audio
  audioElement = new Audio();
  // Imposta l'URL del file audio usando un oggetto URL temporaneo
  audioElement.src = URL.createObjectURL(file);
  // Imposta che non deve ripetere in loop (lo gestiamo noi con il loop selezione)
  audioElement.loop = false;

  // Crea un nuovo AudioContext
  audioContext = new (window.AudioContext || window.webkitAudioContext)();

  // Crea un MediaElementSource che collega l'elemento audio al context
  sourceNode = audioContext.createMediaElementSource(audioElement);

  // Crea un nodo Analyser per ottenere lo spettro
  analyserNode = audioContext.createAnalyser();
  // Imposta la dimensione del buffer FFT (più alto = più dettagli, ma più pesante)
  analyserNode.fftSize = 2048;

  // Calcola metà del numero di bin di frequenza (N/2)
  const bufferLength = analyserNode.frequencyBinCount;

  // Crea un array per contenere i dati di magnitudo delle frequenze
  dataArray = new Uint8Array(bufferLength);

  // Collega la sorgente audio all'analyser
  sourceNode.connect(analyserNode);
  // Collega l'analyser all'output (le casse)
  analyserNode.connect(audioContext.destination);

  // Quando i metadati sono caricati (es: durata), aggiorniamo UI
  audioElement.addEventListener("loadedmetadata", () => {
    // Abilita i controlli ora che l'audio è pronto
    playPauseBtn.disabled = false;
    positionSlider.disabled = false;

    // Imposta slider con min=0 e max=durata in secondi
    positionSlider.min = 0;
    positionSlider.max = audioElement.duration;
    positionSlider.value = 0;

    // Aggiorna l'etichetta della durata totale
    durationLabel.textContent = formatTime(audioElement.duration);
    // Reimposta etichetta tempo corrente
    currentTimeLabel.textContent = "0:00";

    // Inizializza i valori di taglio: inizio = 0, fine = durata
    trimStartSec = 0;
    trimEndSec = audioElement.duration;

    // Configura gli slider di taglio con stessi limiti della traccia
    trimStartSlider.min = 0;
    trimStartSlider.max = audioElement.duration;
    trimStartSlider.value = trimStartSec;

    trimEndSlider.min = 0;
    trimEndSlider.max = audioElement.duration;
    trimEndSlider.value = trimEndSec;

    // Aggiorna le etichette testuali dei tempi di taglio
    trimStartLabel.textContent = formatTime(trimStartSec);
    trimEndLabel.textContent = formatTime(trimEndSec);

    // Abilita gli slider di taglio
    trimStartSlider.disabled = false;
    trimEndSlider.disabled = false;

    // Abilita bottone di analisi AI ora che abbiamo una traccia
    analyzeBtn.disabled = false;
  });

  // Quando l'audio avanza nel tempo, aggiorniamo slider e label
  audioElement.addEventListener("timeupdate", () => {
    // Aggiorna la posizione dello slider in base al currentTime
    positionSlider.value = audioElement.currentTime;
    // Aggiorna il testo dell'orario corrente
    currentTimeLabel.textContent = formatTime(audioElement.currentTime);

    // Se è attivo il loop della selezione, quando superiamo il fine torniamo all'inizio
    if (loopSelectionCheckbox.checked) {
      // Se il tempo corrente supera il fine selezionato, torniamo all'inizio selezionato
      if (audioElement.currentTime > trimEndSec) {
        audioElement.currentTime = trimStartSec;
      }
    }
  });

  // Quando la traccia finisce, aggiorna lo stato
  audioElement.addEventListener("ended", () => {
    // Imposta flag playback su false
    isPlaying = false;
    // Cambia il testo del pulsante su "Play"
    playPauseBtn.textContent = "▶ Play";
    // Rimette lo slider alla fine traccia
    positionSlider.value = audioElement.duration;
  });

  // Ferma eventuali animazioni precedenti dello spettro
  if (animationId) {
    cancelAnimationFrame(animationId);
  }

  // Avvia il loop di disegno dello spettro
  drawSpectrum();
});

// Listener per il pulsante Play/Pausa
playPauseBtn.addEventListener("click", async () => {
  // Se non abbiamo ancora un audioElement o audioContext, non facciamo nulla
  if (!audioElement || !audioContext) {
    return;
  }

  // Se l'audio è in pausa, avviamo la riproduzione
  if (!isPlaying) {
    // Alcuni browser richiedono di riprendere il context sospeso
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }
    // Avvia il playback
    await audioElement.play();
    // Imposta lo stato a "in riproduzione"
    isPlaying = true;
    // Cambia il testo del pulsante su "Pausa"
    playPauseBtn.textContent = "⏸ Pausa";
  } else {
    // Se l'audio sta suonando, mettiamo in pausa
    audioElement.pause();
    // Imposta lo stato a "non in riproduzione"
    isPlaying = false;
    // Cambia il testo del pulsante su "Play"
    playPauseBtn.textContent = "▶ Play";
  }
});

// Listener per lo slider di posizione principale
positionSlider.addEventListener("input", () => {
  // Se non abbiamo ancora un audioElement, usciamo
  if (!audioElement) {
    return;
  }

  // Converte il valore dello slider (stringa) in numero
  const newTime = parseFloat(positionSlider.value);
  // Imposta il currentTime dell'audio in base alla posizione dello slider
  audioElement.currentTime = newTime;

  // Aggiorna immediatamente l'etichetta del tempo corrente
  currentTimeLabel.textContent = formatTime(newTime);
});

// Listener per lo slider di inizio taglio
trimStartSlider.addEventListener("input", () => {
  // Se non c'è audio, usciamo
  if (!audioElement) {
    return;
  }

  // Legge il nuovo valore di inizio in secondi
  const newStart = parseFloat(trimStartSlider.value);

  // Garantisce che l'inizio non superi la fine
  if (newStart >= trimEndSec) {
    // Se l'utente trascina oltre, spostiamo anche il fine un po' più avanti
    trimEndSec = Math.min(newStart + 0.1, audioElement.duration);
    trimEndSlider.value = trimEndSec;
    trimEndLabel.textContent = formatTime(trimEndSec);
  }

  // Aggiorna la variabile globale
  trimStartSec = newStart;

  // Aggiorna l'etichetta testuale dell'inizio
  trimStartLabel.textContent = formatTime(trimStartSec);

  // Sposta l'audio nel nuovo punto, così SENTI subito cosa stai tagliando
  audioElement.currentTime = trimStartSec;
  currentTimeLabel.textContent = formatTime(trimStartSec);
  positionSlider.value = trimStartSec;
});

// Listener per lo slider di fine taglio
trimEndSlider.addEventListener("input", () => {
  // Se non c'è audio, usciamo
  if (!audioElement) {
    return;
  }

  // Legge il nuovo valore di fine in secondi
  const newEnd = parseFloat(trimEndSlider.value);

  // Garantisce che la fine non sia prima dell'inizio
  if (newEnd <= trimStartSec) {
    // Se l'utente trascina prima dell'inizio, spostiamo anche l'inizio un po' indietro
    trimStartSec = Math.max(newEnd - 0.1, 0);
    trimStartSlider.value = trimStartSec;
    trimStartLabel.textContent = formatTime(trimStartSec);
  }

  // Aggiorna la variabile globale
  trimEndSec = newEnd;

  // Aggiorna l'etichetta testuale della fine
  trimEndLabel.textContent = formatTime(trimEndSec);

  // Sposta l'audio nel nuovo punto, così senti la parte finale della selezione
  audioElement.currentTime = trimEndSec;
  currentTimeLabel.textContent = formatTime(trimEndSec);
  positionSlider.value = trimEndSec;
});

// Listener per il bottone "Analizza con AI"
analyzeBtn.addEventListener("click", async () => {
  // Se non c'è file selezionato, usciamo
  const file = audioFileInput.files[0];
  if (!file) {
    analysisOutput.textContent = "⚠ Nessun file selezionato.";
    return;
  }

  try {
    // Mostra messaggio di stato
    analysisOutput.textContent = "⏳ Analisi in corso...";

    // Crea un oggetto FormData per inviare file + parametri
    const formData = new FormData();
    // Aggiunge il file audio
    formData.append("file", file);
    // Aggiunge i parametri di taglio (inizio/fine in secondi)
    formData.append("trim_start", trimStartSec.toString());
    formData.append("trim_end", trimEndSec.toString());

    // Esegue una richiesta POST al backend Python
    const response = await fetch("http://localhost:8001/analyze", {
      method: "POST",
      body: formData,
    });

    // Se la risposta non è ok, mostra errore
    if (!response.ok) {
      analysisOutput.textContent =
        "❌ Errore dal backend: " + response.statusText;
      return;
    }

    // Converte la risposta in JSON
    const data = await response.json();

    // Costruisce una stringa leggibile con i risultati principali
    const text =
      `🎼 Genere stimato: ${data.genre ?? "N/A"}\n\n` +
      `=== PIANO FINALE ===\n${data.final_plan ?? ""}\n\n` +
      `=== MIX ENGINEER ===\n${data.mix_agent ?? ""}\n\n` +
      `=== MUSIC THEORY ===\n${data.theory_agent ?? ""}\n\n` +
      `=== CREATIVE PRODUCER ===\n${data.creative_agent ?? ""}`;

    // Mostra il testo nel box
    analysisOutput.textContent = text;
  } catch (err) {
    // In caso di eccezioni, mostra l'errore
    analysisOutput.textContent = "❌ Errore di rete o backend: " + err;
  }
});

// Funzione per formattare un tempo in secondi in formato M:SS
function formatTime(timeInSeconds) {
  // Arrotonda il tempo all'intero più vicino
  const totalSeconds = Math.floor(timeInSeconds);
  // Calcola i minuti interi
  const minutes = Math.floor(totalSeconds / 60);
  // Calcola i secondi rimanenti
  const seconds = totalSeconds % 60;
  // Ritorna la stringa nel formato M:SS (aggiungendo uno zero se serve)
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

// Funzione che disegna lo spettro sul canvas a ogni frame
function drawSpectrum() {
  // Richiede al browser di chiamare drawSpectrum al prossimo frame (60fps circa)
  animationId = requestAnimationFrame(drawSpectrum);

  // Se l'analyser non è pronto, puliamo il canvas e usciamo
  if (!analyserNode || !dataArray) {
    canvasCtx.clearRect(0, 0, spectrumCanvas.width, spectrumCanvas.height);
    return;
  }

  // Chiede all'analyser di riempire dataArray con i dati di frequenza (0-255)
  analyserNode.getByteFrequencyData(dataArray);

  // Prende larghezza e altezza del canvas
  const width = spectrumCanvas.width;
  const height = spectrumCanvas.height;

  // Cancella il canvas riempiendolo con uno sfondo scuro
  canvasCtx.fillStyle = "#020617";
  canvasCtx.fillRect(0, 0, width, height);

  // Numero di barrette che vogliamo disegnare nello spettro
  const barCount = 120;
  // Calcola di quanti "bin" dello spettro aggregare per ogni barretta
  const step = Math.floor(dataArray.length / barCount);

  // Larghezza di ogni barretta (con spazio tra una e l'altra)
  const barWidth = (width / barCount) * 0.9;
  // Spazio aggiuntivo tra le barrette
  const barGap = (width / barCount) * 0.1;

  // Cicla su ogni barretta da disegnare
  for (let i = 0; i < barCount; i++) {
    // Calcola l'indice di partenza nel dataArray per questa barretta
    const start = i * step;
    // Calcola l'indice di fine (senza superare la lunghezza dell'array)
    const end = Math.min(start + step, dataArray.length);

    // Inizializza una somma per la media di ampiezza
    let sum = 0;
    // Accumula tutti i valori dei bin di questa finestra
    for (let j = start; j < end; j++) {
      sum += dataArray[j];
    }

    // Calcola il valore medio per questa barretta
    const avg = sum / (end - start || 1);

    // Calcola l'altezza della barretta in base al valore medio
    const barHeight = (avg / 255) * height;

    // Posizione X orizzontale della barretta
    const x = i * (barWidth + barGap);
    // Posizione Y verticale (disegniamo dal basso verso l'alto)
    const y = height - barHeight;

    // Crea un gradiente verticale per rendere le barrette più "cool"
    const gradient = canvasCtx.createLinearGradient(x, y, x, height);
    gradient.addColorStop(0, "#38bdf8");
    gradient.addColorStop(0.5, "#0ea5e9");
    gradient.addColorStop(1, "#0369a1");

    // Imposta il fillStyle sul gradiente appena creato
    canvasCtx.fillStyle = gradient;
    // Disegna il rettangolo (barretta) sul canvas
    canvasCtx.fillRect(x, y, barWidth, barHeight);
  }
}
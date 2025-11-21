# Developer Notes – AI Music Analyzer

Queste note sono pensate per sviluppatori che devono capire e modificare il progetto.

---

## 🔥 Architettura del sistema

Il progetto utilizza:

### 1. **Analisi audio classica**
- RMS
- BPM
- Key (chroma)
- Spettro medio
- Bande energetiche

### 2. **Analisi avanzata**
- LUFS (pyloudnorm)
- LRA
- Crest Factor
- Transient Density
- Bande fini (sub / air / ecc.)

### 3. **RAG (Retrieval-Augmented Generation)**
La knowledge base è composta da file `.md` organizzati per:
- genere  
- topic → mix, harmony, creative  

Vengono caricati in ChromaDB tramite embedding generati con `ollama`.

### 4. **Multi-Agent System**
Gli agenti sono:
- Mix Engineer
- Music Theory
- Creative Producer
- Orchestrator

Ogni agente usa:
- Contesto numerico dell’audio
- Contesto RAG  
- Prompt specializzato

---

## 🔄 Flusso dati interno
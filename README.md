# 🎧 AI Music Analyzer

> Multi-agent audio analysis with local LLMs, RAG, and a Streamlit UI.

**AI Music Analyzer** is an interactive tool that helps music producers analyze and improve their tracks using:

- Digital Signal Processing (DSP) feature extraction  
- A multi-agent LLM workflow (via **Ollama**)  
- Retrieval-Augmented Generation (**RAG**, via **ChromaDB**)  
- A browser-based UI built with **Streamlit**

Upload an audio file, select a segment, and the system will:

- Extract audio features (BPM, key, RMS, spectral energy balance)
- Automatically estimate the genre
- Query a genre-aware knowledge base (Markdown + embeddings + ChromaDB)
- Run multiple AI agents (Mix, Harmony, Creative, Orchestrator)
- Return a structured, practical action plan for your track

---

## ✨ Key Features

- 🎚 **Audio analysis**
  - BPM estimation
  - Key / tonal center detection
  - RMS / loudness
  - Spectral energy distribution across sub / bass / low-mid / high-mid / highs

- 🧬 **Genre estimation**
  - Heuristic genre detection based on BPM + spectral shape  
  - Supports typical electronic genres (Progressive House, Melodic Techno, Future Bass, Trance, Hardstyle, Dubstep, DnB, etc.)

- 🤖 **Multi-agent LLM system (via Ollama)**
  - **Mix Engineer Agent** – EQ, compression, stereo & loudness advice  
  - **Music Theory Agent** – chords, harmonic functions, genre-appropriate progressions  
  - **Creative Producer Agent** – hooks, melodic ideas, bass patterns, plus a structured `[MELODY_MIDI]` block  
  - **Orchestrator Agent** – merges everything into a prioritized TODO list

- 📚 **RAG (Retrieval-Augmented Generation)**
  - Markdown files in `kb/` store genre- and topic-specific guidelines:
    - `mix_progressive_house.md`
    - `harmony_melodic_techno.md`
    - `creative_future_bass.md`
    - etc.
  - `build_kb_embeddings.py` builds a persistent **ChromaDB** collection (`music_kb`)
  - Each agent can query the KB by topic (`mix`, `harmony`, `creative`) and genre

- 🖥 **Streamlit UI**
  - Upload audio (WAV/MP3/AIFF/FLAC)
  - Visualize waveform (full + selected segment)
  - Select a time interval with a slider
  - Analyze only the selected segment
  - Display per-agent outputs + final orchestrated plan

- 🧱 **Fully local**
  - No external APIs
  - Uses **Ollama** (with `mistral`) for all LLM calls and embeddings

---

## 🗂 Project Structure

```txt
ai_music_analyzer/
│
├── ai_analyzer_backend.py       # DSP analysis, genre estimation, RAG, multi-agent logic
├── ai_analyzer_gui.py           # Streamlit UI (upload, waveform, segment selection)
├── build_kb_embeddings.py       # Script to build ChromaDB collection from kb/*.md
├── kb/                          # Markdown knowledge base (mixing, harmony, creative, per genre)
├── chroma_db/                   # ChromaDB persistent store (generated)
├── requirements.txt             # Python dependencies
├── INSTALL.md                   # Detailed installation & setup guide
├── README.md                    # Project overview (this file)
└── .gitignore                   # Ignore venv, audio files, ChromaDB, etc.

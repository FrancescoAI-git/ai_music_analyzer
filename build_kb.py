"""
build_kb.py - versione super verbosa per debug
----------------------------------------------
- Legge i file .md nella cartella 'kb/'
- Calcola embedding con Ollama
- Crea/ricrea la collection 'music_kb' in 'chroma_db'
"""

import os
import glob
import chromadb
import ollama

KB_DIR = "kb"                 # cartella con i .md
CHROMA_DB_PATH = "chroma_db"  # deve combaciare con il backend
KB_COLLECTION_NAME = "music_kb"
OLLAMA_EMBED_MODEL = "mistral"


def parse_filename_to_metadata(filename):
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)
    parts = name.split("_")

    topic = parts[0] if len(parts) > 0 else "generic"
    genre = "_".join(parts[1:]) if len(parts) > 1 else "all"

    return {"topic": topic, "genre": genre}


def build_kb():
    print("🔥 build_kb avviato")
    print(f"📂 Cartella KB_DIR: {os.path.abspath(KB_DIR)}")

    # 1) Controllo esistenza cartella kb
    if not os.path.isdir(KB_DIR):
        print(f"⚠️ La cartella '{KB_DIR}' non esiste. Creala e metti dentro i .md.")
        return

    pattern = os.path.join(KB_DIR, "*.md")
    md_files = glob.glob(pattern)
    print(f"🔎 Pattern di ricerca: {pattern}")
    print(f"📚 File .md trovati: {len(md_files)}")

    if not md_files:
        print(f"⚠️ Nessun file .md trovato in '{KB_DIR}'. Nulla da indicizzare.")
        return

    all_documents = []
    all_metadatas = []
    all_ids = []
    all_embeddings = []

    for idx, filepath in enumerate(md_files):
        print(f"\n➡️ [{idx+1}/{len(md_files)}] File: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            print(f"  ❌ Errore leggendo il file: {e}")
            continue

        if not text.strip():
            print("  ⚠️ File vuoto, salto.")
            continue

        meta = parse_filename_to_metadata(filepath)
        meta["filename"] = os.path.basename(filepath)
        print(f"  🏷  Metadati: {meta}")

        # Calcolo embedding
        try:
            print("  🧠 Calcolo embedding con Ollama...")
            emb_res = ollama.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
            embedding = emb_res["embedding"]
            print(f"  ✅ Embedding calcolato, dimensione: {len(embedding)}")
        except Exception as e:
            print(f"  ❌ Errore calcolando embedding con Ollama: {e}")
            continue

        doc_id = f"kb_{idx}"
        all_documents.append(text)
        all_metadatas.append(meta)
        all_ids.append(doc_id)
        all_embeddings.append(embedding)

    if not all_documents:
        print("⚠️ Nessun documento valido da indicizzare (forse tutti errori/embedding falliti).")
        return

    print("\n💾 Connessione a Chroma...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    print("📋 Collezioni esistenti prima:", [c.name for c in client.list_collections()])

    existing_names = [c.name for c in client.list_collections()]
    if KB_COLLECTION_NAME in existing_names:
        print(f"♻️ Collection '{KB_COLLECTION_NAME}' esiste già, la elimino...")
        client.delete_collection(name=KB_COLLECTION_NAME)

    print(f"📦 Creo nuova collection '{KB_COLLECTION_NAME}'...")
    collection = client.create_collection(name=KB_COLLECTION_NAME)

    print(f"📥 Aggiungo {len(all_documents)} documenti alla collection...")
    collection.add(
        ids=all_ids,
        documents=all_documents,
        metadatas=all_metadatas,
        embeddings=all_embeddings
    )

    print("✅ Knowledge base costruita con successo!")
    print("📋 Collezioni esistenti dopo:", [c.name for c in client.list_collections()])
    print(f"   Collection: {KB_COLLECTION_NAME}")
    print(f"   DB path: {os.path.abspath(CHROMA_DB_PATH)}")


if __name__ == "__main__":
    build_kb()
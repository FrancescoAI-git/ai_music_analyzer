🚀 Quick Start

1. Install Python & Ollama
	•	Python 3.10+ (3.11 recommended)
	•	Install Ollama: https://ollama.com/download

ollama pull mistral

2. Clone the Repository
    git clone https://github.com/FrancescoAI-git/ai_analyzer.git
    cd ai_music_analyzer

3. Create and Activate Virtual Environment
macOS/Linux:
    python3 -m venv venv
    source venv/bin/activate
Windows:
    python -m venv venv
    venv\Scripts\activate

4. Install Dependencies
    pip install -r requirements.txt

5. Build the knowledge base
    python build_kb.py

6. Start the Backend Server (Python):
	
	uvicorn backend_server:app --reload --port 8000

7. Start the UI Server (Node.js): First, build the CSS (if you made changes):

	npm run build:css

Then start the server:
npm start
(Or node server.js)

Open in Browser: Go to http://localhost:3000


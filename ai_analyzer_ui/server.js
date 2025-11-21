// Importa il framework Express per creare il server HTTP
const express = require("express");

// Crea un'applicazione Express
const app = express();

// Imposta la porta su cui il server dovrà ascoltare (usa 3000 o variabile d'ambiente)
const PORT = process.env.PORT || 3000;

// Indica a Express di servire i file statici dalla cartella "public"
app.use(express.static("public"));

// Definisce una route base "/" che restituisce il file index.html
app.get("/", (req, res) => {
  // Invia il file index.html come risposta
  res.sendFile(__dirname + "/public/index.html");
});

// Avvia il server e ascolta sulla porta indicata
app.listen(PORT, () => {
  // Stampa in console un messaggio per sapere che il server è attivo
  console.log(`🚀 Server avviato su http://localhost:${PORT}`);
});
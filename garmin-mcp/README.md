# Garmin MCP – i tuoi dati Garmin dentro Claude

Server MCP che dà a Claude accesso **in sola lettura** ai tuoi dati Garmin Connect
tramite la **Garmin Personal API** ufficiale (client Python di Garmin
[`connect-personal-api-python`](https://github.com/garmin/connect-personal-api-python)).

Strumenti disponibili: profilo, zone FC, età fitness, ricerca e dettaglio attività,
riepilogo giornaliero, passi, stress, Body Battery, idratazione, sonno (notte e
intervallo), HRV (notte e intervallo), frequenza cardiaca, SpO2, peso, diario
alimentare e una chiamata GET generica (`garmin_get`) per gli altri endpoint.

La chiave **non** sta nel repository: il server la legge da un file privato sul Mac.

---

## 1. Installazione sul Mac (una volta sola)

Apri **Terminale** ed esegui:

```bash
# 1) uv (gestisce Python e dipendenze in automatico)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env   # oppure chiudi e riapri il Terminale

# 2) scarica il repository
git clone https://github.com/mixpix83/MITDT.git ~/MITDT

# 3) salva la chiave Personal API in un file leggibile solo da te
mkdir -p ~/.config/garmin
(umask 077; read -rs "K?Incolla la chiave Garmin e premi Invio: "; echo; \
  printf '%s' "$K" > ~/.config/garmin/connect-personal-api-key)

# verifica (non mostra la chiave): deve essere -rw------- e dimensione > 0
ls -l ~/.config/garmin/connect-personal-api-key
```

Il comando è per **zsh**, il Terminale predefinito del Mac. In bash usa invece
`read -rsp "Incolla la chiave…: " K`.

La chiave non viene mostrata a schermo né salvata nella cronologia del terminale.

## 2. Usarlo con Claude Code (anche da iPhone/iPad)

```bash
cd ~/MITDT
claude
```

Claude Code trova `.mcp.json` e chiede di approvare il server **garmin**: accetta.
Con `/mcp` verifichi che sia connesso. Prova: *"com'è andato il mio sonno questa settimana?"*

**Da iPhone/iPad:** sul Mac, nella cartella `~/MITDT`, avvia

```bash
claude remote-control
```

(oppure attiva Remote Control dall'app desktop: Impostazioni → Claude Code → Remote Control).
La sessione compare nell'app Claude sul telefono, sezione **Code**: scrivi da lì,
gira sul Mac e usa il server Garmin. Il Mac deve restare acceso e non in stop.

## 3. Usarlo nella chat dell'app desktop Claude (facoltativo)

App Claude → **Impostazioni → Sviluppatore → Modifica configurazione** e aggiungi
(sostituisci `TUONOME` con il tuo utente Mac; `which uv` nel Terminale ti dà il percorso di uv):

```json
{
  "mcpServers": {
    "garmin": {
      "command": "/Users/TUONOME/.local/bin/uv",
      "args": ["run", "--script", "/Users/TUONOME/MITDT/garmin-mcp/server.py"]
    }
  }
}
```

Riavvia l'app. Il percorso completo di `uv` serve perché l'app desktop non legge il PATH del Terminale.

Nota: la chat su iPhone/web **non** vede i server installati sul Mac; da telefono usa
Claude Code con Remote Control (punto 2).

## Manutenzione

- La chiave scade (30 giorni – 1 anno, a tua scelta). Garmin ti avvisa via email una
  settimana prima: crea una nuova chiave su
  [Garmin Connect → Personal API](https://connect.garmin.com/app/settings/personalApiToken)
  e ripeti il comando del punto 1.3.
- Il token di accesso (24 h) viene rinnovato da solo e messo in cache in
  `~/.config/garmin/connect-personal-api-bearer-token.json`.
- Per revocare tutto: elimina la chiave su Garmin Connect.

## Prova veloce senza Claude

```bash
cd ~/MITDT/garmin-mcp
uvx --from garmin-connect-personal-api-python gc-personal profile-settings
```

Se stampa il tuo profilo in JSON, la chiave funziona.

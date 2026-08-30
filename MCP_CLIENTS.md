# MCP-Server in Claude & ChatGPT verwenden

Dieses Repo enthält einen MCP-Server (stdio, 12 Tools) für den aDISWeb-OPAC.
Diese Anleitung erklärt, wie du ihn in **Claude** und **ChatGPT** einrichtest.

Voraussetzung: das Repo ist installiert (siehe README) und der Server startet:

```bash
cd /opt/data/adisweb-client
.venv/bin/python -m adisweb.mcp_server
```

Der Server läuft über **stdio** — er wird von deinem MCP-Client als
Subprozess gestartet. Wichtig ist daher der **absolute Pfad** zum Python
deiner venv (hier `/opt/data/adisweb-client/.venv/bin/python`).

---

## 1. Claude Desktop

### 1.1 Konfigurationsdatei finden

| Betriebssystem | Pfad |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

### 1.2 Server eintragen

Öffne die Datei und füge `adisweb` unter `mcpServers` hinzu
(Datei anlegen, falls sie nicht existiert):

```json
{
  "mcpServers": {
    "adisweb": {
      "command": "/opt/data/adisweb-client/.venv/bin/python",
      "args": ["-m", "adisweb.mcp_server"]
    }
  }
}
```

> **Pfad anpassen:** Ersetze `/opt/data/adisweb-client` durch den Pfad, wo
> das Repo auf deinem Rechner liegt (z.B. `C:\repo\adisweb-client` unter
> Windows — dort mit doppelten Backslashes oder vorwärts Slashes).

### 1.3 Claude Desktop neu starten

Claude Desktop komplett beenden und neu öffnen. Das MCP-Symbol (Steckdose)
unten links sollte `adisweb` zeigen. Klicke es an, um die Tools zu sehen und
zu testen — z.B. `list_libraries` oder `search`.

**Typische Fehler:**

- **`command not found` / Server startet nicht:** Prüfe, dass der Pfad zur
  venv-Python stimmt und die venv existiert: `ls /opt/data/adisweb-client/.venv/bin/python`
- **Tools nicht sichtbar:** In Claude Desktop auf das MCP-Symbol klicken →
  „Edit" → Server neu verbinden, oder Claude komplett neu starten.

---

## 2. Claude Code (CLI)

Falls du [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
nutzt, füge den Server mit einem Befehl hinzu:

```bash
claude mcp add adisweb -- /opt/data/adisweb-client/.venv/bin/python -m adisweb.mcp_server
```

Damit ist `adisweb` für deine Projekte verfügbar. Prüfen:

```bash
claude mcp list
```

Innerhalb einer Claude-Code-Session kannst du die Tools direkt nutzen, z.B.:

> „Suche im VÖBB-Katalog nach ‚One Piece 86' und zeige die Verfügbarkeit in
> der ZLB."

Die Tools heißen dann `mcp__adisweb__search` etc. Für Konto-Funktionen
(`get_loans`, `get_orders`, `reserve`) musst du deine Ausweisnummer und
Passwort als Argumente mitgeben — oder du fragst den User danach.

---

## 3. ChatGPT

### 3.1 Wichtig: Einschränkung

**ChatGPT kann keine lokalen stdio-MCP-Server starten.** ChatGPT (Plus/Pro/
Team/Enterprise) unterstützt MCP nur über **Remote MCP-Server** — also einen
HTTPS-Endpunkt mit OAuth-Authentifizierung (z.B. über die
„Connectors"-Funktion / Workflows). Ein lokaler Server wie dieser muss dafür
öffentlich erreichbar gemacht werden.

### 3.2 Option A: Remote-MCP-Server hosten (empfohlen fürs Testen)

Du kannst den stdio-Server mit einem Bridge-Tool als Remote-MCP-Server
exponieren, z.B. mit [`supergateway`](https://github.com/supercorp-ai/supergateway)
(stdio → SSE/HTTP) oder `mcp-proxy`:

```bash
# Beispiel mit supergateway (npm):
npx -y supergateway \
  --stdio "/opt/data/adisweb-client/.venv/bin/python -m adisweb.mcp_server" \
  --port 8000
```

Dann den Endpunkt hinter einen HTTPS-Reverse-Proxy legen (z.B. Caddy/nginx
mit TLS). Den öffentlichen Endpunkt kannst du in ChatGPT unter
**Einstellungen → Connectors (Beta) → Add MCP server** eintragen:

```
URL:  https://dein-server.example.com/sse
Auth: OAuth (vom Proxy bereitgestellt) oder API-Key
```

> **Sicherheitshinweis:** Der Server erlaubt Konto-Operationen
> (Bestellungen!). Exponiere ihn **nur** mit Authentifizierung und nur, wenn
> du die Risiken kennst. Für den privaten Gebrauch ist ein VPN/Tunnel mit
> Zugriffsschutz die bessere Wahl.

### 3.3 Option B: Ohne MCP — direkt fragen

Falls du keinen Remote-Server betreiben willst, kannst du ChatGPT die
README-/API-Informationen geben und die Python-Aufrufe manuell ausführen
lassen — oder du nutzt Claude (Desktop/Code), das lokale stdio-Server
nativ unterstützt.

---

## 4. Beispiel-Dialoge für den Test

Nach erfolgreicher Einrichtung kannst du z.B. fragen:

**Suche & Verfügbarkeit:**
> „Nutze `mcp__adisweb__search_availability` mit query=‚One Piece 86' und
> branch_filter=‚ZLB' und zeige mir die Kopien mit Standort, Signatur und
> Status."

**Ausleihen anzeigen (Konto):**
> „Rufe `mcp__adisweb__get_loans` auf und liste die Titel mit
> Rückgabedatum."

**Bestellungen anzeigen:**
> „Zeige mir meine Bestellwünsche und Magazin-Bestellungen mit
> `mcp__adisweb__get_orders`."

**Bestellung aufgeben (Vorsicht, kostenpflichtig!):**
> „Prüfe mit `reserve` für One Piece 87, Ausgabeort
> ‚Friedrichshain-Kreuzberg: Familienbibliothek Else Ury', express=True,
> confirm=False — zeige mir die Kosten, bevor wir bestellen."

---

## Sicherheit & Datenschutz

- **Credentials:** Ausweisnummer/Passwort werden als Tool-Argumente
  übergeben — im Klartext an den MCP-Client. Nutze den Server nur auf
  Geräten/Servern, denen du vertraust.
- **Kostenpflichtige Bestellungen:** `reserve` bestellt standardmäßig
  **nichts** (`confirm=False` gibt nur die Kosten zurück). Erst
  `confirm=True` löst eine Bestellung aus.
- **Getestet:** Konto-/Bestell-Funktionen sind nur für die **VÖBB (Berlin)**
  live verifiziert (siehe README).

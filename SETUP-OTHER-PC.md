# Run Fair Share on another iRacing PC

## First-time setup

1. Extract the entire ZIP to a normal folder. Do not run it from inside the ZIP.
2. Open the `connector` folder.
3. Double-click `setup-windows.bat` and approve Windows prompts.
4. When setup finishes, close its window.
5. Start iRacing and enter an active session.
6. Double-click `start-connector.bat`.

The first connector launch creates its private Python environment and may take
a minute. Keep both terminal windows open during the race.

## Local dashboard

The connector opens `http://127.0.0.1:8080`. Enter a race code and click
**Join shared race**. Press **Start** when the race begins.

Driver names in Fair Share should exactly match their iRacing names.

## Teammates and GitHub Pages

The **Fair Share Public Tunnel** window displays an address like:

`https://three-random-words.trycloudflare.com`

Teammates open:

`https://wingmotorsport.github.io/Fair-Share-Calculator/`

Under **Server WebSocket**, everyone enters the tunnel address in this form:

`wss://three-random-words.trycloudflare.com/ws`

Everyone must use the same race code. Use a hard-to-guess race code because the
Quick Tunnel is public. The tunnel address changes whenever it restarts.

## What must remain running

- iRacing in an active session.
- The Fair Share connector window.
- The Fair Share Public Tunnel window.
- The PC must remain awake and connected to the internet.

The SQLite race database is created automatically at
`connector/fair_share.db`. It is intentionally not included in the ZIP.


# Produce Order System

This is a dependency-free Python ordering app for produce customers.

## What it does

- Customers place orders without seeing prices.
- Orders are saved immediately for the warehouse.
- A Windows print listener polls the server and prints a full-size ticket to an HP printer as soon as the order is placed.
- Pricing stays offline and the invoice is delivered later.

## Run the web app

```bash
python3 app.py
```

Open `http://127.0.0.1:8000`.

## Run the Windows print listener

On the warehouse Windows computer:

1. Copy this project to the machine.
2. Confirm the HP printer name in Windows.
3. Run PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows-print-listener.ps1 -ServerUrl "http://YOUR-SERVER-IP:8000" -PrinterName "YOUR HP PRINTER NAME"
```

Keep that PowerShell window open. It checks for new orders every 2 seconds and prints each ticket once.

## Files

- `app.py`: web server and print queue API
- `data/catalog.json`: produce catalog based on the sheet you provided
- `static/index.html`: customer ordering page
- `static/app.js`: ordering UI
- `windows-print-listener.ps1`: Windows auto-print agent

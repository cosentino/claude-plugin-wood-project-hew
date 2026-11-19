# wood-project-hew

Plugin di Claude Code per progettare mobili in legno con [Hew](https://hew3d.com): modello 3D scritto come codice,
quote attivabili, pagina web 3D navigabile anche da telefono, link per aprire il modello in app.hew3d.com,
distinta di taglio ottimizzata su pannelli standard e PDF da dare al rivenditore.

- `skills/wood-project-hew/` — la skill (metodo di lavoro, esempio completo, note tecniche su Hew)
- `scripts/hewlib.py` — libreria per descrivere il modello (`modello.py` di ogni progetto)
- `scripts/hew.py` — comandi: costruisci, foto, apri, ricarica, condividi, pdf, pagina, mcp
- `scripts/taglio.py` — ottimizzazione a ghigliottina (tagli passanti), CSV, schemi SVG, pagina A4
- `templates/viewer.html` — pagina web 3D (three.js)
- `.mcp.json` — server MCP `hew` e `hew-live`: avvia l'hew-cli installato con Hew (nessuna copia)

Requisiti: Hew installato (hew-cli), Python 3, Node (per il link al telefono), Chrome o Edge (per il PDF).

## Installazione

Da GitHub:

```bash
claude plugin marketplace add cosentino/claude-plugin-wood-project-hew
claude plugin install wood-project-hew@falegnameria-locale
```

Da una copia locale del repository:

```bash
claude plugin marketplace add ~/progetti/wood-project-hew
claude plugin install wood-project-hew@falegnameria-locale
```

Poi riavvia Claude Code. Dopo una modifica: alza `version` in `.claude-plugin/plugin.json` e lancia
`claude plugin update wood-project-hew@falegnameria-locale`.

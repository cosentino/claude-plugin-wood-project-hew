# hew-woodworking

Plugin di Claude Code per progettare mobili in legno con [Hew](https://hew3d.com): modello 3D scritto come codice,
quote attivabili, pagina web 3D navigabile anche da telefono, link per aprire il modello in app.hew3d.com,
distinta di taglio ottimizzata su pannelli standard e PDF da dare al rivenditore.

- `skills/designing-furniture-in-hew/` — la skill (metodo di lavoro, esempio completo, note tecniche su Hew)
- `scripts/hewlib.py` — libreria per descrivere il modello (`modello.py` di ogni progetto)
- `scripts/hew.py` — comandi: costruisci, foto, apri, ricarica, condividi, pdf, pagina, mcp
- `scripts/taglio.py` — ottimizzazione a ghigliottina (tagli passanti), CSV, schemi SVG, pagina A4
- `templates/viewer.html` — pagina web 3D (three.js)
- `.mcp.json` — server MCP `hew` e `hew-live`: avvia l'hew-cli installato con Hew (nessuna copia)

Requisiti: Hew installato (hew-cli), Python 3, Node (per il link al telefono), Chrome o Edge (per il PDF).

## Installazione

```bash
claude plugin marketplace add cosentino/claude-plugins
claude plugin install hew-woodworking@cosentino
```

Poi riavvia Claude Code. Per lo sviluppo, da una copia locale del repository:
`claude plugin marketplace add ~/progetti/claude-plugins`. Dopo una modifica alza `version` in
`.claude-plugin/plugin.json` (e nella voce del catalogo) e lancia `claude plugin update hew-woodworking@cosentino`.

## Licenza

MIT, vedi [LICENSE](LICENSE). Hew è un progetto separato (AGPL-3.0): il plugin avvia l'`hew-cli` installato e non ne include il codice.

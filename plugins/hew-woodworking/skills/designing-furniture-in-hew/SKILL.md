---
name: designing-furniture-in-hew
description: Use when the user asks to create, recreate from drawings, modify or price a wood furniture/woodworking project in 3D with Hew (mobile, carrello, mensola, letto, armadio, scaffale), to see it on the phone or in a rotatable web page, to add dimensions (quote), or to get a cutting list (distinta di taglio) optimized on standard plywood sheets (multistrato, compensato) and a printable PDF for the panel seller.
---

# Progetto in legno con Hew

## Principio

Il modello è codice: `modello.py` descrive pezzi, quote e pannelli con la libreria `hewlib`.
Tutto il resto (file Hew con quote, copia SketchUp 2017, pagina web 3D, distinta ottimizzata, PDF)
si rigenera con un comando. **Ogni modifica permanente va in `modello.py`**: modifiche fatte a mano
nell'app o con gli strumenti MCP vengono cancellate alla prossima rigenerazione.

`$PLUGIN` qui sotto è la cartella del plugin (quella che contiene `scripts/` e `templates/`, due livelli sopra questo file).

## Comandi (dalla cartella del progetto)

| Comando | Cosa fa |
|---|---|
| `python3 $PLUGIN/scripts/hew.py costruisci` | modello.py → `<cartella>.hew` (con quote) + `.skp` 2017 + `build/modello.glb` + `distinta-taglio.csv/.pdf` + `build/pagina.html` |
| `python3 $PLUGIN/scripts/hew.py foto iso build/iso.png` | render del modello da guardare con Read (viste: iso front back left right top). Non disegna le quote |
| `python3 $PLUGIN/scripts/hew.py apri` | apre il .hew nell'app Hew sul PC (la avvia se serve) |
| `python3 $PLUGIN/scripts/hew.py ricarica` | dopo una rigenerazione, aggiorna la finestra già aperta in Hew |
| `python3 $PLUGIN/scripts/hew.py condividi` | link `app.hew3d.com/#recv=…` per aprire il modello dal telefono (cifrato, temporaneo) |

## Nuovo progetto

1. Crea `~/progetti/<nome>/` con `riferimenti/` (PDF, schizzi, foto ricevuti) e copia
   [esempio-carrello.py](esempio-carrello.py) come `modello.py`: è un progetto completo da adattare.
2. Prima di scrivere il modello chiedi (o conferma) ciò che decide la distinta: **formato dei pannelli**
   (2500×1250 è comune dai rivenditori; Leroy Merlin vende 2500×1220), **spessori**, **essenza**, **lama**
   (default 3 mm). Misure mancanti nei riferimenti: deducile, scrivile in `note=` di `p.taglio(...)` e dillo.
3. `costruisci`, poi guarda il risultato (`foto` + Read) e confrontalo con i riferimenti.
4. Pubblica `build/pagina.html` con lo strumento Artifact; agli aggiornamenti ripubblica **lo stesso percorso**
   così il link resta uguale. Per una sezione in più (preventivo, ipotesi) crea `sezioni.html` nel progetto:
   viene inserita in fondo alla pagina (usa le classi `quote-cost`, `tbl`, `notes`, `mm` del template).
5. Se l'utente usa Hew sul PC: `apri` la prima volta, `ricarica` dopo ogni rigenerazione.
6. Il PDF per il rivenditore è `distinta-taglio.pdf`: mandalo con SendUserFile.

## Modifica di un progetto esistente

Leggi `modello.py`, cambia le costanti o i pezzi, `costruisci`, controlla l'output
(numero oggetti, pannelli per spessore, avanzi), `foto`, poi `ricarica` e ripubblica la pagina.
Se aveva un link per il telefono, rigeneralo con `condividi`: il vecchio mostra la versione vecchia.

## Scrivere modello.py

```python
from hewlib import Progetto
p = Progetto("Mensola", sottotitolo="Soggiorno · Hew", descrizione="Mensola a muro con due ripiani.")
M18 = p.materiale("Multistrato betulla 18 mm", (222, 196, 140), spessore=18)   # da tagliare
FERRO = p.materiale("Staffe", (60, 60, 65))                                   # non entra in distinta
with p.gruppo("Struttura", esploso=(0, -200, 0)):     # ogni pezzo sta in un gruppo
    p.box("Fianco sx", M18, (0, 0, 0), (18, 250, 600), codice="F1", voce="Fianco")
    p.box("Fianco dx", M18, (782, 0, 0), (800, 250, 600), codice="F2", voce="Fianco")
    p.box("Ripiano", M18, (18, 0, 300), (782, 250, 318), codice="R1", nota="bordo frontale bordato")
p.quota("Ingombri", (0, 0, 0), (800, 0, 0), (0, 0, 1), (0, -120, 0), arrotonda=True)
p.taglio(pannelli={18: [(2500, 1250), (1250, 1250)]}, lama=3)
p.salva()
```

- **Assi e unità:** mm; X lunghezza, Y profondità (0 = fronte, cresce verso il retro), Z alto (0 = pavimento).
- **`box(nome, mat, a, b)`**: una delle tre misure deve valere lo spessore del materiale (altrimenti errore).
- **`profilo(nome, mat, piano, quota, spessore, punti)`**: sagome (smussi, trapezi) su piano `"yz"`/`"xz"`/`"xy"`,
  estruse lungo l'asse mancante. La distinta usa il rettangolo d'ingombro e il PDF dice al rivenditore di tagliare il rettangolo.
  Per un pannello **inclinato** (parallelogramma estruso per la sua larghezza) passa `taglio=(lunghezza, larghezza)`.
- **`cilindro(...)`**: ruote, tondini (mai in un materiale da pannello).
- **Distinta:** ogni pezzo in un materiale con `spessore=` vuole un `codice` univoco; `voce` uguale raggruppa i gemelli;
  `venatura=True` vieta la rotazione sul pannello. Materiali diversi solo per colore ma tagliati dallo stesso pannello:
  `p.materiale("Telaio", colore, spessore=12, pannello="Multistrato 12 mm")`.
- **Quote:** `p.quota(tag, a, b, normale, offset)`: `normale` è l'asse perpendicolare al piano della quota,
  `offset` sposta la linea di misura nel piano. Ogni `tag` diventa in Hew il tag "Quote - <tag>" (attivabile dal pannello Tag)
  e nella pagina web un pulsante. Usa due tag: "Ingombri" e "Dettagli".
- **`p.taglio(pannelli={spessore: [formato standard, formati più piccoli...]}, lama, rifilo, note)`**: il secondo formato
  (es. mezzo pannello) si usa per l'ultimo pannello se ci sta.
- `p.scena(nome, occhio, bersaglio)` aggiunge scene a Hew (punti in mm).

## Strumenti MCP `hew` e `hew-live`

`hew` lavora su un documento solo tuo, `hew-live` sulla finestra aperta dall'utente. Usali per **ispezionare**
(`hew_describe_scene`, `hew_snapshot` per vedere il modello, `hew_query` per misurare) o per una prova veloce;
poi riporta in `modello.py` ciò che va tenuto. `hew_capabilities` elenca i comandi con i parametri esatti.

## Errori comuni

| Sintomo | Causa e rimedio |
|---|---|
| `nessuna misura … vale lo spessore` | il box non ha una misura uguale allo spessore del materiale: controlla coordinate o materiale |
| `i pezzi da tagliare vogliono un codice` | aggiungi `codice=` (es. "S1") |
| `alcuni pezzi non stanno nel formato` | pezzo più grande del pannello: dividilo nel modello o usa un formato più grande |
| L'utente non vede le modifiche in Hew | `ricarica` (Hew rifiuta "Revert" su un documento senza modifiche: lo script lo aggira) |
| Quote invisibili nello snapshot | lo snapshot non disegna le quote: controllale nella pagina web o nell'app |
| Modifiche fatte nell'app sparite | la rigenerazione riscrive il .hew: le modifiche vanno in modello.py |

Dettagli del protocollo Hew, formato delle quote nel .hew e link per il telefono: [reference/hew.md](reference/hew.md).

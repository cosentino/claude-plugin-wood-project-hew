# Hew: note tecniche

Verificate con Hew 1.4.0 (Windows, pilotato da WSL). Servono quando gli script del plugin non bastano.

## hew-cli

- Percorso tipico: `/mnt/c/Users/<utente>/AppData/Local/Programs/Hew/hew-cli.exe`; gli script lo trovano da soli
  o usano `HEW_CLI`. Aggiornando Hew con il suo installer si aggiornano anche CLI e MCP.
- `hew-cli run script.json --out file.hew`: script = array JSON di frame JSON-RPC (o JSONL, **un oggetto per riga**).
  Inizia con `hew.meta.hello {"protocol":1}` e `hew.doc.new`. Il primo rifiuto ferma lo script.
- `hew-cli dispatch <metodo> '<params>' --file f.hew` (i comandi che modificano risalvano il file) oppure `--live [--document doc_2]`.
- `hew.meta.capabilities` elenca tutti i comandi con lo schema dei parametri e i rifiuti possibili.
- Con l'eseguibile Windows i percorsi relativi funzionano (cwd WSL tradotta in UNC); per `hew.doc.open --live`
  serve il percorso Windows (`wslpath -w`).
- `--launch` richiede `HEW_APP` col percorso di `hew.exe` e, da WSL, `WSLENV=HEW_APP`. Il primo `open` con `--launch`
  spesso scade mentre l'app parte: ripetere senza `--launch`.

## Geometria

- Unità **metri**. Piano: `{"origin":[...],"normal":[...],"x_axis":[...]}`; i punti si danno in coordinate 3D sul piano.
- `hew.sketch.draw_rect` / `draw_line` (chiusa) / `draw_circle` con `"detached": true`, poi `hew.solid.extrude`
  `{"region":{"$ref":"<as>#/region_id"},"distance":d}`: estrude lungo la normale del piano e crea un oggetto solido.
- In `hew.doc.transact` ogni comando può avere `"as":"nome"` e i successivi lo citano con `{"$ref":"nome#/campo"}`
  (`object_id` dell'estrusione, `group` di `hew.group.create`).
- Materiali: `hew.material.create` restituisce `mat_0`, `mat_1`… nell'ordine di creazione.
- Esportazioni: `hew.doc.export {"format":"glb"|"stl"|"3mf"|"usdz","path":…}`;
  SketchUp: `hew.doc.save {"copy":true,"path":"x.skp","format":"skp2017","units":"mm"}` (SketchUp Make 2017 lo apre).
- glTF esportato: Y in alto, fronte verso +Z (`x, z, -y` rispetto agli assi del modello); un nodo per oggetto col suo nome, gruppi appiattiti.

## Quote (annotations)

hew-cli non ha comandi per le quote. Vanno nel `manifest.json` dentro lo zip `.hew` (ZIP_STORED, manifest per primo):

```json
"tags": [{"path": ["Quote - Ingombri"], "sid": 83, "hidden": false}],
"annotations": [{"id": 0, "sid": 85, "kind": "linear",
  "a": {"p": [0.0, -0.008, 0.0]}, "b": {"p": [1.2, -0.008, 0.0]},
  "offset": [0.0, -0.15, 0.0], "plane": [0.0, 0.0, 1.0, 0.0], "tags": [["Quote - Ingombri"]]}]
```

`sid` univoci oltre il massimo già presente nel manifest; `plane` = normale + `d` con `n·a = d`.
Il manifest omette le chiavi vuote (`tags`, `annotations`). Hew rilegge e risalva queste quote senza perderle.
`hew.view.snapshot` non le disegna.

## Ricaricare un documento aperto

`hew.doc.revert` rifiuta (`nothing_to_revert`) se il documento non ha modifiche. Per far rileggere il file rigenerato:
`hew.guide.point {"position":[0,0,0]}` (lo sporca) e poi `hew.doc.revert`. `hew-cli documents --live` dà id e titolo delle finestre.

## Link per il telefono ("Open on Phone")

Dal sorgente (github.com/hew3d/hew, `relay_client.rs`, `PhoneShareDialog.tsx`): il .hew viene cifrato AES-256-GCM
con chiave casuale (`[IV 12 byte][cifrato+tag]`), `PUT https://app.hew3d.com/relay/drop` (octet-stream) → `{"token"}`;
link `https://app.hew3d.com/#recv=<token>.<chiave base64url>.<nome>`. La chiave resta nel frammento: il server non legge il
modello. Il deposito scade dopo un tempo limitato. `HEAD /relay/drop/<token>` → 200 se c'è ancora.

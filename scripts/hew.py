#!/usr/bin/env python3
"""Comandi del flusso di lavoro con Hew. Da lanciare nella cartella del progetto.

    python3 hew.py costruisci          modello.py -> .hew con quote, .skp 2017, .glb, distinta, PDF, pagina
    python3 hew.py pagina              solo la pagina web (build/pagina.html)
    python3 hew.py pdf                 solo il PDF della distinta (distinta-taglio.pdf)
    python3 hew.py apri                apre il .hew nell'app Hew (la avvia se serve)
    python3 hew.py ricarica            ricarica nell'app il .hew rigenerato (senza chiudere la finestra)
    python3 hew.py condividi           link per aprire il modello in app.hew3d.com dal telefono
    python3 hew.py foto <vista> <png>  render (iso, front, back, left, right, top) del file .hew
    python3 hew.py mcp [--live]        server MCP di hew-cli (usato dal plugin)

Variabili: HEW_CLI (percorso di hew-cli), HEW_APP (hew.exe per l'avvio), CHROME (per il PDF).
"""
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(QUI)
sys.path.insert(0, QUI)


# --- dove sono le cose ------------------------------------------------------------
def wsl():
    return os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop") or "microsoft" in open("/proc/version").read().lower()


def hew_cli():
    if os.environ.get("HEW_CLI"):
        return os.environ["HEW_CLI"]
    for pat in ["/mnt/c/Users/*/AppData/Local/Programs/Hew/hew-cli.exe",
                "/mnt/c/Program Files/Hew/hew-cli.exe",
                os.path.expanduser("~/.local/bin/hew-cli"), "/usr/local/bin/hew-cli", "/usr/bin/hew-cli"]:
        trovati = sorted(glob.glob(pat))
        if trovati:
            return trovati[0]
    if shutil.which("hew-cli"):
        return shutil.which("hew-cli")
    raise SystemExit("hew-cli non trovato: installa Hew (hew3d.com) o imposta HEW_CLI")


def hew_app(cli):
    if os.environ.get("HEW_APP"):
        return os.environ["HEW_APP"]
    vicino = os.path.join(os.path.dirname(cli), "hew.exe" if cli.endswith(".exe") else "hew")
    return vicino


def percorso_per_hew(path, cli):
    """hew-cli.exe di Windows vuole percorsi Windows per i file aperti nell'app."""
    path = os.path.abspath(path)
    if cli.endswith(".exe") and wsl():
        return subprocess.check_output(["wslpath", "-w", path], text=True).strip()
    return path


def chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for p in ["/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
              "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
              "/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe"]:
        if os.path.exists(p):
            return p
    for n in ["google-chrome", "chromium", "chromium-browser", "microsoft-edge"]:
        if shutil.which(n):
            return shutil.which(n)
    return None


def nome_hew():
    return os.path.basename(os.path.abspath(".")) + ".hew"


def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    out = (r.stdout or "").replace("\r", "")
    err = (r.stderr or "").replace("\r", "")
    if r.returncode != 0:
        raise SystemExit(f"errore da {os.path.basename(args[0])} {' '.join(args[1:3])}:\n{err or out}")
    return out


def dispatch(cli, metodo, params=None, file=None, live=False, documento=None):
    args = [cli, "dispatch", metodo, json.dumps(params or {})]
    if file:
        args += ["--file", file]
    if live:
        args += ["--live"]
        if documento:
            args += ["--document", documento]
    env = dict(os.environ)
    out = run(args, env=env)
    return json.loads(out.strip().splitlines()[-1])


# --- quote nel manifest del .hew ---------------------------------------------------
def scrivi_quote(path, quote):
    """hew-cli non ha comandi per le quote: si scrivono nel manifest (chiave "annotations")."""
    with zipfile.ZipFile(path) as z:
        voci = {i.filename: z.read(i.filename) for i in z.infolist()}
    man = json.loads(voci["manifest.json"])

    def sids(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "sid" and isinstance(v, int):
                    yield v
                yield from sids(v)
        elif isinstance(o, list):
            for v in o:
                yield from sids(v)

    sid = max(sids(man), default=0) + 1
    tag_quote = []
    for q in quote:
        if q["tag"] not in tag_quote:
            tag_quote.append(q["tag"])
    tags = [t for t in man.get("tags", []) if t["path"][0] not in tag_quote]
    for nome in tag_quote:
        tags.append({"path": [nome], "sid": sid, "hidden": False})
        sid += 1
    ann = [a for a in man.get("annotations", []) if not any(t[0] in tag_quote for t in a.get("tags", []))]
    m = lambda v: [round(c / 1000.0, 6) for c in v]  # noqa: E731
    for q in quote:
        d = sum(a * b for a, b in zip(q["n"], m(q["a"])))
        ann.append({"id": len(ann), "sid": sid, "kind": "linear", "a": {"p": m(q["a"])}, "b": {"p": m(q["b"])},
                    "offset": m(q["off"]), "plane": [*map(float, q["n"]), round(d, 6)], "tags": [[q["tag"]]]})
        sid += 1
    man["tags"] = tags
    man["annotations"] = ann
    voci["manifest.json"] = json.dumps(man, indent=2).encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        z.writestr("manifest.json", voci.pop("manifest.json"))
        for nome, dati in voci.items():
            z.writestr(nome, dati)


# --- comandi ---------------------------------------------------------------------
def costruisci():
    if not os.path.exists("modello.py"):
        raise SystemExit("manca modello.py nella cartella corrente")
    cli = hew_cli()
    os.makedirs("build", exist_ok=True)
    env = dict(os.environ, PYTHONPATH=QUI + os.pathsep + os.environ.get("PYTHONPATH", ""))
    print(run([sys.executable, "modello.py"], env=env).strip())
    prog = json.load(open("build/progetto.json"))
    hew = nome_hew()
    out = run([cli, "run", "build/script.json", "--out", hew])
    scena = json.loads(out.strip().splitlines()[-1])["result"]
    attesi = len(prog["pezzi"])
    if scena["document"]["objects"] != attesi:
        raise SystemExit(f"Hew ha {scena['document']['objects']} oggetti, attesi {attesi}")
    if prog["quote"]:
        scrivi_quote(hew, prog["quote"])
    # Hew rilegge il file: verifica che quote e tag siano accettati
    sc = dispatch(cli, "hew.query.scene", file=hew)["result"]
    base = os.path.splitext(hew)[0]
    dispatch(cli, "hew.doc.export", {"format": "glb", "path": "build/modello.glb"}, file=hew)
    skp = dispatch(cli, "hew.doc.save", {"copy": True, "path": base + ".skp", "format": "skp2017", "units": "mm"}, file=hew)
    print(f"{hew}: {sc['document']['objects']} oggetti, {len(prog['gruppi'])} gruppi, {len(prog['quote'])} quote "
          f"({', '.join(t['path'][0] for t in sc.get('tags', []))}); {base}.skp (SketchUp 2017)"
          + (f" — semplificato: {'; '.join(skp['result'].get('simplified', []))}" if skp["result"].get("simplified") else ""))
    import taglio
    if any("codice" in p for p in prog["pezzi"]):
        taglio.main(".")
        pdf()
    pagina()


def pdf():
    src = os.path.abspath("build/distinta-stampa.html")
    if not os.path.exists(src):
        raise SystemExit("manca build/distinta-stampa.html: lancia prima `costruisci`")
    exe = chrome()
    if not exe:
        print("Chrome/Edge non trovato: stampa build/distinta-stampa.html dal browser", file=sys.stderr)
        return
    if exe.endswith(".exe") and wsl():
        tmp_win = run(["cmd.exe", "/c", "echo %TEMP%"], cwd="/mnt/c").strip()
        tmp = subprocess.check_output(["wslpath", "-u", tmp_win], text=True).strip()
        d = os.path.join(tmp, "wood-project-hew")
        os.makedirs(d, exist_ok=True)
        shutil.copy(src, os.path.join(d, "d.html"))
        win = lambda p: subprocess.check_output(["wslpath", "-w", p], text=True).strip()  # noqa: E731
        html_p, pdf_p, pdf_local = win(os.path.join(d, "d.html")), win(os.path.join(d, "d.pdf")), os.path.join(d, "d.pdf")
    else:
        d = tempfile.mkdtemp()
        html_p, pdf_p = src, os.path.join(d, "d.pdf")
        pdf_local = pdf_p
    if os.path.exists(pdf_local):
        os.remove(pdf_local)
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_p}", html_p],
                   capture_output=True, timeout=120)
    if not os.path.exists(pdf_local):
        raise SystemExit("la stampa in PDF non ha prodotto il file")
    shutil.copy(pdf_local, "distinta-taglio.pdf")
    print("distinta-taglio.pdf scritto")


def pagina():
    import html
    import taglio as T
    prog = json.load(open("build/progetto.json"))
    lo, hi = prog["ingombro"]
    tre = lambda p: [p[0] / 1000, p[2] / 1000, -p[1] / 1000]  # noqa: E731  mm (Z su) -> three.js (Y su)
    centro = tre([(lo[i] + hi[i]) / 2 for i in range(3)])
    raggio = 0.55 * sum((hi[i] - lo[i]) ** 2 for i in range(3)) ** 0.5 / 1000
    tags = []
    for q in prog["quote"]:
        if q["tag"] not in tags:
            tags.append(q["tag"])
    cfg = {
        "centro": centro, "raggio": raggio, "pavimento": lo[2] / 1000,
        "gruppi": [{"nome": g["nome"], "pezzi": g["pezzi"], "esploso": tre(g["esploso"])} for g in prog["gruppi"]],
        "quote": [{"tag": q["tag"], "a": q["a"], "b": q["b"], "off": q["off"], "mm": q["mm"], "arrotonda": q.get("arrotonda", False)}
                  for q in prog["quote"]],
    }
    if tags:
        bottoni = "\n".join(
            f'          <button type="button" id="q-{i}" data-quote="{html.escape(t)}" aria-pressed="{"true" if i == 0 else "false"}">'
            f'{html.escape(t.replace("Quote - ", ""))}</button>' for i, t in enumerate(tags))
        quote_ctl = f'      <div class="ctl">\n        <h2>Quote (mm)</h2>\n        <div class="row">\n{bottoni}\n        </div>\n      </div>\n'
    else:
        quote_ctl = ""
    righe = fogli = lede = note_html = ""
    if os.path.exists("build/taglio.json"):
        tg = json.load(open("build/taglio.json"))
        righe = open("build/distinta-righe.html").read()
        fogli = open("build/distinta-fogli.html").read()
        cont = {}
        for f in tg["fogli"]:
            k = (T.num(f["spessore"]), T.num(f["formato"][0]), T.num(f["formato"][1]))
            cont[k] = cont.get(k, 0) + 1
        parti = [f"{n} {'pannello' if n == 1 else 'pannelli'} da {sp} mm {a} × {b}" for (sp, a, b), n in cont.items()]
        lede = (", ".join(parti[:-1]) + " e " + parti[-1] if len(parti) > 1 else parti[0]) + \
            f". Lama da {T.num(tg['lama'])} mm considerata tra un pezzo e l'altro."
        note = prog["taglio"].get("note", [])
        if note:
            note_html = '    <div class="notes-wrap">\n      <h2>Note</h2>\n      <ul class="notes">' + \
                "".join(f"<li>{html.escape(n)}</li>" for n in note) + "</ul>\n    </div>"
    t = open(os.path.join(PLUGIN, "templates", "viewer.html")).read()
    sezioni = open("sezioni.html").read() if os.path.exists("sezioni.html") else ""
    w, d, h = (hi[i] - lo[i] for i in range(3))
    sost = {
        "__TITOLO__": html.escape(prog["titolo"]), "__SOTTOTITOLO__": html.escape(prog.get("sottotitolo") or "Hew"),
        "__DESCRIZIONE__": html.escape(prog.get("descrizione", "")), "__INGOMBRO__": f"{round(w)} × {round(d)} × {round(h)}",
        "__QUOTE_CTL__": quote_ctl, "__TAGLIO_LEDE__": html.escape(lede), "__TAGLIO_NOTE__": note_html,
        "__RIGHE__": righe, "__FOGLI__": fogli, "__SEZIONI__": sezioni,
        "__CONFIG_JSON__": json.dumps(cfg, separators=(",", ":")),
        "__GLB_BASE64__": base64.b64encode(open("build/modello.glb", "rb").read()).decode(),
    }
    for k, v in sost.items():
        t = t.replace(k, v)
    if not os.path.exists("build/taglio.json"):
        i = t.find('  <section class="cutlist"')
        j = t.find("  </section>", i) + len("  </section>")
        t = t[:i] + t[j:]
    open("build/pagina.html", "w").write(t)
    print(f"build/pagina.html scritta ({len(t) // 1024} KB): pubblicala con lo strumento Artifact, sempre da questo percorso")


def documento_live(cli, hew):
    out = run([cli, "documents", "--live"])
    for riga in out.strip().splitlines():
        d = json.loads(riga)
        if d.get("title") == os.path.basename(hew):
            return d["id"]
    return None


def apri():
    cli, hew = hew_cli(), nome_hew()
    env = dict(os.environ, HEW_APP=hew_app(cli))
    if cli.endswith(".exe") and wsl():
        env["WSLENV"] = "HEW_APP" + (":" + os.environ["WSLENV"] if os.environ.get("WSLENV") else "")
    params = json.dumps({"path": percorso_per_hew(hew, cli), "focus": True})
    r = subprocess.run([cli, "dispatch", "hew.doc.open", params, "--live", "--launch"], capture_output=True, text=True,
                       env=env, timeout=150)
    if r.returncode != 0:  # il primo avvio spesso scade prima che l'app sia pronta: riprova senza --launch
        r = subprocess.run([cli, "dispatch", "hew.doc.open", params, "--live"], capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        raise SystemExit((r.stderr or r.stdout).replace("\r", ""))
    doc = json.loads(r.stdout.replace("\r", "").strip().splitlines()[-1])["result"]["document"]
    dispatch(cli, "hew.view.zoom_extents", live=True, documento=doc["id"])
    print(f"aperto in Hew come {doc['id']}")


def ricarica():
    """Hew rifiuta revert su un documento senza modifiche: si aggiunge una guida e poi si annulla tutto."""
    cli, hew = hew_cli(), nome_hew()
    doc = documento_live(cli, hew)
    if not doc:
        return apri()
    dispatch(cli, "hew.guide.point", {"position": [0, 0, 0]}, live=True, documento=doc)
    dispatch(cli, "hew.doc.revert", live=True, documento=doc)
    dispatch(cli, "hew.view.zoom_extents", live=True, documento=doc)
    print(f"ricaricato in Hew ({doc})")


def condividi():
    hew = nome_hew()
    nome = os.path.splitext(hew)[0]
    print(run(["node", os.path.join(QUI, "condividi_telefono.mjs"), hew, nome]).strip())


def foto(vista, png):
    cli = hew_cli()
    dispatch(cli, "hew.view.snapshot", {"view": vista, "width": 1000, "height": 900, "path": png}, file=nome_hew())
    print(png)


def mcp(argv):
    cli = hew_cli()
    os.execv(cli, [cli, "mcp", *argv])


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    cmd, args = sys.argv[1], sys.argv[2:]
    semplici = {"costruisci": costruisci, "pagina": pagina, "pdf": pdf, "apri": apri, "ricarica": ricarica,
                "condividi": condividi}
    if cmd in semplici:
        semplici[cmd]()
    elif cmd == "foto" and len(args) == 2:
        foto(*args)
    elif cmd == "mcp":
        mcp(args)
    else:
        raise SystemExit(f"comando sconosciuto o argomenti mancanti: {' '.join(sys.argv[1:])}\n\n{__doc__}")

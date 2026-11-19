#!/usr/bin/env python3
"""Ottimizzazione del taglio e distinta, a partire da build/progetto.json.

Algoritmo a ghigliottina (ogni taglio attraversa il pezzo da parte a parte, come
su una sezionatrice), con lama e rifilo. Prova molte combinazioni di ordinamento,
criterio di scelta e regola di divisione e tiene la soluzione con meno pannelli e
gli avanzi più grandi. L'ultimo pannello, se ci sta, passa a un formato più piccolo
(es. mezzo pannello).

Uscite (nella cartella del progetto):
    distinta-taglio.csv
    build/taglio.json             disposizione dei pezzi
    build/distinta-righe.html     righe della tabella per la pagina web
    build/distinta-fogli.html     schemi SVG per la pagina web
    build/distinta-stampa.html    pagina A4 per il rivenditore (poi PDF con hew.py pdf)
"""
import csv
import html
import itertools
import json
import os
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hewlib import chiave_spessore  # noqa: E402

EPS = 1e-6


# --- impaccamento a ghigliottina ------------------------------------------------
def _score(fit, fr, w, h):
    lw, lh = fr[2] - w, fr[3] - h
    if fit == "area":
        return (fr[2] * fr[3] - w * h, min(lw, lh))
    if fit == "lato_corto":
        return (min(lw, lh), max(lw, lh))
    return (max(lw, lh), min(lw, lh))  # lato_lungo


def _split(regola, fr, w, h):
    x, y, W, H = fr
    lw, lh = W - w, H - h
    if regola == "orizzontale":
        orizz = True
    elif regola == "verticale":
        orizz = False
    elif regola == "asse_corto":
        orizz = lw <= lh
    elif regola == "asse_lungo":
        orizz = lw > lh
    else:  # area_min: rende più piccolo il rettangolo minore, così il maggiore resta ampio
        orizz = (w * lh) > (lw * h)
    if orizz:  # taglio orizzontale lungo tutta la larghezza del rettangolo libero
        a = (x + w, y, lw, h)
        b = (x, y + h, W, lh)
    else:
        a = (x + w, y, lw, H)
        b = (x, y + h, w, lh)
    return [r for r in (a, b) if r[2] > EPS and r[3] > EPS]


def impacca(pezzi, formato, lama, rifilo, ordine, fit, regola, max_fogli=None):
    """pezzi: [(codice, lunghezza, larghezza, venatura)]. Restituisce [{"liberi", "pezzi"}] o None."""
    W = formato[0] - 2 * rifilo + lama
    H = formato[1] - 2 * rifilo + lama
    fogli = []
    for cod, L, l, ven in ordine(pezzi):
        orient = [(L, l, False)] if ven else [(L, l, False), (l, L, True)]
        migliore = None
        for fi, f in enumerate(fogli):
            for ri, fr in enumerate(f["liberi"]):
                for w, h, rot in orient:
                    W2, H2 = w + lama, h + lama
                    if W2 <= fr[2] + EPS and H2 <= fr[3] + EPS:
                        sc = (fi,) + _score(fit, fr, W2, H2)
                        if migliore is None or sc < migliore[0]:
                            migliore = (sc, fi, ri, w, h, rot)
        if migliore is None:
            if max_fogli is not None and len(fogli) >= max_fogli:
                return None
            fr0 = (0.0, 0.0, W, H)
            ok = [(w, h, rot) for w, h, rot in orient if w + lama <= W + EPS and h + lama <= H + EPS]
            if not ok:
                return None
            fogli.append({"liberi": [fr0], "pezzi": []})
            w, h, rot = min(ok, key=lambda o: _score(fit, fr0, o[0] + lama, o[1] + lama))
            fi, ri = len(fogli) - 1, 0
        else:
            _, fi, ri, w, h, rot = migliore
        f = fogli[fi]
        fr = f["liberi"].pop(ri)
        f["pezzi"].append({"cod": cod, "x": fr[0] + rifilo, "y": fr[1] + rifilo, "w": w, "h": h, "ruotato": rot})
        f["liberi"] += _split(regola, fr, w + lama, h + lama)
    return fogli


ORDINI = {
    "area": lambda ps: sorted(ps, key=lambda p: (-p[1] * p[2], -p[1])),
    "lato_lungo": lambda ps: sorted(ps, key=lambda p: (-p[1], -p[2])),
    "lato_corto": lambda ps: sorted(ps, key=lambda p: (-p[2], -p[1])),
    "perimetro": lambda ps: sorted(ps, key=lambda p: (-(p[1] + p[2]), -p[1])),
}
FIT = ["area", "lato_corto", "lato_lungo"]
REGOLE = ["asse_corto", "asse_lungo", "area_min", "orizzontale", "verticale"]


def _qualita(fogli, formato):
    """Meno fogli; poi l'avanzo più grande dell'ultimo foglio il più ampio possibile."""
    ultimo = fogli[-1]
    avanzo = max((r[2] * r[3] for r in ultimo["liberi"]), default=0)
    return (len(fogli), -avanzo)


def ottimizza(pezzi, formati, lama, rifilo):
    standard = formati[0]
    best = None
    for (no, ordine), fit, regola in itertools.product(ORDINI.items(), FIT, REGOLE):
        fogli = impacca(pezzi, standard, lama, rifilo, ordine, fit, regola)
        if fogli is None:
            continue
        q = _qualita(fogli, standard)
        if best is None or q < best[0]:
            best = (q, fogli, (no, fit, regola))
    if best is None:
        raise SystemExit(f"alcuni pezzi non stanno nel formato {standard}")
    fogli = [{"formato": list(standard), "pezzi": f["pezzi"], "liberi": f["liberi"]} for f in best[1]]
    # ultimo foglio in un formato più piccolo, se ci sta
    ultimo_cod = {p["cod"] for p in fogli[-1]["pezzi"]}
    resto = [p for p in pezzi if p[0] in ultimo_cod]
    for formato in sorted(formati[1:], key=lambda f: f[0] * f[1]):
        prova = None
        for (no, ordine), fit, regola in itertools.product(ORDINI.items(), FIT, REGOLE):
            r = impacca(resto, formato, lama, rifilo, ordine, fit, regola, max_fogli=1)
            if r and (prova is None or _qualita(r, formato) < _qualita(prova, formato)):
                prova = r
        if prova:
            fogli[-1] = {"formato": list(formato), "pezzi": prova[0]["pezzi"], "liberi": prova[0]["liberi"]}
            break
    return fogli, best[2]


def verifica(fogli, lama, rifilo):
    for f in fogli:
        W, H = f["formato"]
        ps = f["pezzi"]
        for p in ps:
            assert p["x"] >= rifilo - EPS and p["y"] >= rifilo - EPS, p
            assert p["x"] + p["w"] <= W - rifilo + EPS and p["y"] + p["h"] <= H - rifilo + EPS, p
        for a, b in itertools.combinations(ps, 2):
            sep_x = a["x"] + a["w"] + lama <= b["x"] + EPS or b["x"] + b["w"] + lama <= a["x"] + EPS
            sep_y = a["y"] + a["h"] + lama <= b["y"] + EPS or b["y"] + b["h"] + lama <= a["y"] + EPS
            assert sep_x or sep_y, (a["cod"], b["cod"])


# --- formattazione -----------------------------------------------------------
def num(v):
    return ("%.1f" % v).rstrip("0").rstrip(".").replace(".", ",")


def righe_distinta(pezzi_prog, dove):
    """Raggruppa i pezzi uguali (stessa voce, misure, spessore, nota)."""
    gruppi = {}
    for p in pezzi_prog:
        k = (p["voce"], p["lunghezza"], p["larghezza"], p["spessore"], p.get("nota", ""))
        gruppi.setdefault(k, []).append(p["codice"])
    out = []
    for (voce, L, l, sp, nota), cods in gruppi.items():
        cod_txt = cods[0] if len(cods) == 1 else (f"{cods[0]}–{cods[-1]}" if len(cods) > 2 else ", ".join(cods))
        out.append({"codici": cods, "cod_txt": cod_txt, "voce": voce, "pz": len(cods), "L": L, "l": l, "sp": sp,
                    "nota": nota, "pannelli": sorted({dove[c] for c in cods})})
    return out


def _sagoma_svg(p, pez, cls):
    x, y, w, h = p["x"], p["y"], p["w"], p["h"]
    pts = []
    for lu, la in pez["sagoma"]:
        if p["ruotato"]:   # lunghezza lungo y
            pts.append((x + la, y + h - lu))
        else:
            pts.append((x + lu, y + h - la))
    return f'<polygon class="{cls}" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>'


def svg_foglio(f, pezzi_by_cod, stampa=False):
    W, H = f["formato"]
    m = 60 if stampa else 20
    out = [f'<svg viewBox="{-m} {-m} {W + 2 * m:.0f} {H + 2 * m:.0f}" class="cut" xmlns="http://www.w3.org/2000/svg"'
           f' role="img" aria-label="Schema di taglio {html.escape(f["nome"])}">']
    out.append(f'<rect class="sheet{"" if stampa else "-bg"}" x="0" y="0" width="{W:.0f}" height="{H:.0f}"/>')
    if stampa:
        out.append(f'<text class="edge" x="{W / 2:.0f}" y="-18">{num(W)}</text>')
        out.append(f'<text class="edge" x="-18" y="{H / 2:.0f}" transform="rotate(-90 -18 {H / 2:.0f})">{num(H)}</text>')
    for p in f["pezzi"]:
        pez = pezzi_by_cod[p["cod"]]
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        if pez.get("sagoma") and not stampa:
            out.append(f'<rect class="pc-box" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/>')
            out.append(_sagoma_svg(p, pez, "pc"))
        else:
            extra = "" if stampa else (" pc8" if pez["spessore"] < 10 else "")
            out.append(f'<rect class="pc{extra}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/>')
        cx, cy = x + w / 2, y + h / 2
        mis = f'{num(pez["lunghezza"])} × {num(pez["larghezza"])}'
        cod = html.escape(p["cod"])
        if w < 140:
            out.append(f'<text class="lab" x="{cx:.1f}" y="{cy:.1f}" transform="rotate(-90 {cx:.1f} {cy:.1f})">'
                       f'<tspan class="cod">{cod}</tspan>  {mis}</text>')
        elif h < 140:
            out.append(f'<text class="lab" x="{cx:.1f}" y="{cy:.1f}"><tspan class="cod">{cod}</tspan>  {mis}</text>')
        elif w < 320:
            yb = y + h - 170 if pez.get("sagoma") and not stampa else cy - 40
            out.append(f'<text class="lab" x="{cx:.1f}" y="{yb:.1f}"><tspan class="cod">{cod}</tspan></text>')
            out.append(f'<text class="lab sm" x="{cx:.1f}" y="{yb + 70:.1f}">{num(pez["lunghezza"])}</text>')
            out.append(f'<text class="lab sm" x="{cx:.1f}" y="{yb + 125:.1f}">× {num(pez["larghezza"])}</text>')
        else:
            out.append(f'<text class="lab" x="{cx:.1f}" y="{cy - 30:.1f}"><tspan class="cod">{cod}</tspan></text>')
            out.append(f'<text class="lab" x="{cx:.1f}" y="{cy + 40:.1f}">{mis}</text>')
    out.append("</svg>")
    return "\n".join(out)


def utilizzo(f, pezzi_by_cod):
    W, H = f["formato"]
    return sum(pezzi_by_cod[p["cod"]]["lunghezza"] * pezzi_by_cod[p["cod"]]["larghezza"] for p in f["pezzi"]) / (W * H)


def avanzo_maggiore(f, lama):
    r = max(f["liberi"], key=lambda r: r[2] * r[3], default=None)
    if not r:
        return None
    return max(0, r[2] - lama), max(0, r[3] - lama)


STAMPA_CSS = """
@page { size: A4; margin: 12mm 12mm 14mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; color: #111; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 2mm; }
h2 { font-size: 12pt; margin: 0 0 2mm; }
.meta { display: grid; grid-template-columns: 1fr 1fr; gap: 1mm 8mm; margin: 3mm 0 4mm; }
.meta div { border-bottom: 0.3pt solid #999; padding: 1mm 0; }
.meta b { display: inline-block; min-width: 24mm; }
.box { border: 0.6pt solid #111; padding: 3mm 4mm; margin-bottom: 4mm; }
.box ul { margin: 1mm 0 0; padding-left: 5mm; }
.box li { margin: 0.6mm 0; }
table { width: 100%; border-collapse: collapse; margin-bottom: 3mm; }
th, td { border: 0.4pt solid #555; padding: 1.2mm 2mm; text-align: left; vertical-align: top; }
th { background: #eee; font-size: 8.5pt; }
td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.c { font-weight: 700; white-space: nowrap; }
td.chk { width: 8mm; }
.foglio { break-inside: avoid; margin-bottom: 6mm; }
.foglio + .foglio { break-before: page; }
.schema svg { height: auto; display: block; }
svg .sheet { fill: #fff; stroke: #111; stroke-width: 5; stroke-dasharray: 22 14; }
svg .pc { fill: #f1e6d2; stroke: #111; stroke-width: 4; }
svg .lab { font-family: Arial, sans-serif; font-size: 50px; text-anchor: middle; dominant-baseline: middle; fill: #111; }
svg .lab.sm { font-size: 44px; }
svg .cod { font-weight: 700; }
svg .edge { font-family: Arial, sans-serif; font-size: 48px; text-anchor: middle; fill: #444; }
footer { margin-top: 3mm; font-size: 8.5pt; color: #444; }
"""


def pagina_stampa(prog, fogli, pezzi_by_cod, lama, rifilo, data):
    W_max = max(f["formato"][0] for f in fogli)
    blocchi = []
    for f in fogli:
        W, H = f["formato"]
        cods = [p["cod"] for p in f["pezzi"]]
        dove = {c: f["nome"] for c in cods}
        righe = righe_distinta([pezzi_by_cod[c] for c in sorted(cods, key=_ordine_codice)], dove)
        tr = []
        for r in righe:
            nota = html.escape(r["nota"])
            if pezzi_by_cod[r["codici"][0]].get("sagoma"):
                nota = (nota + "; " if nota else "") + "tagliare il rettangolo, la sagoma la rifinisco io"
            tr.append(f"<tr><td class='c'>{html.escape(r['cod_txt'])}</td><td>{html.escape(r['voce'])}</td><td class='n'>{r['pz']}</td>"
                      f"<td class='n'>{num(r['L'])}</td><td class='n'>{num(r['l'])}</td><td>{nota}</td><td class='chk'></td></tr>")
        larghezza = 100 * W / W_max
        blocchi.append(f"""
<section class="foglio">
  <h2>{f['nome']} — {f['materiale']}, {num(W)} × {num(H)}</h2>
  <table><thead><tr><th>Cod.</th><th>Pezzo</th><th>Pz</th><th>Lungh.</th><th>Largh.</th><th>Note</th><th>✓</th></tr></thead>
  <tbody>{''.join(tr)}</tbody></table>
  <div class="schema"><div style="width:{larghezza:.1f}%">{svg_foglio(f, pezzi_by_cod, stampa=True)}</div></div>
</section>""")
    materiali = {}
    for f in fogli:
        materiali.setdefault((f["materiale"], tuple(f["formato"])), []).append(f["nome"].replace("Pannello ", ""))
    righe_mat = "".join(
        f"<li>{len(n)} {'pannello' if len(n) == 1 else 'pannelli'} <b>{html.escape(mat)}</b>, formato <b>{num(fm[0])} × {num(fm[1])}</b> "
        f"({'pannello' if len(n) == 1 else 'pannelli'} {', '.join(n)})</li>"
        for (mat, fm), n in materiali.items())
    note = [
        "Misure in millimetri, finite. Solo tagli dritti a 90°.",
        f"Lo schema considera una lama da {num(lama)} mm" + (f" e un rifilo di {num(rifilo)} mm per lato." if rifilo else
                                                              " e parte da uno spigolo in squadra del pannello."),
    ]
    if any(p.get("sagoma") for p in pezzi_by_cod.values()):
        note.append("I pezzi sagomati vanno tagliati come rettangoli: le sagome le rifinisco io.")
    note.append("Gli avanzi li ritiro.")
    note += prog["taglio"].get("note", [])
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>Distinta di taglio - {html.escape(prog['titolo'])}</title>
<style>{STAMPA_CSS}</style></head><body>
<h1>Distinta di taglio — {html.escape(prog['titolo'])}</h1>
<div class="meta">
  <div><b>Data</b> {data}</div><div><b>Cliente</b></div>
  <div><b>Essenza</b> ______________</div><div><b>Telefono</b></div>
</div>
<div class="box">
  <b>Materiale da fornire</b><ul>{righe_mat}</ul>
  <b>Indicazioni per il taglio</b><ul>{''.join(f'<li>{html.escape(n)}</li>' for n in note)}</ul>
</div>
{''.join(blocchi)}
<footer>Pezzi totali: {len(pezzi_by_cod)}. Codici come nello schema di ciascun pannello.</footer>
</body></html>"""


def _ordine_codice(c):
    pref = c.rstrip(string.digits)
    n = c[len(pref):]
    return (pref, int(n) if n else 0)


def main(cartella="."):
    import datetime
    prog = json.load(open(os.path.join(cartella, "build", "progetto.json")))
    cfg = prog["taglio"]
    lama, rifilo = cfg["lama"], cfg["rifilo"]
    da_tagliare = [p for p in prog["pezzi"] if "codice" in p]
    pezzi_by_cod = {p["codice"]: p for p in da_tagliare}
    per_pannello = {}
    for p in da_tagliare:
        per_pannello.setdefault((p.get("pannello") or p["materiale"], chiave_spessore(p["spessore"])), []).append(p)
    fogli = []
    lettere = iter(string.ascii_uppercase)
    for nome_pannello, sp in sorted(per_pannello, key=lambda k: (-float(k[1]), k[0])):
        formati = cfg["pannelli"].get(sp)
        if not formati:
            raise SystemExit(f"manca il formato dei pannelli per lo spessore {sp} mm (p.taglio(pannelli=...))")
        gruppo = per_pannello[(nome_pannello, sp)]
        pezzi = [(p["codice"], p["lunghezza"], p["larghezza"], p.get("venatura", False)) for p in gruppo]
        risultato, strategia = ottimizza(pezzi, formati, lama, rifilo)
        for f in risultato:
            f["nome"] = f"Pannello {next(lettere)}"
            f["spessore"] = float(sp)
            f["materiale"] = nome_pannello
            f["pezzi"].sort(key=lambda q: (q["x"], q["y"]))
            fogli.append(f)
        print(f"{nome_pannello} ({sp} mm): {len(risultato)} pannelli (strategia {strategia})")
    verifica(fogli, lama, rifilo)
    dove = {p["cod"]: f["nome"] for f in fogli for p in f["pezzi"]}

    with open(os.path.join(cartella, "distinta-taglio.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["codice", "voce", "lunghezza_mm", "larghezza_mm", "spessore_mm", "pannello", "nota", "pezzo_nel_modello"])
        for c in sorted(pezzi_by_cod, key=_ordine_codice):
            p = pezzi_by_cod[c]
            w.writerow([c, p["voce"], num(p["lunghezza"]), num(p["larghezza"]), num(p["spessore"]), dove[c], p.get("nota", ""), p["nome"]])

    righe = righe_distinta([pezzi_by_cod[c] for c in sorted(pezzi_by_cod, key=_ordine_codice)], dove)
    tr = []
    for r in righe:
        pann = ", ".join(x.replace("Pannello ", "") for x in r["pannelli"])
        tr.append(f'<tr><td class="code">{html.escape(r["cod_txt"])}</td><td>{html.escape(r["voce"])}</td><td class="mm">{r["pz"]}</td>'
                  f'<td class="mm">{num(r["L"])} × {num(r["l"])}</td><td class="mm">{num(r["sp"])}</td><td class="mm">{pann}</td>'
                  f'<td>{html.escape(r["nota"])}</td></tr>')
    figs = []
    riepilogo = []
    for f in fogli:
        W, H = f["formato"]
        u = utilizzo(f, pezzi_by_cod)
        av = avanzo_maggiore(f, lama)
        av_txt = f" · avanza {num(av[0])} × {num(av[1])}" if av and av[0] > 200 and av[1] > 200 else ""
        figs.append(f'<figure class="sheetfig"><figcaption><strong>{f["nome"]}</strong> · {num(W)} × {num(H)} · {num(f["spessore"])} mm'
                    f' · utilizzo {u * 100:.0f}%{av_txt}</figcaption><div class="svgscroll">{svg_foglio(f, pezzi_by_cod)}</div></figure>')
        riepilogo.append({"nome": f["nome"], "formato": f["formato"], "spessore": f["spessore"], "utilizzo": round(u, 3),
                          "avanzo": av, "pezzi": [p["cod"] for p in f["pezzi"]]})
    os.makedirs(os.path.join(cartella, "build"), exist_ok=True)
    open(os.path.join(cartella, "build", "distinta-righe.html"), "w").write("\n".join(tr))
    open(os.path.join(cartella, "build", "distinta-fogli.html"), "w").write("\n".join(figs))
    data = datetime.date.today().isoformat()
    open(os.path.join(cartella, "build", "distinta-stampa.html"), "w").write(
        pagina_stampa(prog, fogli, pezzi_by_cod, lama, rifilo, data))
    json.dump({"lama": lama, "rifilo": rifilo, "fogli": fogli, "riepilogo": riepilogo},
              open(os.path.join(cartella, "build", "taglio.json"), "w"), indent=1)
    for r in riepilogo:
        av = r["avanzo"]
        print(f'{r["nome"]} {num(r["formato"][0])}x{num(r["formato"][1])} sp {num(r["spessore"])}: {len(r["pezzi"])} pezzi, '
              f'utilizzo {r["utilizzo"] * 100:.0f}%' + (f', avanzo maggiore {num(av[0])}x{num(av[1])}' if av else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")

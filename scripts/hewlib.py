"""Libreria per descrivere un mobile in legno e generarne il modello Hew.

Un progetto è uno script `modello.py` che crea un `Progetto`, dichiara
materiali, pezzi (dentro gruppi), quote e scene, e chiama `salva()`.

Convenzioni:
    - misure in mm; Hew lavora in metri, la conversione è qui dentro
    - assi: X = lunghezza (sinistra -> destra), Y = profondità (0 = fronte,
      cresce verso il retro), Z = alto (0 = pavimento)
    - ogni pezzo in un materiale con `spessore=` entra nella distinta di taglio

`salva()` scrive in build/:
    script.json    i comandi JSON-RPC per `hew-cli run`
    progetto.json  pezzi, gruppi, quote, scene, ingombri e configurazione di taglio
"""
import json
import math
import os
import sys
from contextlib import contextmanager


def _m(v):
    return round(v / 1000.0, 6)


def _pt(p):
    return [_m(c) for c in p]


def chiave_spessore(sp):
    """Chiave testuale di uno spessore: 12 e 12.0 diventano entrambi "12"."""
    return "%g" % float(sp)


class Progetto:
    def __init__(self, titolo, sottotitolo="", descrizione=""):
        self.titolo = titolo
        self.sottotitolo = sottotitolo
        self.descrizione = descrizione
        self.materiali = {}      # nome -> {"id", "colore", "spessore"}
        self.pezzi = []          # dict per pezzo
        self.gruppi = []         # [{"nome", "esploso", "pezzi": [nomi]}]
        self.quote = []
        self.scene = []
        self.taglio_cfg = {"lama": 3.0, "rifilo": 0.0, "note": [], "pannelli": {}}
        self._gruppo = None
        self._frames = [
            {"method": "hew.meta.hello", "params": {"protocol": 1}},
            {"method": "hew.doc.new", "params": {}},
        ]
        self._cmds = None
        self._n = 0
        self._codici = set()

    # --- materiali -----------------------------------------------------------------
    def materiale(self, nome, colore, spessore=None, pannello=None):
        """Colore RGB 0-255. Con `spessore` (mm) il materiale è un pannello da tagliare.

        `pannello`: nome del pannello da cui si ricavano i pezzi (default: il nome del materiale).
        Materiali diversi solo per colore nel modello (es. "Telaio") ma tagliati dallo stesso
        pannello devono avere lo stesso `pannello` e lo stesso spessore.
        """
        if nome in self.materiali:
            raise ValueError(f"materiale ripetuto: {nome}")
        self.materiali[nome] = {"id": f"mat_{len(self.materiali)}", "colore": list(colore), "spessore": spessore,
                                "pannello": (pannello or nome) if spessore is not None else None}
        self._frames.append({"method": "hew.material.create", "params": {"name": nome, "color": list(colore)}})
        return nome

    # --- gruppi --------------------------------------------------------------------
    @contextmanager
    def gruppo(self, nome, esploso=(0, 0, 0)):
        """Tutti i pezzi creati nel blocco finiscono in un gruppo Hew (una voce di annullamento).

        `esploso`: spostamento in mm del gruppo nella vista esplosa del visualizzatore.
        """
        if self._gruppo is not None:
            raise RuntimeError("i gruppi non si annidano")
        self._gruppo = {"nome": nome, "esploso": list(esploso), "pezzi": [], "labels": []}
        self._cmds = []
        try:
            yield self
        finally:
            g = self._gruppo
            if g["labels"]:
                lg = self._label("g")
                self._cmds += [
                    {"method": "hew.group.create", "as": lg,
                     "params": {"members": [{"$ref": f"{l}#/object_id"} for l in g["labels"]]}},
                    {"method": "hew.entity.rename", "params": {"id": {"$ref": f"{lg}#/group"}, "name": nome}},
                ]
                self._frames.append({"method": "hew.doc.transact", "params": {"label": nome, "commands": self._cmds}})
                self.gruppi.append({"nome": nome, "esploso": g["esploso"], "pezzi": g["pezzi"]})
            self._gruppo = None
            self._cmds = None

    def _label(self, prefix):
        self._n += 1
        return f"{prefix}{self._n}"

    def _registra(self, nome, mat, bbox, taglio, codice, nota, venatura, extra_cmds_label, voce=None, sagoma=None):
        if self._gruppo is None:
            raise RuntimeError(f"il pezzo {nome!r} va creato dentro un `with p.gruppo(...)`")
        if mat not in self.materiali:
            raise ValueError(f"materiale sconosciuto: {mat}")
        if any(p["nome"] == nome for p in self.pezzi):
            raise ValueError(f"nome pezzo ripetuto (serve univoco): {nome}")
        sp = self.materiali[mat]["spessore"]
        pezzo = {"nome": nome, "materiale": mat, "gruppo": self._gruppo["nome"], "bbox": bbox, "nota": nota}
        if sp is not None:
            if taglio is None:
                raise ValueError(f"{nome}: impossibile ricavare le misure di taglio")
            if codice is None:
                raise ValueError(f"{nome}: i pezzi da tagliare vogliono un `codice` (es. 'F', 'S1')")
            if codice in self._codici:
                raise ValueError(f"codice ripetuto: {codice}")
            self._codici.add(codice)
            lun, lar = sorted(taglio, reverse=True)
            pezzo.update({"codice": codice, "voce": voce or nome, "spessore": sp, "pannello": self.materiali[mat]["pannello"],
                          "lunghezza": round(lun, 1),
                          "larghezza": round(lar, 1), "venatura": venatura})
            if sagoma:
                pezzo["sagoma"] = sagoma
        self.pezzi.append(pezzo)
        self._gruppo["pezzi"].append(nome)
        self._gruppo["labels"].append(extra_cmds_label)

    def _finisci(self, e, nome, mat):
        self._cmds += [
            {"method": "hew.entity.rename", "params": {"id": {"$ref": f"{e}#/object_id"}, "name": nome}},
            {"method": "hew.material.paint", "params": {"id": {"$ref": f"{e}#/object_id"}, "material": self.materiali[mat]["id"]}},
        ]

    # --- pezzi ---------------------------------------------------------------------
    def box(self, nome, mat, a, b, codice=None, voce=None, nota="", venatura=False):
        """Parallelepipedo tra gli spigoli opposti `a` e `b` (mm).

        Per un pannello, lo spessore del materiale deve coincidere con una delle tre misure.
        `codice` (es. "F", "S1") e `voce` (nome nella distinta, uguale per pezzi gemelli)
        servono alla distinta di taglio; `venatura=True` vieta di ruotare il pezzo sul pannello.
        """
        (x0, y0, z0), (x1, y1, z1) = [min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)]
        dims = [x1 - x0, y1 - y0, z1 - z0]
        taglio = None
        sp = self.materiali[mat]["spessore"]
        if sp is not None:
            idx = [i for i, d in enumerate(dims) if abs(d - sp) < 0.01]
            if not idx:
                raise ValueError(f"{nome}: nessuna misura {dims} vale lo spessore {sp}")
            taglio = [d for i, d in enumerate(dims) if i != idx[0]]
        r, e = self._label("r"), self._label("e")
        self._cmds += [
            {"method": "hew.sketch.draw_rect", "as": r, "params": {
                "detached": True, "plane": {"origin": _pt((0, 0, z0)), "normal": [0, 0, 1], "x_axis": [1, 0, 0]},
                "corner_a": _pt((x0, y0, z0)), "corner_b": _pt((x1, y1, z0))}},
            {"method": "hew.solid.extrude", "as": e, "params": {"region": {"$ref": f"{r}#/region_id"}, "distance": _m(z1 - z0)}},
        ]
        self._finisci(e, nome, mat)
        self._registra(nome, mat, [[x0, y0, z0], [x1, y1, z1]], taglio, codice, nota, venatura, e, voce)
        return nome

    def profilo(self, nome, mat, piano, quota, spessore, punti, codice=None, voce=None, nota="", venatura=False, taglio=None):
        """Poligono disegnato su un piano assiale ed estruso di `spessore` lungo l'asse del piano.

        piano "yz": punti (y, z), piano a x=quota, estrusione verso +X
        piano "xz": punti (x, z), piano a y=quota, estrusione verso +Y
        piano "xy": punti (x, y), piano a z=quota, estrusione verso +Z
        Le misure di taglio sono il rettangolo d'ingombro del poligono (la sagoma si rifinisce a parte).
        Per un pannello inclinato, il cui spessore non corre lungo l'asse di estrusione (es. un listello
        disegnato come parallelogramma nel piano e estruso per la sua larghezza), passa
        `taglio=(lunghezza, larghezza)` esplicito: lo spessore del materiale non viene controllato.
        """
        assi = {"yz": (0, (1, 2)), "xz": (1, (0, 2)), "xy": (2, (0, 1))}
        ax, (u, v) = assi[piano]
        normale = [0, 0, 0]
        normale[ax] = 1
        x_axis = [0, 0, 0]
        x_axis[u] = 1

        def p3(uv):
            p = [0.0, 0.0, 0.0]
            p[ax], p[u], p[v] = quota, uv[0], uv[1]
            return p

        chiuso = list(punti) + [punti[0]]
        us, vs = [p[0] for p in punti], [p[1] for p in punti]
        lo, hi = [0.0] * 3, [0.0] * 3
        lo[ax], hi[ax] = quota, quota + spessore
        lo[u], hi[u], lo[v], hi[v] = min(us), max(us), min(vs), max(vs)
        sp = self.materiali[mat]["spessore"]
        esplicito = taglio is not None
        if sp is not None and esplicito:
            taglio = list(taglio)
        elif sp is not None:
            if abs(spessore - sp) > 0.01:
                raise ValueError(f"{nome}: estrusione {spessore} diversa dallo spessore del materiale {sp}")
            taglio = [max(us) - min(us), max(vs) - min(vs)]
        o = [0.0, 0.0, 0.0]
        o[ax] = quota
        l, e = self._label("p"), self._label("e")
        self._cmds += [
            {"method": "hew.sketch.draw_line", "as": l, "params": {
                "detached": True, "plane": {"origin": _pt(o), "normal": normale, "x_axis": x_axis},
                "points": [_pt(p3(q)) for q in chiuso]}},
            {"method": "hew.solid.extrude", "as": e, "params": {"region": {"$ref": f"{l}#/region_id"}, "distance": _m(spessore)}},
        ]
        self._finisci(e, nome, mat)
        sagoma = None
        du, dv = max(us) - min(us), max(vs) - min(vs)
        rettangolo = len(punti) == 4 and all(
            (abs(q[0] - min(us)) < 0.01 or abs(q[0] - max(us)) < 0.01) and (abs(q[1] - min(vs)) < 0.01 or abs(q[1] - max(vs)) < 0.01)
            for q in punti)
        if taglio is not None and not rettangolo and not esplicito:
            # sagoma nelle coordinate del rettangolo di taglio: (lungo la lunghezza, lungo la larghezza)
            if du >= dv:
                sagoma = [[round(q[0] - min(us), 1), round(q[1] - min(vs), 1)] for q in punti]
            else:
                sagoma = [[round(q[1] - min(vs), 1), round(q[0] - min(us), 1)] for q in punti]
        self._registra(nome, mat, [lo, hi], taglio, codice, nota, venatura, e, voce, sagoma)
        return nome

    def cilindro(self, nome, mat, centro, raggio, lunghezza, asse="x", segmenti=32):
        """Cilindro (ruote, tondini). `centro` è il centro della base; estrusione verso +asse."""
        ax = "xyz".index(asse)
        normale = [0, 0, 0]
        normale[ax] = 1
        x_axis = [0, 1, 0] if asse == "x" else [1, 0, 0]
        o = [0.0, 0.0, 0.0]
        o[ax] = centro[ax]
        lo = [c - raggio for c in centro]
        hi = [c + raggio for c in centro]
        lo[ax], hi[ax] = centro[ax], centro[ax] + lunghezza
        c, e = self._label("c"), self._label("e")
        self._cmds += [
            {"method": "hew.sketch.draw_circle", "as": c, "params": {
                "detached": True, "plane": {"origin": _pt(o), "normal": normale, "x_axis": x_axis},
                "center": _pt(centro), "radius": _m(raggio), "segments": segmenti}},
            {"method": "hew.solid.extrude", "as": e, "params": {"region": {"$ref": f"{c}#/region_id"}, "distance": _m(lunghezza)}},
        ]
        self._finisci(e, nome, mat)
        if self.materiali[mat]["spessore"] is not None:
            raise ValueError(f"{nome}: un cilindro non può stare in un materiale da pannello")
        self._registra(nome, mat, [lo, hi], None, None, "", False, e)
        return nome

    # --- quote, scene, taglio ------------------------------------------------------
    def quota(self, tag, a, b, normale, offset, arrotonda=False):
        """Quota lineare da `a` a `b` (mm), nel piano con `normale` (asse, es. (0,0,1)),
        con la linea di misura spostata di `offset` (vettore mm nel piano).

        `tag` è il nome del gruppo di quote: nell'app diventa il tag "Quote - <tag>".
        `arrotonda=True`: nella pagina web mostra il valore al millimetro (utile per gli ingombri).
        """
        self.quote.append({"tag": f"Quote - {tag}", "a": list(a), "b": list(b), "n": list(normale),
                           "off": list(offset), "mm": round(math.dist(a, b), 1), "arrotonda": arrotonda})

    def scena(self, nome, occhio, bersaglio):
        """Scena Hew con camera (punti in mm)."""
        self.scene.append({"nome": nome, "occhio": list(occhio), "bersaglio": list(bersaglio)})

    def taglio(self, pannelli, lama=3.0, rifilo=0.0, note=()):
        """Formati dei pannelli per spessore, es. {12: [(2500, 1250)], 8: [(2500, 1250), (1250, 1250)]}.

        Il primo formato è quello standard; gli altri (più piccoli) si usano per l'ultimo pannello
        se bastano. `rifilo`: margine da togliere su ogni bordo del pannello.
        `note`: righe aggiunte alle indicazioni per il rivenditore nella distinta stampabile.
        """
        self.taglio_cfg = {"lama": lama, "rifilo": rifilo, "note": list(note),
                           "pannelli": {chiave_spessore(k): [list(f) for f in v] for k, v in pannelli.items()}}

    # --- uscita --------------------------------------------------------------------
    def ingombro(self):
        lo = [min(p["bbox"][0][i] for p in self.pezzi) for i in range(3)]
        hi = [max(p["bbox"][1][i] for p in self.pezzi) for i in range(3)]
        return lo, hi

    def salva(self, cartella="build"):
        if self._gruppo is not None:
            raise RuntimeError("salva() dentro un gruppo")
        os.makedirs(cartella, exist_ok=True)
        frames = list(self._frames)
        for s in self.scene:
            frames.append({"method": "hew.scenes.add", "params": {
                "name": s["nome"], "camera": {"eye": _pt(s["occhio"]), "target": _pt(s["bersaglio"]), "up": [0, 0, 1]}}})
        frames.append({"method": "hew.query.scene", "params": {}})
        script = [{"jsonrpc": "2.0", "id": i + 1, **f} for i, f in enumerate(frames)]
        with open(os.path.join(cartella, "script.json"), "w") as fh:
            json.dump(script, fh)
        mancanti = [chiave_spessore(p["spessore"]) for p in self.pezzi if "codice" in p
                    and chiave_spessore(p["spessore"]) not in self.taglio_cfg["pannelli"]]
        if mancanti:
            print(f"attenzione: nessun formato di pannello per gli spessori {sorted(set(mancanti))}: "
                  "chiama p.taglio(pannelli={...})", file=sys.stderr)
        lo, hi = self.ingombro()
        dati = {
            "titolo": self.titolo, "sottotitolo": self.sottotitolo, "descrizione": self.descrizione,
            "materiali": self.materiali, "pezzi": self.pezzi, "gruppi": self.gruppi, "quote": self.quote,
            "scene": self.scene, "taglio": self.taglio_cfg, "ingombro": [lo, hi],
        }
        with open(os.path.join(cartella, "progetto.json"), "w") as fh:
            json.dump(dati, fh, indent=1)
        n_tagli = sum(1 for p in self.pezzi if "codice" in p)
        print(f"{len(self.pezzi)} pezzi ({n_tagli} da tagliare) in {len(self.gruppi)} gruppi, "
              f"{len(self.quote)} quote; ingombro {hi[0] - lo[0]:.0f} x {hi[1] - lo[1]:.0f} x {hi[2] - lo[2]:.0f} mm")

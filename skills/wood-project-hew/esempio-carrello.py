"""Carrello porta scarti: carrello su ruote per ritagli di legno.

Fonte: riferimenti/Carrello per gli scarti.pdf (SketchUp, 2021), con le modifiche concordate:
pannello centrale 1100, coperture da 8 mm applicate all'esterno, scaffale a listelli da 90
al posto del pannello inclinato, telaio di base con listelli da 90.

Assi: X lunghezza (0..1200), Y profondità (0 = fronte), Z alto. Misure in mm.
"""
import math

from hewlib import Progetto

p = Progetto(
    "Carrello porta scarti",
    sottotitolo="Wood storage · Hew",
    descrizione="Ricostruzione 3D dalle tavole SketchUp del 2021, con scaffale a listelli e distinta di taglio.",
)

# --- misure ---------------------------------------------------------------------
T, T8 = 12.0, 8.0                 # multistrato strutturale e coperture
L, P = 1200.0, 600.0              # fondo
H_RUOTE = 75.0                    # piastra delle ruote
Z_TELAIO = H_RUOTE
Z_FONDO = Z_TELAIO + T
Z0 = Z_FONDO + T                  # piano d'appoggio: le altezze del PDF partono da qui

SEP_P, SEP_H_DIETRO, SEP_H_DAVANTI, SEP_PIANO = 238.0, 600.0, 400.0, 125.0
VANI = [100, 200, 250, 250, 328]  # 6 separatori da 12 + vani = 1200
H_FRONTALE, H_BATTUTA = 421.0, 100.0

Y_C = SEP_P                       # faccia anteriore del pannello centrale
H_CENTRALE = 1100.0
PROF_BASE, INCL = 220.0, 0.0875   # listelli inclinati di ~5°: danno i ripiani 194 / 172,8 / 151,7 / 130,2
N_LIST, W_LIST, L_LIST = 5, 90.0, 1240.0
H_LIST = L_LIST * math.cos(math.atan(INCL))
Z_RIPIANI = [285.0, 285 + T + 230, 285 + 2 * (T + 230), 285 + 2 * (T + 230) + T + 233]
W_TELAIO = 90.0


def y_listelli(z):
    """Faccia anteriore dei listelli inclinati, z relativo a Z0."""
    return Y_C + T + PROF_BASE - INCL * z


# --- materiali ------------------------------------------------------------------
M12 = p.materiale("Multistrato 12 mm", (222, 196, 140), spessore=12)
M8 = p.materiale("Multistrato 8 mm", (196, 160, 104), spessore=8)
TEL = p.materiale("Telaio", (170, 132, 82), spessore=12, pannello="Multistrato 12 mm")
RUOTA = p.materiale("Ruote", (55, 55, 60))
PIASTRA = p.materiale("Ruote - piastre", (150, 150, 155))

# --- pezzi ----------------------------------------------------------------------
with p.gruppo("Base e ruote", esploso=(0, 0, -220)):
    for nome, xc, yc in [("AS", 60, 60), ("AD", L - 60, 60), ("PS", 60, P - 60), ("PD", L - 60, P - 60)]:
        p.box(f"Ruota {nome} - piastra", PIASTRA, (xc - 35, yc - 35, H_RUOTE - 5), (xc + 35, yc + 35, H_RUOTE))
        p.box(f"Ruota {nome} - forcella", PIASTRA, (xc - 16, yc - 12, 30), (xc + 16, yc + 12, H_RUOTE - 5))
        p.cilindro(f"Ruota {nome} - ruota", RUOTA, (xc - 11, yc, 30), 30, 22, asse="x")
    w, zt0, zt1 = W_TELAIO, Z_TELAIO, Z_TELAIO + T
    p.box("Telaio - traverso sx", TEL, (0, 0, zt0), (w, P, zt1), codice="T1", voce="Telaio, traverso")
    p.box("Telaio - traverso dx", TEL, (L - w, 0, zt0), (L, P, zt1), codice="T2", voce="Telaio, traverso")
    p.box("Telaio - longherone anteriore", TEL, (w, 0, zt0), (L - w, w, zt1), codice="G1", voce="Telaio, longherone",
          nota="tra i due traversi")
    p.box("Telaio - longherone posteriore", TEL, (w, P - w, zt0), (L - w, P, zt1), codice="G2", voce="Telaio, longherone",
          nota="tra i due traversi")
    p.box("Fondo", M12, (0, 0, Z_FONDO), (L, P, Z0), codice="F")

with p.gruppo("Vano scarti", esploso=(0, -420, 0)):
    p.box("Frontale", M8, (0, -T8, Z_TELAIO), (L, 0, Z_TELAIO + H_FRONTALE), codice="FR", nota="copre fondo e telaio")
    profilo = [(0, Z0), (SEP_P, Z0), (SEP_P, Z0 + SEP_H_DIETRO), (SEP_P - SEP_PIANO, Z0 + SEP_H_DIETRO), (0, Z0 + SEP_H_DAVANTI)]
    x = 0.0
    for i in range(len(VANI) + 1):
        p.profilo(f"Separatore {i + 1}", M12, "yz", x, T, profilo, codice=f"S{i + 1}", voce="Separatore",
                  nota="davanti 400, piano 125, smusso 60,5°")
        if i < len(VANI):
            x += T + VANI[i]

with p.gruppo("Pannello centrale", esploso=(0, -120, 0)):
    p.box("Pannello centrale", M12, (0, Y_C, Z0), (L, Y_C + T, Z0 + H_CENTRALE), codice="PC")

with p.gruppo("Scaffale listelli", esploso=(0, 180, 0)):
    sp_o = T / math.cos(math.atan(INCL))
    falda = [(y_listelli(0), Z0), (y_listelli(0) + sp_o, Z0), (y_listelli(H_LIST) + sp_o, Z0 + H_LIST), (y_listelli(H_LIST), Z0 + H_LIST)]
    passo = (L - W_LIST) / (N_LIST - 1)
    for i in range(N_LIST):
        p.profilo(f"Listello {i + 1}", M12, "yz", i * passo, W_LIST, falda, codice=f"L{i + 1}", voce="Listello scaffale",
                  taglio=(L_LIST, W_LIST), nota=f"estremità a 5°, interasse ~{passo:.0f}")
    for i, zr in enumerate(Z_RIPIANI):
        prof = y_listelli(zr + T) - (Y_C + T)
        p.box(f"Ripiano {i + 1}", M12, (0, Y_C + T, Z0 + zr), (L, Y_C + T + prof, Z0 + zr + T), codice=f"R{i + 1}",
              voce=f"Ripiano {i + 1}" + (" (basso)" if i == 0 else " (alto)" if i == 3 else ""))

with p.gruppo("Battuta pannelli", esploso=(0, 500, 0)):
    p.box("Battuta posteriore", M8, (0, P, Z_TELAIO), (L, P + T8, Z_TELAIO + H_BATTUTA), codice="BT", nota="copre fondo e telaio")

# --- quote ----------------------------------------------------------------------
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
Y_CB, Z_TOP_L, Y_TOP_L = Y_C + T, Z0 + H_LIST, y_listelli(H_LIST)
p.quota("Ingombri", (0, -T8, 0), (L, -T8, 0), Z, (0, -150, 0), arrotonda=True)
p.quota("Ingombri", (L, -T8, 0), (L, P + T8, 0), Z, (150, 0, 0), arrotonda=True)
p.quota("Ingombri", (L, Y_C, 0), (L, Y_C, Z0 + H_CENTRALE), X, (0, -330, 0), arrotonda=True)
p.quota("Ingombri", (L, Y_TOP_L, 0), (L, Y_TOP_L, Z_TOP_L), X, (0, 360, 0), arrotonda=True)

p.quota("Dettagli", (0, -T8, Z_TELAIO), (0, -T8, Z_TELAIO + H_FRONTALE), X, (0, -80, 0))
x = 0.0
for v in VANI:
    p.quota("Dettagli", (x + T, Y_C, Z0 + SEP_H_DIETRO), (x + T + v, Y_C, Z0 + SEP_H_DIETRO), Y, (0, 0, 60))
    x += T + v
p.quota("Dettagli", (L, Y_C, Z0), (L, Y_C, Z0 + SEP_H_DIETRO), X, (0, -70, 0))
p.quota("Dettagli", (L, 0, Z0), (L, 0, Z0 + SEP_H_DAVANTI), X, (0, -45, 0))
p.quota("Dettagli", (L, Y_C - SEP_PIANO, Z0 + SEP_H_DIETRO), (L, Y_C, Z0 + SEP_H_DIETRO), X, (0, 0, 50))
z = Z0
for zr in Z_RIPIANI:
    p.quota("Dettagli", (0, Y_CB, z), (0, Y_CB, Z0 + zr), X, (0, 45, 0))
    z = Z0 + zr + T
for zr in Z_RIPIANI:
    zt = Z0 + zr + T
    p.quota("Dettagli", (0, Y_CB, zt), (0, y_listelli(zr + T), zt), X, (0, 0, 30))
passo = (L - W_LIST) / (N_LIST - 1)
p.quota("Dettagli", (0, Y_TOP_L, Z_TOP_L), (W_LIST, Y_TOP_L, Z_TOP_L), Z, (0, -40, 0))
p.quota("Dettagli", (W_LIST, Y_TOP_L, Z_TOP_L), (passo, Y_TOP_L, Z_TOP_L), Z, (0, -40, 0))

# --- scene ----------------------------------------------------------------------
c = (L / 2, P / 2, 600)
p.scena("Fronte 3/4", (c[0] + 1900, c[1] - 2600, 1900), c)
p.scena("Retro 3/4", (c[0] - 1900, c[1] + 2600, 1900), c)
p.scena("Fianco", (c[0] + 3000, c[1], 600), c)

# --- taglio ---------------------------------------------------------------------
p.taglio(
    pannelli={12: [(2500, 1250)], 8: [(2500, 1250), (1250, 1250)]},
    lama=3,
    note=[
        "Listelli L1–L5 lunghi 1240: con l'inclinazione di 5° salgono a circa 1235 dal fondo, 135 sopra il pannello centrale.",
        "Telaio di base con listelli da 90 al posto di 80 e 60 del PDF, per ricavarli dalle stesse strisce.",
        "Misure dedotte: spessore 12 mm (6 separatori + vani = 1200), inclinazione 5° dei listelli, ruote indicative.",
    ],
)

p.salva()

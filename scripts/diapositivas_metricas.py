"""Diapositivas de métricas (1920×1080, 16:9) para el pitch.

    env -u PYTHONPATH .venv/bin/python scripts/diapositivas_metricas.py   -> pitch/diapositivas/*.png

Datos: la misma simulación que /api/metricas (sim/metricas.py + scripts/graficos_metricas.py).
Una idea por diapositiva; el titular dice la conclusión, la gráfica la demuestra.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from graficos_metricas import C, simular_dia  # noqa: E402
from sim import fisica_pabellon as fp  # noqa: E402
from sim.metricas import PASO_S, UMBRAL_RIESGO, dia, escenario  # noqa: E402

SALIDA = RAIZ / "pitch" / "diapositivas"
FONDO, TINTA, SUAVE = "#fcfcfb", "#1b1b19", "#6b6a63"
def es(x, d=1):
    """Número con coma decimal y punto de miles (formato español)."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


PIE = "Simulación física OASI · ola de calor tipo Barcelona (julio) · datos de entrada supuestos, no medidos"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 17, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e5df", "axes.edgecolor": "#9a998f", "axes.labelcolor": SUAVE,
                     "xtick.color": SUAVE, "ytick.color": SUAVE, "figure.facecolor": FONDO, "axes.facecolor": FONDO,
                     "savefig.bbox": "standard", "savefig.dpi": 150})   # sin recorte: 1920×1080 exactos


def lienzo(titular: str, sub: str = ""):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
    fig.text(0.045, 0.93, titular, fontsize=30, fontweight="bold", color=TINTA, va="top")
    if sub:
        fig.text(0.045, 0.855, sub, fontsize=17, color=SUAVE, va="top")
    fig.text(0.045, 0.03, PIE, fontsize=11, color=SUAVE)
    return fig


def guardar(fig, nombre):
    fig.savefig(SALIDA / f"{nombre}.png", facecolor=FONDO)
    plt.close(fig)


def horas(ax):
    ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 3)); ax.set_xticklabels([f"{h}h" for h in range(0, 25, 3)])


def d1_cifras(R, R5):
    fig = lienzo("OASI en cifras", "Pabellón Venturi 6 × 2,4 m en una parada de bus · día tipo de ola de calor (máx. 36 °C)")
    kpis = [(f"−{R['grados_reducidos_pico']:.0f} °C", "más fresco que la calle\nen la hora punta", C["azul"]),
            (f"{R['horas_riesgo_evitadas']:.0f} h", "de calor peligroso evitadas\ncada día (índice > 32 °C)", C["naranja"]),
            (f"{R['pct_autoconsumo']:.0f} %", "de la energía sale\nde sus placas solares", C["aqua"]),
            (f"{es(R['coste_eur_dia'], 0)} €", "de luz de la red al día\n(todo con sol y batería)", C["violeta"]),
            (f"{R['autonomia_h']:.0f} h", "de autonomía nocturna\ncon batería", C["azul"]),
            (f"{R['kwh_solares']:.0f} kWh", "solares al día", C["aqua"])]
    for i, (v, t, col) in enumerate(kpis):
        x, y = 0.045 + (i % 3) * 0.315, 0.52 - (i // 3) * 0.36
        fig.patches.append(plt.Rectangle((x, y), 0.29, 0.29, transform=fig.transFigure, facecolor="white", edgecolor="#e2e1da", lw=1.5))
        fig.patches.append(plt.Rectangle((x, y + 0.27), 0.29, 0.02, transform=fig.transFigure, facecolor=col, edgecolor="none"))
        fig.text(x + 0.02, y + 0.19, v, fontsize=46, fontweight="bold", color=TINTA, va="center")
        fig.text(x + 0.02, y + 0.07, t, fontsize=15, color=SUAVE, va="center", linespacing=1.3)
    guardar(fig, "01_cifras_clave")


def d2_temperatura(D, R):
    fig = lienzo(f"Dentro, {R['grados_reducidos_pico']:.0f} °C menos que en la calle",
                 "Temperatura a lo largo del día · el mismo pabellón cerrado y sin control llegaría a más de 50 °C")
    ax = fig.add_axes([0.07, 0.12, 0.86, 0.66])
    ax.plot(D["h"], D["t_cerrado"], color=C["amarillo"], lw=3)
    ax.plot(D["h"], D["t_ext"], color=C["naranja"], lw=3.5)
    ax.plot(D["h"], D["t_int"], color=C["azul"], lw=4.5)
    for y, txt, col in [(D["t_cerrado"], "Cerrado sin control", C["amarillo"]), (D["t_ext"], "Calle", C["naranja"]), (D["t_int"], "OASI", C["azul"])]:
        i = int(np.argmin(np.abs(D["h"] - 13.5)))
        ax.annotate(txt, (D["h"][i], y[i]), xytext=(0, 16), textcoords="offset points", color=col, fontweight="bold", fontsize=17, ha="center")
    i = int(np.argmax(D["t_ext"] - D["t_int"] + (D["rad"] <= 0) * -99))
    ax.annotate("", xy=(D["h"][i], D["t_int"][i]), xytext=(D["h"][i], D["t_ext"][i]), arrowprops=dict(arrowstyle="<->", color=TINTA, lw=2))
    ax.text(D["h"][i] + 0.35, (D["t_int"][i] + D["t_ext"][i]) / 2, f"−{D['t_ext'][i] - D['t_int'][i]:.0f} °C", fontsize=24, fontweight="bold", va="center")
    ax.set_ylabel("°C"); horas(ax)
    guardar(fig, "02_temperatura_calle_vs_oasi")


def d3_riesgo(D, R):
    paso = PASO_S / 3600
    hc, hi = (D["ic_ext"] > UMBRAL_RIESGO).sum() * paso, (D["ic_int"] > UMBRAL_RIESGO).sum() * paso
    fig = lienzo(f"{R['horas_riesgo_evitadas']:.0f} horas de calor peligroso evitadas al día",
                 f"Horas con índice de calor NOAA > {UMBRAL_RIESGO:.0f} °C (temperatura + humedad)")
    ax = fig.add_axes([0.07, 0.12, 0.55, 0.66])
    ax.plot(D["h"], D["ic_ext"], color=C["naranja"], lw=3.5, label="Calle")
    ax.plot(D["h"], D["ic_int"], color=C["azul"], lw=4, label="OASI")
    ax.axhline(UMBRAL_RIESGO, color=C["rojo"], ls=":", lw=2)
    ax.fill_between(D["h"], UMBRAL_RIESGO, D["ic_ext"], where=D["ic_ext"] > UMBRAL_RIESGO, color=C["naranja"], alpha=0.15)
    ax.text(0.3, UMBRAL_RIESGO + 0.5, "riesgo", color=C["rojo"], fontsize=15, fontweight="bold")
    ax.set_ylabel("índice de calor (°C)"); horas(ax); ax.legend(frameon=False, loc="upper left")
    bx = fig.add_axes([0.70, 0.12, 0.26, 0.66])
    b = bx.bar(["Calle", "OASI"], [hc, hi], color=[C["naranja"], C["azul"]], width=0.62)
    bx.bar_label(b, labels=[f"{hc:.0f} h", f"{hi:.0f} h"], fontsize=24, fontweight="bold", padding=6)
    bx.set_ylim(0, max(hc, 1) * 1.25); bx.set_yticks([]); bx.grid(False); bx.spines["left"].set_visible(False)
    bx.set_title("horas de riesgo / día", color=SUAVE, fontsize=15)
    guardar(fig, "03_horas_de_riesgo")


def d4_energia(D, R):
    fig = lienzo(f"{R['pct_autoconsumo']:.0f} % solar: el refugio se paga su propio aire",
                 f"{es(R['kwh_solares'])} kWh de placas al día · la batería cubre la noche · {es(R['coste_eur_dia'], 0)} € de red")
    ax = fig.add_axes([0.07, 0.12, 0.86, 0.66])
    ax.fill_between(D["h"], 0, D["solar"] / 1000, color=C["aqua"], alpha=0.3)
    ax.plot(D["h"], D["solar"] / 1000, color=C["aqua"], lw=3.5)
    ax.plot(D["h"], D["consumo"] / 1000, color=C["naranja"], lw=3.5)
    ax.text(13.5, D["solar"].max() / 1000 + 0.08, "Placas solares", color=C["aqua"], fontweight="bold", ha="center")
    ax.text(21.5, D["consumo"][int(21.5 * 6)] / 1000 + 0.12, "Consumo", color=C["naranja"], fontweight="bold", ha="center")
    ax.set_ylabel("kW"); horas(ax)
    a2 = ax.twinx(); a2.plot(D["h"], D["bat"], color=C["azul"], lw=2.5, ls="--"); a2.set_ylim(0, 105); a2.set_ylabel("batería (%)", color=C["azul"])
    a2.grid(False); a2.spines["right"].set_visible(True); a2.tick_params(colors=C["azul"])
    a2.text(2, D["bat"][12] + 4, "Batería", color=C["azul"], fontweight="bold")
    guardar(fig, "04_energia_solar")


def d5_ventilacion(D):
    q = D["q"]; h_v = (q > 0).sum() * PASO_S / 3600
    fig = lienzo("De noche se refresca solo, sin gastar energía",
                 f"Efecto Venturi + tiro térmico: {h_v:.0f} h de ventilación natural, hasta {es(q.max(), 0)} m³/h")
    ax = fig.add_axes([0.07, 0.30, 0.86, 0.48])
    ax.fill_between(D["h"], 0, q, color=C["aqua"], alpha=0.35, step="pre"); ax.plot(D["h"], q, color=C["aqua"], lw=3, drawstyle="steps-pre")
    ax.set_ylabel("aire renovado (m³/h)"); horas(ax); ax.set_xticklabels([])
    ax.text(4.2, q.max() * 0.55, "Ventilación natural\n(cima abierta)", color=C["aqua"], fontweight="bold", ha="center", fontsize=17)
    ax.text(16.5, q.max() * 0.55, "Calor fuera: cima cerrada,\naire acondicionado solar", color=C["naranja"], fontweight="bold", ha="center", fontsize=17)
    bx = fig.add_axes([0.07, 0.12, 0.86, 0.13])
    est = np.vstack([D["apertura"] > 0, D["ac"]]).astype(float)
    bx.imshow(est, aspect="auto", extent=(0, 24, 1.5, -0.5), cmap="Greens", vmin=0, vmax=1.3, interpolation="nearest")
    bx.set_yticks([0, 1]); bx.set_yticklabels(["Cima abierta", "AC"], fontsize=14); bx.grid(False); horas(bx)
    guardar(fig, "05_ventilacion_natural")


def d6_tamanos():
    fig = lienzo("Crece con la ciudad: de 4 a 12 m de largo",
                 "y de 2,4 a 4,8 m de ancho · cada tamaño simulado con la misma física")
    filas = [(l, a, dia(l, a)) for a in fp.ANCHOS for l in fp.LARGOS]
    cols = {2.4: C["azul"], 3.6: C["aqua"], 4.8: C["violeta"]}
    for k, (clave, tit, f) in enumerate([("kwh", "Energía solar (kWh/día)", lambda r: r["resumen"]["kwh_solares"]),
                                         ("aut", "Autonomía de batería (h)", lambda r: r["resumen"]["autonomia_h"]),
                                         ("afo", "Plazas", lambda r: r["pabellon"]["aforo_max"])]):
        ax = fig.add_axes([0.06 + k * 0.315, 0.14, 0.27, 0.6])
        for a in fp.ANCHOS:
            xs = [l for l, aa, _ in filas if aa == a]; ys = [f(r) for l, aa, r in filas if aa == a]
            ax.plot(xs, ys, "o-", color=cols[a], lw=3, ms=8)
            ax.lines[-1].set_label(f"ancho {a:.1f} m".replace(".", ","))
        if k == 0:
            ax.legend(frameon=False, fontsize=14, loc="upper left")
        ax.set_title(tit, loc="left", fontsize=17, fontweight="bold", color=TINTA); ax.set_xticks(fp.LARGOS); ax.set_xlabel("largo (m)")
    guardar(fig, "06_tamanos")


def d7_ola_5_dias():
    e = escenario(); s, r5 = e["series"], e["resumen"]
    h = np.array(s["t"]) / 3600
    fig = lienzo("Aguanta la ola de calor entera",
                 f"5 días (+0,5 °C cada día) · {es(r5['pct_autoconsumo'], 0)} % solar · al final la batería toca la reserva:"
                 f" {es(r5['coste_eur_dia'], 2)} €/día de red")
    ax = fig.add_axes([0.07, 0.36, 0.86, 0.42])
    ax.plot(h, s["temp_calle"], color=C["naranja"], lw=2.5, label="Calle"); ax.plot(h, s["temp_oasi"], color=C["azul"], lw=3, label="OASI")
    ax.set_ylabel("°C"); ax.set_xlim(0, 120); ax.set_xticks(range(0, 121, 24)); ax.set_xticklabels([]); ax.legend(frameon=False, ncol=2, loc="upper left")
    bx = fig.add_axes([0.07, 0.14, 0.86, 0.17])
    bx.plot(h, s["bateria"], color=C["aqua"], lw=2.5); bx.set_ylim(0, 105); bx.set_ylabel("batería %")
    bx.set_xlim(0, 120); bx.set_xticks(range(0, 121, 24)); bx.set_xticklabels([])
    for d in range(5):
        bx.text(24 * d + 12, -8, f"día {d + 1}", ha="center", va="top", color=SUAVE, fontsize=16)
    guardar(fig, "07_ola_de_calor_5_dias")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    D = simular_dia()
    R = dia(6.0, 2.4)["resumen"]
    d1_cifras(R, escenario()["resumen"]); d2_temperatura(D, R); d3_riesgo(D, R); d4_energia(D, R)
    d5_ventilacion(D); d6_tamanos(); d7_ola_5_dias()
    print("diapositivas en", SALIDA)


if __name__ == "__main__":
    main()

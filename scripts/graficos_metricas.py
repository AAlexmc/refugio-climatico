"""Gráficos de cómo se obtienen las métricas de la simulación (PNG para el pitch).

    env -u PYTHONPATH .venv/bin/python scripts/graficos_metricas.py   -> pitch/graficos/*.png

Usa EXACTAMENTE el mismo método que sim/metricas.py: el simulador (sim/clima.py + física del
pabellón sim/fisica_pabellon.py) y las reglas reales (control/reglas.py) en lazo cerrado sobre
un bus en memoria, paso de 30 s, muestreo cada 10 min. Aquí además se guarda la física paso a paso.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from control.reglas import MotorReglas  # noqa: E402
from nucleo.bus import Bus  # noqa: E402
from nucleo.confort import indice_calor  # noqa: E402
from nucleo.evento import Evento  # noqa: E402
from sim import clima, fisica_pabellon as fp  # noqa: E402
from sim.metricas import CTRL_S, EUR_KWH, KG_CO2_KWH, PASO_S, UMBRAL_RIESGO, aforo_en, dia  # noqa: E402

SALIDA = RAIZ / "pitch" / "graficos"
# paleta validada (skill dataviz, modo claro): azul, naranja, aqua, amarillo, magenta, verde, violeta
C = {"azul": "#2a78d6", "naranja": "#eb6834", "aqua": "#1baf7a", "amarillo": "#eda100",
     "magenta": "#e87ba4", "violeta": "#6250d6", "gris": "#77766f", "rojo": "#c52f2f"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5df",
                     "axes.edgecolor": "#9a998f", "axes.titleweight": "bold", "axes.titlesize": 12,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def simular_dia(largo: float = 6.0, ancho: float = 2.4) -> dict:
    """Un día (0-24 h) con la física guardada cada 10 min. Mismo lazo que sim.metricas._simular."""
    bus = Bus()
    MotorReglas_ = MotorReglas(bus, avisar=lambda r, m: None)
    bus.oyente(MotorReglas_.procesar)
    oasi = clima.FuenteClimaSim(inicio_hora=0.0, tipo="pabellon")
    oasi._modulos({"tipo": "pabellon", "largo": largo, "ancho": ancho})
    bus.oyente(oasi._oir)
    cerrado = clima.FuenteClimaSim(inicio_hora=0.0, tipo="pabellon")          # sin reglas: todo cerrado/apagado
    cerrado._modulos({"tipo": "pabellon", "largo": largo, "ancho": ancho})
    cap = oasi.aforo_max or 20
    R = {k: [] for k in ("h", "t_ext", "hr_ext", "rad", "t_int", "t_cerrado", "at_int", "at_ext", "ic_ext", "ic_int",
                         "viento", "dp_v", "dp_s", "q", "apertura", "ac", "neb", "ext", "solar", "consumo", "bat",
                         "aforo", "evap", "ac_w")}
    n_sub = round(PASO_S / CTRL_S)
    for i in range(int(86400 / PASO_S)):
        for j in range(n_sub):
            h = ((i * PASO_S + j * CTRL_S) / 3600.0) % 24
            a = aforo_en(h, cap)
            cerrado.aforo = a
            bus.publicar(Evento("aforo", a, "sim"))
            d = oasi.paso(CTRL_S)
            c = cerrado.paso(CTRL_S)
            for k in ("temp_ext", "temp", "humedad"):
                bus.publicar(Evento(k, d[k], "sim"))
        f = d["fisica"]
        R["h"].append((i + 1) * PASO_S / 3600.0)
        R["t_ext"].append(d["temp_ext"]); R["hr_ext"].append(d["humedad_ext"]); R["rad"].append(d["radiacion"])
        R["t_int"].append(d["temp"]); R["t_cerrado"].append(c["temp"])
        R["at_int"].append(f["t_aparente"]); R["at_ext"].append(f["t_aparente_ext"])
        R["ic_ext"].append(indice_calor(d["temp_ext"], d["humedad_ext"])); R["ic_int"].append(indice_calor(d["temp"], d["humedad"]))
        R["viento"].append(f["viento"]); R["dp_v"].append(f["dp_venturi"]); R["dp_s"].append(f["dp_chimenea"])
        R["q"].append(f["caudal_m3h"]); R["apertura"].append(d["claraboya"]); R["ac"].append(d["ac"])
        R["neb"].append(d["nebulizador"]); R["ext"].append(d["ventilador"]); R["evap"].append(f["evaporativo_w"])
        R["ac_w"].append(f.get("ac_w", 0) if d["ac"] else 0)
        R["solar"].append(d["solar"]); R["consumo"].append(d["potencia"]); R["bat"].append(d["bateria"]); R["aforo"].append(a)
    return {k: np.array(v, dtype=float) for k, v in R.items()}


def ejes_hora(ax):
    ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 3)); ax.set_xticklabels([f"{h}h" for h in range(0, 25, 3)])


def etiqueta_final(ax, x, y, txt, color):
    ax.annotate(txt, (x[-1], y[-1]), xytext=(4, 0), textcoords="offset points", va="center", color=color, fontsize=9, fontweight="bold")


def g1_entradas(D):
    fig, axs = plt.subplots(2, 2, figsize=(11, 6.2), sharex=True)
    fig.suptitle("1 · Entradas del escenario: ola de calor tipo Barcelona (julio) — datos SUPUESTOS, no medidos", fontweight="bold")
    series = [(axs[0, 0], D["t_ext"], "Temperatura exterior (°C)", C["naranja"], "26 °C a las 4-5 h, 36 °C a las 16 h (senoide)"),
              (axs[0, 1], D["hr_ext"], "Humedad relativa exterior (%)", C["azul"], "35 % por la tarde, 75 % de madrugada"),
              (axs[1, 0], D["rad"], "Radiación solar (W/m²)", C["amarillo"], "media senoide 6:30-20:30, pico 850"),
              (axs[1, 1], D["viento"], "Viento (m/s)", C["aqua"], "brisa marina: 1,5 de noche, ~4 a media tarde")]
    for ax, y, tit, col, nota in series:
        ax.plot(D["h"], y, color=col, lw=2); ax.set_title(tit, loc="left"); ejes_hora(ax)
        ax.text(0.99, 0.96, nota, transform=ax.transAxes, fontsize=8.5, color=C["gris"], ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85))
    fig.savefig(SALIDA / "1_entradas.png"); plt.close(fig)


def g2_temperaturas(D, R):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(D["h"], D["t_cerrado"], color=C["amarillo"], lw=2, label="Pabellón cerrado y sin control")
    ax.plot(D["h"], D["t_ext"], color=C["naranja"], lw=2, label="Calle (temperatura)")
    ax.plot(D["h"], D["at_ext"], color=C["naranja"], lw=1.5, ls="--", label="Calle (sensación)")
    ax.plot(D["h"], D["t_int"], color=C["azul"], lw=2.4, label="OASI dentro (temperatura)")
    ax.plot(D["h"], D["at_int"], color=C["violeta"], lw=1.6, ls="--", label="OASI dentro (sensación)")
    i = int(np.argmax(D["t_ext"] - D["t_int"] + (D["rad"] <= 0) * -99))
    ax.annotate("", xy=(D["h"][i], D["t_int"][i]), xytext=(D["h"][i], D["t_ext"][i]), arrowprops=dict(arrowstyle="<->", color="#333", lw=1.4))
    ax.text(D["h"][i] + 0.3, (D["t_int"][i] + D["t_ext"][i]) / 2, f"{D['t_ext'][i] - D['t_int'][i]:.1f} °C\n«grados reducidos\nen el pico»",
            fontsize=9, va="center")
    ax.set_title(f"2 · Temperaturas en 24 h · pabellón 6 × 2,4 m   (pico −{R['grados_reducidos_pico']:.1f} °C)", loc="left")
    ax.set_ylabel("°C"); ejes_hora(ax); ax.legend(ncol=3, fontsize=8.8, loc="upper left", frameon=False)
    fig.savefig(SALIDA / "2_temperaturas.png"); plt.close(fig)


def g3_riesgo(D):
    paso_h = PASO_S / 3600.0
    hc, hi = (D["ic_ext"] > UMBRAL_RIESGO).sum() * paso_h, (D["ic_int"] > UMBRAL_RIESGO).sum() * paso_h
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [3, 1]})
    a1.plot(D["h"], D["ic_ext"], color=C["naranja"], lw=2, label="Calle")
    a1.plot(D["h"], D["ic_int"], color=C["azul"], lw=2, label="OASI dentro")
    a1.axhline(UMBRAL_RIESGO, color=C["rojo"], lw=1.2, ls=":")
    a1.fill_between(D["h"], UMBRAL_RIESGO, D["ic_ext"], where=D["ic_ext"] > UMBRAL_RIESGO, color=C["naranja"], alpha=0.15)
    a1.text(0.3, UMBRAL_RIESGO + 0.4, f"umbral de riesgo: índice de calor > {UMBRAL_RIESGO:.0f} °C (NOAA)", color=C["rojo"], fontsize=8.5)
    a1.set_title("3 · Índice de calor NOAA (temperatura + humedad)", loc="left"); a1.set_ylabel("°C"); ejes_hora(a1); a1.legend(frameon=False)
    b = a2.bar(["Calle", "OASI"], [hc, hi], color=[C["naranja"], C["azul"]], width=0.6)
    a2.bar_label(b, fmt="%.1f h", fontweight="bold"); a2.set_title("Horas de riesgo / día", loc="left"); a2.grid(axis="x", visible=False)
    a2.text(0.5, -0.22, f"evitadas = {hc - hi:.1f} h", transform=a2.transAxes, ha="center", fontweight="bold")
    fig.savefig(SALIDA / "3_horas_riesgo.png"); plt.close(fig)


def g4_ventilacion(D):
    fig, axs = plt.subplots(3, 1, figsize=(11, 7.6), sharex=True, gridspec_kw={"height_ratios": [1.2, 1, 0.6]})
    axs[0].fill_between(D["h"], 0, D["q"], color=C["aqua"], alpha=0.35, step="pre")
    axs[0].plot(D["h"], D["q"], color=C["aqua"], lw=2, drawstyle="steps-pre")
    axs[0].set_title("4 · Ventilación natural: caudal de aire renovado (m³/h)", loc="left")
    axs[0].text(0.01, 0.82, "Q = Cd·A_eff·√(2·Δp/ρ)  ·  rejillas bajas y garganta en serie", transform=axs[0].transAxes, fontsize=9)
    axs[1].plot(D["h"], D["dp_v"], color=C["violeta"], lw=2, label="Succión Venturi ½ρv²(K²−1), K = 1,6 (solo con garganta abierta)")
    axs[1].plot(D["h"], D["dp_s"], color=C["naranja"], lw=2, label="Tiro térmico ρ·g·H·ΔT/T")
    axs[1].axhline(0, color="#999", lw=0.8); axs[1].set_ylabel("Pa"); axs[1].legend(frameon=False, fontsize=8.6, loc="upper right")
    axs[1].set_title("Presiones que mueven el aire", loc="left")
    est = np.vstack([D["apertura"], D["ac"], D["neb"], D["ext"]])
    axs[2].imshow(est, aspect="auto", extent=(0, 24, 3.5, -0.5), cmap="Greens", vmin=0, vmax=1.3, interpolation="nearest")
    axs[2].set_yticks(range(4)); axs[2].set_yticklabels(["Garganta abierta", "AC", "Nebulizador", "Extractores"])
    axs[2].grid(False); axs[2].set_title("Decisiones del control (verde = encendido/abierto)", loc="left"); ejes_hora(axs[2])
    fig.savefig(SALIDA / "4_ventilacion.png"); plt.close(fig)


def g5_energia(D, R):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True)
    a1.fill_between(D["h"], 0, D["solar"], color=C["aqua"], alpha=0.25)
    a1.plot(D["h"], D["solar"], color=C["aqua"], lw=2, label="Placas FV curvas (W)")
    a1.plot(D["h"], D["consumo"], color=C["naranja"], lw=2, label="Consumo: control + AC + extractores + bombas (W)")
    a1.set_title(f"5 · Energía · {R['kwh_solares']:.1f} kWh solares/día · autoconsumo {R['pct_autoconsumo']:.0f} % · red {R['coste_eur_dia']:.2f} €/día",
                 loc="left"); a1.set_ylabel("W"); a1.legend(frameon=False)
    a2.plot(D["h"], D["bat"], color=C["azul"], lw=2.2); a2.axhline(clima.BAT_RESERVA, color=C["rojo"], ls=":", lw=1.2)
    a2.text(0.2, clima.BAT_RESERVA + 2, f"reserva {clima.BAT_RESERVA:.0f} % (control + alerta 061)", color=C["rojo"], fontsize=8.5)
    a2.set_ylim(0, 105); a2.set_ylabel("%"); a2.set_title("Batería: sol → batería → consumo; red solo por debajo de la reserva", loc="left"); ejes_hora(a2)
    fig.savefig(SALIDA / "5_energia.png"); plt.close(fig)


def g6_tamanos():
    combos = [(l, a) for a in fp.ANCHOS for l in fp.LARGOS]
    filas = []
    for l, a in combos:
        r = dia(l, a)
        filas.append((l, a, r["resumen"], r["pabellon"]["aforo_max"]))
    fig, axs = plt.subplots(1, 3, figsize=(12.5, 4.4))
    cols = {2.4: C["azul"], 3.6: C["aqua"], 4.8: C["violeta"]}
    for a in fp.ANCHOS:
        xs = [l for l, aa, _, _ in filas if aa == a]
        axs[0].plot(xs, [r["kwh_solares"] for l, aa, r, _ in filas if aa == a], "o-", color=cols[a], label=f"ancho {a:.1f} m".replace(".", ","))
        axs[1].plot(xs, [r["autonomia_h"] for l, aa, r, _ in filas if aa == a], "o-", color=cols[a])
        axs[2].plot(xs, [c for l, aa, _, c in filas if aa == a], "o-", color=cols[a])
    for ax, t in zip(axs, ["Solar (kWh/día)", "Autonomía batería (h)", "Aforo (1,5 m²/pers.)"]):
        ax.set_title(t, loc="left"); ax.set_xlabel("largo (m)"); ax.set_xticks(fp.LARGOS)
    axs[0].legend(frameon=False)
    fig.suptitle("6 · Ampliar a lo largo y a lo ancho: misma simulación de 24 h para cada tamaño", fontweight="bold", x=0.01, ha="left", y=1.03)
    fig.tight_layout()
    fig.savefig(SALIDA / "6_tamanos.png"); plt.close(fig)


def g7_modelo():
    p = fp.Pabellon()
    v = np.linspace(0, 6, 61)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.3))
    for ap, col in [(0.25, C["amarillo"]), (0.5, C["aqua"]), (1.0, C["azul"])]:
        a1.plot(v, [fp.caudal(p, 30, 30, x, ap, False)["caudal"] * 3600 for x in v], color=col, lw=2, label=f"garganta {int(ap * 100)} %")
    a1.axhline(p.extractores * fp.Q_EXTRACTOR * 3600, color=C["gris"], ls="--", lw=1.2)
    a1.text(0.1, p.extractores * fp.Q_EXTRACTOR * 3600 + 120, "3 extractores (sin viento)", fontsize=8.5, color=C["gris"])
    a1.set_title("7a · Modelo: caudal según viento (6 × 2,4 m)", loc="left"); a1.set_xlabel("viento (m/s)"); a1.set_ylabel("m³/h"); a1.legend(frameon=False)
    hr = np.linspace(20, 95, 76)
    for t, col in [(30, C["aqua"]), (35, C["naranja"])]:
        a2.plot(hr, [fp.enfriamiento_evaporativo(p, 0.8, t, x, True) / 1000 for x in hr], color=col, lw=2, label=f"{t} °C")
    a2.set_title("7b · Nebulización: frío útil cae con la humedad", loc="left"); a2.set_xlabel("humedad relativa (%)"); a2.set_ylabel("kW")
    a2.text(0.02, 0.05, "límite: no se enfría por debajo del bulbo húmedo (Stull 2011)", transform=a2.transAxes, fontsize=8.5, color=C["gris"])
    a2.legend(frameon=False)
    fig.savefig(SALIDA / "7_modelo_fisico.png"); plt.close(fig)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    D = simular_dia()
    R = dia(6.0, 2.4)["resumen"]
    g1_entradas(D); g2_temperaturas(D, R); g3_riesgo(D); g4_ventilacion(D); g5_energia(D, R); g6_tamanos(); g7_modelo()
    print("resumen 6 × 2,4 m:", R)
    print("constantes: umbral riesgo", UMBRAL_RIESGO, "°C · precio", EUR_KWH, "€/kWh · CO₂", KG_CO2_KWH, "kg/kWh")
    print("gráficos en", SALIDA)


if __name__ == "__main__":
    main()

import asyncio

from nucleo.bus import Bus
from vision.pose_sim import X_RANGO, Y_RANGO, FuentePoseSim


def test_esqueleto_forma_y_rangos():
    s = FuentePoseSim(semilla=1)
    for t in (0, 5, 17.3, 33):
        pts = s.puntos(t)
        assert len(pts) == 33 and all(len(p) == 3 for p in pts)
        assert X_RANGO[0] - 0.4 <= pts[23][0] <= X_RANGO[1] + 0.4
        assert Y_RANGO[0] - 0.4 <= pts[23][1] <= Y_RANGO[1] + 0.4
    assert 0.8 < s.puntos(0)[23][2] < 1.0


def test_determinista_con_semilla():
    assert FuentePoseSim(semilla=3).puntos(12.0) == FuentePoseSim(semilla=3).puntos(12.0)
    assert FuentePoseSim(semilla=3).puntos(12.0) != FuentePoseSim(semilla=4).puntos(12.0)


def test_ciclo_sincrono_caida_true_luego_false():
    s = FuentePoseSim(periodo_caida=5.0, semilla=0)
    cambios = []
    for k in range(180):
        for ev in s.paso(k * 0.1):
            if ev.tipo == "caida":
                cambios.append((k * 0.1, ev.valor))
    assert [v for _, v in cambios] == [True, False]
    assert 5.0 < cambios[0][0] < 7.0   # detecta < 2 s tras empezar la caída


def test_sin_caida_antes_del_periodo():
    s = FuentePoseSim(periodo_caida=50.0)
    assert not any(ev.tipo == "caida" for k in range(400) for ev in s.paso(k * 0.1))


async def test_correr_publica_pose_y_caida_en_bus():
    bus = Bus()
    sim = FuentePoseSim(periodo_caida=2.0, fps=100, velocidad=10.0)
    caidas, poses = [], 0

    async def consumir():
        nonlocal poses
        async for ev in bus.suscribir():
            if ev.tipo == "pose":
                poses += 1
                assert len(ev.valor["puntos"]) == 33 and "cadera_z" in ev.valor
            if ev.tipo == "caida":
                caidas.append(ev.valor)
                if len(caidas) == 2:
                    return

    tarea = asyncio.create_task(sim.correr(bus))
    try:
        await asyncio.wait_for(consumir(), timeout=3.0)
    finally:
        tarea.cancel()
    assert caidas == [True, False]
    assert poses > 10


def test_forzar_caida_y_levantarse():
    from vision.pose_sim import FuentePoseSim
    from vision.caidas import cadera_z
    f = FuentePoseSim(periodo_caida=40.0)
    f._t = 5.0
    f.forzar(True)
    assert f._t == 40.0                                  # empieza a caer ya
    f._t += 3.0
    assert cadera_z(f.puntos(f._t)) < 0.45               # en el suelo
    f.forzar(False)
    assert cadera_z(f.puntos(f._t)) > 0.7                # de pie
    f.forzar(False)                                      # idempotente de pie
    assert cadera_z(f.puntos(f._t)) > 0.7


def test_mira_hacia_donde_camina_y_lado_izquierdo_real():
    """Marco habitación dextrógiro (z arriba): izquierda × arriba = adelante.
    Con el esqueleto espejado el gemelo pinta al refugio andando de espaldas."""
    import numpy as np
    s = FuentePoseSim(semilla=0)
    for t in (1.0, 5.0, 12.0, 20.0):
        p = np.array(s.puntos(t))
        p2 = np.array(s.puntos(t + 0.1))
        mov = (p2[23] + p2[24]) / 2 - (p[23] + p[24]) / 2
        mov[2] = 0
        izq = p[23] - p[24]
        adelante = np.cross(izq, [0.0, 0.0, 1.0])
        assert adelante @ mov > 0                       # camina hacia delante
        nariz = p[0] - (p[11] + p[12]) / 2
        assert adelante @ nariz > 0                     # la cara mira adelante

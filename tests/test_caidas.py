import math

from vision.caidas import DetectorCaidas
from sim.pose_sim import esqueleto

DT = 0.1


def pose(z_cadera, incl_deg=0.0):
    """Esqueleto con la cadera a z_cadera y torso inclinado incl_deg de la vertical."""
    p = esqueleto((0.0, 2.0), 0.0, 0.0)
    a = math.radians(incl_deg)
    for i in (11, 12):  # hombros: 0,49 m sobre la cadera
        p[i][1] = 2.0 + 0.49 * math.sin(a)
        p[i][2] = z_cadera + 0.49 * math.cos(a)
    for i in (23, 24):
        p[i][1], p[i][2] = 2.0, z_cadera
    return p


def correr(det, serie, t0=0.0):
    """serie: lista de (z, incl) o None, una por DT. Devuelve [(t, cambio)]."""
    out = []
    for k, e in enumerate(serie):
        t = t0 + k * DT
        r = det.actualizar(t, None if e is None else pose(*e))
        if r is not None:
            out.append((round(t, 2), r))
    return out


def rampa(z0, z1, i0, i1, dur):
    n = int(round(dur / DT))
    return [(z0 + (z1 - z0) * k / n, i0 + (i1 - i0) * k / n) for k in range(1, n + 1)]


def de_pie(seg):
    return [(0.95, 0.0)] * int(round(seg / DT))


def test_caida_rapida_detecta_en_menos_de_2s():
    det = DetectorCaidas()
    serie = de_pie(2) + rampa(0.95, 0.15, 0, 90, 0.6) + [(0.15, 90)] * 20
    ev = correr(det, serie)
    assert ev and ev[0][1] is True
    assert ev[0][0] - 2.0 < 2.0


def test_tumbarse_lento_no_dispara():
    det = DetectorCaidas()
    serie = de_pie(2) + rampa(0.95, 0.15, 0, 90, 8.0) + [(0.15, 90)] * 100
    assert correr(det, serie) == []
    assert det.caida is False


def test_sentarse_rapido_no_dispara():
    det = DetectorCaidas()  # cadera baja pero torso vertical
    serie = de_pie(2) + rampa(0.95, 0.40, 0, 5, 0.5) + [(0.40, 5)] * 50
    assert correr(det, serie) == []


def test_levantarse_resetea():
    det = DetectorCaidas()
    serie = (de_pie(1) + rampa(0.95, 0.15, 0, 90, 0.6) + [(0.15, 90)] * 20
             + rampa(0.15, 0.95, 90, 0, 1.0) + de_pie(3))
    ev = correr(det, serie)
    assert [c for _, c in ev] == [True, False]


def test_oclusion_en_el_suelo_no_resetea():
    det = DetectorCaidas()
    serie = de_pie(1) + rampa(0.95, 0.15, 0, 90, 0.6) + [(0.15, 90)] * 20
    correr(det, serie)
    assert det.caida is True
    assert correr(det, [None] * 100, t0=10.0) == []
    assert det.caida is True


def test_oclusion_durante_suelo_no_impide_detectar():
    det = DetectorCaidas()
    serie = (de_pie(1) + rampa(0.95, 0.15, 0, 90, 0.6) + [(0.15, 90)] * 3 + [None] * 5
             + [(0.15, 90)] * 20)
    assert [c for _, c in correr(det, serie)] == [True]


def test_suelo_menos_de_1s_no_dispara():
    det = DetectorCaidas()
    serie = de_pie(1) + rampa(0.95, 0.15, 0, 90, 0.6) + [(0.15, 90)] * 5 + de_pie(3)
    assert correr(det, serie) == []

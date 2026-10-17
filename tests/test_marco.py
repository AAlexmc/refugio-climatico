import math

import numpy as np
import pytest

from vision.marco import MarcoHabitacion, webcam_a_camara


def hab_a_cam(p, altura, pitch):
    """Inversa de a_habitacion, escrita aparte para contrastar."""
    s, c = math.sin(pitch), math.cos(pitch)
    x, y, z = p
    dz = z - altura
    return [x, -y * s - dz * c, y * c - dz * s]


def test_sin_pitch_eje_optico_es_y():
    m = MarcoHabitacion(altura=2.0, pitch=0.0)
    assert np.allclose(m.a_habitacion([0.3, 0.0, 3.0]), [0.3, 3.0, 2.0])


def test_punto_conocido_con_pitch():
    # cámara a 2 m, pitch 30 deg: punto sobre el eje óptico a 2 m de distancia
    m = MarcoHabitacion(altura=2.0, pitch=math.radians(30))
    p = m.a_habitacion([0.0, 0.0, 2.0])
    assert np.allclose(p, [0.0, 2 * math.cos(math.radians(30)), 1.0])


def test_roundtrip_suelo():
    m = MarcoHabitacion(altura=2.0, pitch=math.radians(30))
    suelo = [0.2, 2.5, 0.0]
    assert np.allclose(m.a_habitacion(hab_a_cam(suelo, 2.0, math.radians(30))), suelo)


def test_autocalibrar_plano_recupera_altura_y_pitch():
    altura, pitch = 2.3, math.radians(25)
    tobillos = [[-0.5, 2.0, 0.08], [0.6, 3.0, 0.08], [0.1, 4.0, 0.08], [-0.3, 2.5, 0.08]]
    m = MarcoHabitacion()
    m.autocalibrar([hab_a_cam(p, altura, pitch) for p in tobillos])
    assert m.altura == pytest.approx(altura, abs=1e-6)
    assert m.pitch == pytest.approx(pitch, abs=1e-6)


def test_autocalibrar_un_punto_solo_altura():
    m = MarcoHabitacion(altura=1.0, pitch=0.0)
    m.autocalibrar([[0.0, 1.5, 3.0]])    # 1,5 m por debajo de la cámara
    assert m.altura == pytest.approx(1.5 + 0.08)
    assert m.a_habitacion([0.0, 1.5, 3.0])[2] == pytest.approx(0.08)


def test_webcam_profundidad_inversa_al_tamano():
    lm = np.full((33, 3), 0.5)
    lm[0] = [0.5, 0.2, 0]            # nariz
    lm[27] = lm[28] = [0.5, 0.8, 0]  # tobillos: 0,6 del alto de imagen
    z1 = webcam_a_camara(lm)[0, 2]
    lm[0, 1] = 0.5                   # tamaño en imagen 0,3 = la mitad -> doble distancia
    lm[27, 1] = lm[28, 1] = 0.8
    z2 = webcam_a_camara(lm)[0, 2]
    assert z2 == pytest.approx(z1 * 2)


def test_webcam_sin_persona_falla():
    with pytest.raises(ValueError):
        webcam_a_camara(np.full((33, 3), 0.5))

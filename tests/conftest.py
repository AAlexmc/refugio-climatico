import pytest

from vision import calibracion


@pytest.fixture(autouse=True)
def _calibracion_aislada(tmp_path, monkeypatch):
    """Ningún test lee ni escribe la calibración real de datos/."""
    monkeypatch.setattr(calibracion, "RUTA", tmp_path / "caida_calibracion.json")

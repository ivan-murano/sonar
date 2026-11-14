"""Regressione: i risultati della ricerca città devono essere gestiti nel thread dell'interfaccia."""
import os
import time

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_lookup_callbacks_run_in_gui_thread(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv('SONAR_HOME', str(tmp_path / 'home'))
    from sonar_app import places
    from sonar_app.ui import app as ui

    candidate = places.Candidate(name='Prova', label='Prova, Italia', lat=40.85, lon=14.25, country_code='IT', kind='city', importance=0.9)
    city = places.City(name='Prova', country_code='IT', lat=40.85, lon=14.25, lau_id='000001', gisco_id='IT_000001',
                       lau_name='Prova', lau_year=2024, area_km2=12.0, geometry={})
    monkeypatch.setattr(places, 'search', lambda query, language='it', limit=10: [candidate])
    monkeypatch.setattr(places, 'resolve_boundary', lambda cand, progress=None: city)

    gui_thread = QApplication.instance().thread()
    calls = []

    def guarded(name):
        original = getattr(ui.MainWindow, name)

        def wrapper(self, *args, **kwargs):
            in_gui = QThread.currentThread() == gui_thread
            calls.append((name, in_gui))
            if in_gui:  # fuori dal thread GUI non tocchiamo i widget: il test fallisce senza bloccarsi
                return original(self, *args, **kwargs)
        return wrapper

    for name in ('on_candidates', 'on_city', 'on_lookup_error'):
        monkeypatch.setattr(ui.MainWindow, name, guarded(name))

    window = ui.MainWindow()
    try:
        window.search.edit.setText('Prova')
        window.lookup(then_start=False)
        deadline = time.monotonic() + 5
        while window.city is None and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        window.pool.waitForDone(2000)
        qapp.processEvents()

        assert calls and all(in_gui for _, in_gui in calls), calls
        assert [name for name, _ in calls] == ['on_candidates', 'on_city']
        assert window.city is city
        assert not window.busy_lookup
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()

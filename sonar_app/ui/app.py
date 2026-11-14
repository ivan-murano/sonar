"""Finestra principale di Sonar."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QRunnable, QThreadPool, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, __version__, config, places
from ..i18n import DEFAULT_LANGUAGE, LANGUAGES, t
from ..worker import EVENT_PREFIX
from .widgets import (THEMES, Frame, IconButton, LanguageToggle, Logo, ProgressLine, SearchBar, ThemeToggle, font, load_fonts)


def style_sheet(c) -> str:
    return f"""
    QWidget {{ color: {c['fg']}; }}
    QLabel#subtitle {{ font-size: 12px; }}
    QLabel#status {{ font-size: 12px; font-weight: 600; }}
    QLabel#detail {{ font-size: 11px; color: {c['muted']}; }}
    QLabel#error {{ font-size: 12px; font-weight: 600; color: {c['error']}; }}
    QPushButton#link {{ border: 2px solid {c['fg']}; border-radius: 7px; background: transparent; padding: 3px 12px; font-size: 12px; font-weight: 700; }}
    QPushButton#link:hover {{ background: {c['soft']}; }}
    QListWidget {{ border: 2px solid {c['fg']}; border-radius: 8px; background: {c['bg']}; font-size: 12px; padding: 4px; outline: 0; }}
    QListWidget::item {{ padding: 6px; border-radius: 5px; }}
    QListWidget::item:selected {{ background: {c['fg']}; color: {c['bg']}; }}
    QToolTip {{ color: {c['bg']}; background: {c['fg']}; border: none; padding: 4px; }}
    """


class Movable:
    """Finestra senza cornice di sistema spostata trascinando lo sfondo."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)


class Dialog(Movable, QDialog):
    def __init__(self, parent, title, message, choices=None, ok='OK', cancel=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        frame = Frame(self); frame.set_theme(parent.colors)
        self.setStyleSheet(style_sheet(parent.colors))
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(frame)
        lay = QVBoxLayout(frame); lay.setContentsMargins(30, 26, 30, 24); lay.setSpacing(12)
        head = QLabel(title); head.setFont(font(18, QFont.Weight.Bold)); lay.addWidget(head)
        text = QLabel(message); text.setWordWrap(True); text.setFont(font(12.5, QFont.Weight.DemiBold)); lay.addWidget(text)
        self.list = None
        if choices:
            self.list = QListWidget(); self.list.setFont(font(12.5))
            for value, label in choices:
                item = QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole, value); self.list.addItem(item)
            self.list.setCurrentRow(0); self.list.setMinimumHeight(170)
            self.list.itemDoubleClicked.connect(lambda _: self.accept())
            lay.addWidget(self.list)
        row = QHBoxLayout(); row.addStretch(1)
        for label, slot in ((cancel, self.reject), (ok, self.accept)):
            if label:
                b = QPushButton(label); b.setObjectName('link'); b.setFont(font(12.5, QFont.Weight.Bold))
                b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(slot); row.addWidget(b)
        lay.addLayout(row)
        self.resize(540 if choices else 420, self.sizeHint().height())

    def value(self):
        item = self.list.currentItem() if self.list else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None


class Task(QRunnable):
    """Funzione eseguita fuori dal thread dell'interfaccia (ricerca e confine)."""

    class Signals(QObject):
        finished = Signal(object, object)  # (task, risultato)
        failed = Signal(object, object)    # (task, eccezione)

    def __init__(self, function, *args):
        super().__init__()
        # Il riferimento resta a chi avvia il Task (MainWindow._tasks) finché il segnale non è consegnato.
        self.setAutoDelete(False)
        self.function, self.args, self.signals = function, args, Task.Signals()

    def run(self):
        try:
            result = self.function(*self.args)
        except BaseException as exc:  # anche SystemExit & co.: l'interfaccia non deve restare in attesa
            self.signals.failed.emit(self, exc)
        else:
            self.signals.finished.emit(self, result)


def worker_command(job_file: Path) -> tuple[str, list[str]]:
    if config.frozen():
        return sys.executable, ['--worker', str(job_file)]
    return sys.executable, ['-m', 'sonar_app.worker', str(job_file)]


class MainWindow(Movable, QWidget):
    def __init__(self):
        super().__init__()
        settings = config.load_settings()
        self.language = settings.get('language') if settings.get('language') in LANGUAGES else DEFAULT_LANGUAGE
        self.theme = settings.get('theme')
        if self.theme not in THEMES:
            hints = QGuiApplication.styleHints()
            self.theme = 'dark' if hasattr(hints, 'colorScheme') and hints.colorScheme() == Qt.ColorScheme.Dark else 'light'
        self.colors = THEMES[self.theme]
        self.city: places.City | None = None
        self.city_query = ''
        self.process: QProcess | None = None
        self.result_folder = None
        self.log_tail: list[str] = []
        self.error = None
        self.busy_lookup = False
        self.pool = QThreadPool.globalInstance()
        self._tasks: set[Task] = set()
        self._current_task: Task | None = None
        self._then_start = False

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(640, 360)
        self.frame = Frame(self)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(self.frame)
        self.btn_min = IconButton('min', self.frame); self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = IconButton('close', self.frame); self.btn_close.clicked.connect(self.close)
        self.theme_toggle = ThemeToggle(self.frame)
        self.theme_toggle.switched.connect(lambda i: self.apply_theme(('light', 'dark')[i], True))
        self.lang_toggle = LanguageToggle(self.frame)
        self.lang_toggle.switched.connect(lambda i: self.apply_language(LANGUAGES[i], True))

        lay = QVBoxLayout(self.frame); lay.setContentsMargins(40, 44, 40, 26); lay.setSpacing(0)
        self.logo = Logo(); lay.addWidget(self.logo)
        self.subtitle = QLabel(); self.subtitle.setObjectName('subtitle'); self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setFont(font(12.5, QFont.Weight.Medium, 0.4)); lay.addWidget(self.subtitle); lay.addSpacing(22)
        self.search = SearchBar()
        self.search.activated.connect(self.on_start)
        self.search.submitted.connect(self.on_submit)
        self.search.edit.textEdited.connect(self.on_text_edited)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(self.search); row.addStretch(1); lay.addLayout(row); lay.addSpacing(16)

        self.status_box = QWidget(); sb = QVBoxLayout(self.status_box); sb.setContentsMargins(0, 0, 0, 0); sb.setSpacing(6)
        self.progress = ProgressLine(); self.progress.setFixedWidth(332)
        prow = QHBoxLayout(); prow.addStretch(1); prow.addWidget(self.progress); prow.addStretch(1); sb.addLayout(prow)
        self.status = QLabel(); self.status.setObjectName('status'); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(font(12.5, QFont.Weight.DemiBold))
        self.detail = QLabel(); self.detail.setObjectName('detail'); self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setFont(font(11.5)); self.detail.setFixedWidth(500)
        sb.addWidget(self.status, 0, Qt.AlignmentFlag.AlignHCenter); sb.addWidget(self.detail, 0, Qt.AlignmentFlag.AlignHCenter)
        self.action = QPushButton(); self.action.setObjectName('link'); self.action.setFont(font(12.5, QFont.Weight.Bold))
        self.action.setCursor(Qt.CursorShape.PointingHandCursor); self.action.clicked.connect(self.on_action); self.action.hide()
        sb.addSpacing(2); sb.addWidget(self.action, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.status_box); self.status_box.hide(); lay.addStretch(1)

        self.apply_theme(self.theme)
        self.apply_language(self.language)
        self.search.edit.setText(settings.get('last_city', ''))

    # ---------------------------------------------------------------- aspetto e lingua
    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        self.btn_close.move(w - 14 - self.btn_close.width(), 14)
        self.btn_min.move(w - 14 - self.btn_close.width() - 4 - self.btn_min.width(), 14)
        self.theme_toggle.move(w - 18 - self.theme_toggle.width(), h - 18 - self.theme_toggle.height())
        self.lang_toggle.move(self.theme_toggle.x() - 8 - self.lang_toggle.width(), self.theme_toggle.y())
        super().resizeEvent(event)

    def apply_theme(self, theme, animate=False):
        self.theme, self.colors = theme, THEMES[theme]
        config.save_settings({'theme': theme})
        self.setStyleSheet(style_sheet(self.colors))
        for widget in (self.frame, self.logo, self.btn_min, self.btn_close, self.progress, self.search, self.theme_toggle, self.lang_toggle):
            widget.set_theme(self.colors)
        self.theme_toggle.set_index(0 if theme == 'light' else 1, animate)

    def apply_language(self, language, animate=False):
        self.language = language
        config.save_settings({'language': language})
        self.lang_toggle.set_index(LANGUAGES.index(language), animate)
        self.subtitle.setText(t('subtitle', language))
        self.search.edit.setPlaceholderText(t('placeholder', language))
        self.search.set_button(t('cancel' if self.process else 'start', language), not self.busy_lookup)
        self.btn_min.setToolTip(t('minimize', language)); self.btn_close.setToolTip(t('close', language))
        self.theme_toggle.setToolTip(t('theme_tip', language)); self.lang_toggle.setToolTip(t('language_tip', language))
        if self.city and not self.process and not self.result_folder:
            self.show_city()
        if self.action.isVisible():
            self.action.setText(t('open_folder' if self.action.property('mode') == 'open' else 'open_log', language))

    # ---------------------------------------------------------------- stato
    def show_status(self, text, detail='', progress=None, error=False, busy=True):
        self.status_box.show()
        self.status.setObjectName('error' if error else 'status')
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.status.setText(text)
        self.detail.setText(self.detail.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideMiddle, self.detail.width()))
        self.detail.setToolTip(detail)
        if progress is None:
            self.progress.hide()
        else:
            self.progress.show(); self.progress.set_value(progress, busy)

    def show_city(self):
        c = self.city
        area = f'{c.area_km2:,.0f}' if self.language == 'en' else f'{c.area_km2:,.0f}'.replace(',', '.')
        self.show_status(t('city_found', self.language, name=c.name, country=c.country_code, area=area),
                         t('city_hint', self.language, lau=c.gisco_id or c.lau_id, year=c.lau_year))
        self.action.hide()

    def set_lookup(self, busy: bool):
        self.busy_lookup = busy
        self.search.edit.setEnabled(not busy)
        self.search.set_button(t('start', self.language), not busy)

    # ---------------------------------------------------------------- ricerca della città
    def on_text_edited(self, _):
        if self.city is not None and self.search.edit.text().strip() != self.city_query:
            self.city = None
            self.status_box.hide()

    def on_submit(self):
        if not self.process:
            self.lookup(then_start=False)

    def on_start(self):
        if self.process:
            self.confirm_cancel()
            return
        query = ' '.join(self.search.edit.text().split())
        if self.city is not None and query == self.city_query:
            self.choose_folder_and_run()
        else:
            self.lookup(then_start=True)

    def lookup(self, then_start: bool):
        query = ' '.join(self.search.edit.text().split())
        if not query:
            self.show_status(t('type_city', self.language), error=True); return
        self.result_folder = None
        self.city, self.city_query = None, query
        self.set_lookup(True)
        self.show_status(t('searching', self.language), query, progress=0.0)
        self._then_start = then_start
        self.start_task(self.on_candidates, places.search, query, self.language)

    def start_task(self, on_finished, function, *args):
        """Avvia function nel pool; on_finished/on_lookup_error girano sempre nel thread GUI (connessione accodata)."""
        task = Task(function, *args)
        task.signals.finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
        task.signals.failed.connect(self.on_lookup_error, Qt.ConnectionType.QueuedConnection)
        self._tasks.add(task)
        self._current_task = task
        self.pool.start(task)

    def take_task(self, task) -> bool:
        """Rilascia il Task consegnato; False se è il risultato di una ricerca superata."""
        self._tasks.discard(task)
        return task is self._current_task

    def on_candidates(self, task, found):
        if not self.take_task(task):
            return
        if not found:
            self.set_lookup(False); self.show_status(t('not_found', self.language), self.city_query, error=True); return
        candidate = found[0]
        if len(found) > 1 and (found[0].importance - found[1].importance < 0.15 or found[0].name.lower() != self.city_query.split(',')[0].strip().lower()):
            dialog = Dialog(self, t('choose_city_title', self.language), t('choose_city_text', self.language),
                            [(i, c.label) for i, c in enumerate(found)], ok=t('use', self.language), cancel=t('cancel', self.language))
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.value() is None:
                self.set_lookup(False); self.status_box.hide(); return
            candidate = found[dialog.value()]
        self.show_status(t('boundary_loading', self.language), candidate.label, progress=0.0)
        self.start_task(self.on_city, places.resolve_boundary, candidate)

    def on_city(self, task, city):
        if not self.take_task(task):
            return
        self._current_task = None
        self.set_lookup(False)
        if city is None:
            self.show_status(t('not_europe', self.language), self.city_query, error=True); return
        self.city = city
        self.search.edit.setText(city.name)
        self.city_query = city.name
        config.save_settings({'last_city': city.name})
        self.show_city()
        if self._then_start:
            self.choose_folder_and_run()

    def on_lookup_error(self, task, exc):
        import traceback
        if not self.take_task(task):
            return
        self._current_task = None
        self.set_lookup(False)
        self.log_tail = traceback.format_exception(exc)
        self.save_error_log()
        self.action.setProperty('mode', 'log'); self.action.setText(t('open_log', self.language)); self.action.show()
        self.show_status(t('network_error', self.language), f'{type(exc).__name__}: {exc}', error=True)
        self.action.show()

    # ---------------------------------------------------------------- lavoro
    def choose_folder_and_run(self):
        settings = config.load_settings()
        start = settings.get('last_folder') or str(Path.home())
        target = QFileDialog.getExistingDirectory(self, t('choose_folder', self.language), start, QFileDialog.Option.ShowDirsOnly)
        if not target:
            return
        config.save_settings({'last_folder': target})
        job = {'city': self.city.to_json(), 'out_dir': target, 'language': self.language}
        job_file = config.runs_dir() / f'job_{os.getpid()}.json'
        job_file.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        self.result_folder, self.error, self.log_tail = None, None, []
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUNBUFFERED', '1'); env.insert('PYTHONIOENCODING', 'utf-8'); env.insert('PYTHONUTF8', '1')
        if not config.frozen():
            env.insert('PYTHONPATH', str(config.install_dir()) + os.pathsep + env.value('PYTHONPATH', ''))
        self.process = QProcess(self)
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.on_output)
        self.process.finished.connect(self.on_finished)
        self.process.errorOccurred.connect(self.on_process_error)
        self.buffer = ''
        program, args = worker_command(job_file)
        self.search.edit.setEnabled(False)
        self.search.set_button(t('cancel', self.language))
        self.action.hide()
        self.show_status(t('starting', self.language), self.city.name, progress=0.0)
        self.process.start(program, args)

    def on_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        self.buffer += data.replace('\r\n', '\n')
        *lines, self.buffer = self.buffer.split('\n')
        for line in lines:
            if line.startswith(EVENT_PREFIX):
                try:
                    self.on_event(json.loads(line[len(EVENT_PREFIX):]))
                except ValueError:
                    pass
            elif line.strip():
                self.log_tail = (self.log_tail + [line])[-200:]

    def on_event(self, ev):
        kind = ev.get('event')
        if kind == 'progress':
            self.show_status(ev.get('stage', ''), ev.get('detail', ''), progress=float(ev.get('value', 0)))
        elif kind == 'folder':
            self.result_folder = ev.get('path')
        elif kind == 'log':
            self.log_tail = (self.log_tail + str(ev.get('text', '')).splitlines())[-200:]
        elif kind == 'done':
            self.result_folder = ev.get('path')
        elif kind == 'error':
            self.error = ev.get('message')

    def on_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.error = f'{self.process.program()}: failed to start'
            self.finish(1)

    def on_finished(self, code, _status):
        self.finish(code)

    def finish(self, code):
        if self.process is None:
            return
        cancelled = bool(self.process.property('cancelled'))
        self.process.deleteLater(); self.process = None
        self.search.edit.setEnabled(True)
        self.search.set_button(t('start', self.language))
        if cancelled:
            self.show_status(t('cancelled', self.language), progress=None)
            return
        if code == 0 and self.result_folder:
            self.progress.set_value(1.0, busy=False)
            self.show_status(t('done', self.language), self.result_folder, progress=1.0, busy=False)
            self.action.setProperty('mode', 'open'); self.action.setText(t('open_folder', self.language)); self.action.show()
            return
        self.save_error_log()
        self.show_status(t('failed', self.language), self.error or (self.log_tail[-1] if self.log_tail else ''), error=True)
        self.action.setProperty('mode', 'log'); self.action.setText(t('open_log', self.language)); self.action.show()

    def save_error_log(self):
        path = config.user_data_dir() / 'ultimo_errore.txt'
        path.write_text('\n'.join(self.log_tail), encoding='utf-8')
        self.error_log = path

    def confirm_cancel(self):
        dialog = Dialog(self, t('confirm_stop_title', self.language), t('confirm_stop_text', self.language),
                        ok=t('stop', self.language), cancel=t('continue', self.language))
        if dialog.exec() == QDialog.DialogCode.Accepted and self.process is not None:
            self.process.setProperty('cancelled', True)
            self.process.kill()

    def on_action(self):
        target = self.result_folder if self.action.property('mode') == 'open' else str(getattr(self, 'error_log', ''))
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def closeEvent(self, event):
        if self.process is not None:
            dialog = Dialog(self, t('confirm_close_title', self.language), t('confirm_close_text', self.language),
                            ok=t('close', self.language), cancel=t('continue', self.language))
            if dialog.exec() != QDialog.DialogCode.Accepted:
                event.ignore(); return
            self.process.setProperty('cancelled', True)
            self.process.kill(); self.process.waitForFinished(3000)
        super().closeEvent(event)


def run(argv) -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME); app.setApplicationVersion(__version__)
    load_fonts()
    icon = config.assets_dir() / 'sonar.ico'
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    return app.exec()

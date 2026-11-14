"""Widget disegnati a mano nello stile della UI di riferimento: linee nere/bianche da 2 px, angoli tondi."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Property, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QLineEdit, QWidget

from ..config import assets_dir

THEMES = {
    'light': {'bg': '#FFFFFF', 'fg': '#000000', 'muted': '#8E8E8E', 'soft': '#EDEDED', 'error': '#B3261E'},
    'dark': {'bg': '#1C1C1C', 'fg': '#FFFFFF', 'muted': '#8A8A8A', 'soft': '#353535', 'error': '#FF8A80'},
}
FAMILY = ['Quicksand']


def load_fonts():
    for path in sorted((assets_dir() / 'fonts').glob('*.ttf')):
        ident = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(ident) if ident >= 0 else []
        if families:
            FAMILY[0] = families[0]


def font(size: float, weight=QFont.Weight.Medium, spacing: float | None = None) -> QFont:
    f = QFont(FAMILY[0])
    f.setPixelSize(max(1, int(round(size))))
    f.setWeight(weight)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    if spacing is not None:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


class Themed:
    colors = THEMES['light']

    def set_theme(self, colors):
        self.colors = colors
        self.update()


class Frame(Themed, QWidget):
    """Sfondo con cornice interna da 2 px."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.colors['bg']))
        p.setPen(QPen(QColor(self.colors['fg']), 2))
        p.drawRect(QRectF(self.rect()).adjusted(8, 8, -8, -8))


class Logo(Themed, QWidget):
    """Logo provvisorio: 'Sonar' a contorno. Un file assets/logo.svg lo sostituisce."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(92)
        self.svg = None
        path = assets_dir() / 'logo.svg'
        if path.exists():
            try:
                from PySide6.QtSvg import QSvgRenderer
                self.svg = QSvgRenderer(str(path))
            except Exception:
                self.svg = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.svg is not None and self.svg.isValid():
            size = self.svg.defaultSize().scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio)
            self.svg.render(p, QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2, size.width(), size.height()))
            return
        path = QPainterPath()
        path.addText(0, 0, font(84, QFont.Weight.Bold, 13), 'Sonar')
        box = path.boundingRect()
        path.translate((self.width() - box.width()) / 2 - box.left(), (self.height() - box.height()) / 2 - box.top())
        p.setPen(QPen(QColor(self.colors['fg']), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


class IconButton(Themed, QAbstractButton):
    """Riduci a icona (trattino) e chiudi (croce)."""

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(self.colors['soft'])); p.drawRoundedRect(self.rect(), 6, 6)
        p.setPen(QPen(QColor(self.colors['fg']), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        c, r = QPointF(self.width() / 2, self.height() / 2), 8.5
        if self.kind == 'min':
            p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        else:
            p.drawLine(QPointF(c.x() - r, c.y() - r), QPointF(c.x() + r, c.y() + r))
            p.drawLine(QPointF(c.x() - r, c.y() + r), QPointF(c.x() + r, c.y() - r))

    def enterEvent(self, e):
        self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self.update(); super().leaveEvent(e)


class SearchBar(Themed, QWidget):
    """Campo città e pulsante in un'unica forma: bordo arrotondato da 2 px, pulsante pieno fino al bordo."""
    activated = Signal()      # pulsante
    submitted = Signal()      # Invio nel campo

    RADIUS = 6.5
    BUTTON_WIDTH = 115

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(332, 30)
        self.label = ''
        self.hover = False
        self.enabled_button = True
        self.edit = QLineEdit(self)
        self.edit.setFrame(False)
        self.edit.setFont(font(20.5, QFont.Weight.Normal))
        self.edit.returnPressed.connect(self.submitted)
        self.setMouseTracking(True)
        self._place()

    def _place(self):
        self.edit.setGeometry(8, 0, self.width() - self.BUTTON_WIDTH - 10, self.height())

    def set_theme(self, colors):
        super().set_theme(colors)
        self.edit.setStyleSheet(f'QLineEdit {{ background: transparent; border: none; color: {colors["fg"]};'
                                f' selection-background-color: {colors["fg"]}; selection-color: {colors["bg"]}; }}'
                                f' QLineEdit[placeholderText] {{ }}')
        palette = self.edit.palette()
        palette.setColor(palette.ColorRole.PlaceholderText, QColor(colors['muted']))
        palette.setColor(palette.ColorRole.Text, QColor(colors['fg']))
        self.edit.setPalette(palette)

    def set_button(self, text: str, enabled: bool = True):
        self.label, self.enabled_button = text, enabled
        self.update()

    def _button_rect(self) -> QRectF:
        return QRectF(self.width() - self.BUTTON_WIDTH, 0, self.BUTTON_WIDTH, self.height())

    def mouseMoveEvent(self, event):
        hover = self._button_rect().contains(event.position())
        if hover != self.hover:
            self.hover = hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        self.hover = False; self.update(); super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._button_rect().contains(event.position()) and self.enabled_button:
            self.activated.emit()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg, bg = QColor(self.colors['fg']), QColor(self.colors['bg'])
        outer = QRectF(1, 1, self.width() - 2, self.height() - 2)
        shape = QPainterPath()
        shape.addRoundedRect(outer, self.RADIUS, self.RADIUS)
        p.fillPath(shape, bg)
        button = self._button_rect()
        fill = QColor(fg)
        if not self.enabled_button:
            fill = QColor(self.colors['muted'])
        elif self.hover:
            fill.setAlphaF(0.82)
        p.save(); p.setClipPath(shape); p.fillRect(button, fill); p.restore()
        p.setPen(QPen(fg if self.enabled_button else QColor(self.colors['muted']), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(shape)
        p.setPen(bg)
        p.setFont(font(18.5, QFont.Weight.Bold))
        p.drawText(button, Qt.AlignmentFlag.AlignCenter, self.label)


class PillToggle(Themed, QAbstractButton):
    """Interruttore a due posizioni come nella UI: pillola con bordo, cerchio pieno sulla scelta attiva."""
    switched = Signal(int)

    def __init__(self, parent=None, width=54):
        super().__init__(parent)
        self.index = 0
        self._pos = 0.0
        self.setFixedSize(width, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.anim = QPropertyAnimation(self, b'knob', self)
        self.anim.setDuration(160); self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.clicked.connect(lambda: self.switched.emit(1 - self.index))

    def get_knob(self):
        return self._pos

    def set_knob(self, value):
        self._pos = value; self.update()

    knob = Property(float, get_knob, set_knob)

    def set_index(self, index: int, animate=False):
        self.index = index
        if animate:
            self.anim.stop(); self.anim.setStartValue(self._pos); self.anim.setEndValue(float(index)); self.anim.start()
        else:
            self._pos = float(index); self.update()

    def geometry_points(self):
        rect = QRectF(1.2, 1.2, self.width() - 2.4, self.height() - 2.4)
        d = rect.height() - 6
        left = QPointF(rect.left() + 3 + d / 2, rect.center().y())
        right = QPointF(rect.right() - 3 - d / 2, rect.center().y())
        return rect, d, left, right

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg, bg = QColor(self.colors['fg']), QColor(self.colors['bg'])
        rect, d, left, right = self.geometry_points()
        p.setPen(QPen(fg, 2)); p.setBrush(bg); p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        knob = QPointF(left.x() + (right.x() - left.x()) * self._pos, left.y())
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(fg)
        p.drawEllipse(knob, d / 2, d / 2)
        self.draw_marks(p, left, right, d, bg if self._pos < 0.5 else fg, bg if self._pos >= 0.5 else fg)

    def draw_marks(self, p, left, right, d, left_color, right_color):
        raise NotImplementedError


class ThemeToggle(PillToggle):
    """Sole (chiaro) / luna (scuro)."""

    def draw_marks(self, p, left, right, d, left_color, right_color):
        p.setPen(QPen(left_color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.setBrush(Qt.BrushStyle.NoBrush)
        r = d * 0.17
        p.drawEllipse(left, r, r)
        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(QPointF(left.x() + math.cos(a) * r * 1.6, left.y() + math.sin(a) * r * 1.6),
                       QPointF(left.x() + math.cos(a) * r * 2.3, left.y() + math.sin(a) * r * 2.3))
        r = d * 0.33
        outer = QPainterPath(); outer.addEllipse(right, r, r)
        cut = QPainterPath(); cut.addEllipse(QPointF(right.x() + r * 0.55, right.y() - r * 0.45), r * 0.85, r * 0.85)
        p.setPen(QPen(right_color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(outer.subtracted(cut))


class LanguageToggle(PillToggle):
    """IT / EN con la stessa forma dell'interruttore del tema."""
    LABELS = ('IT', 'EN')

    def draw_marks(self, p, left, right, d, left_color, right_color):
        p.setFont(font(10.5, QFont.Weight.Bold))
        for centre, color, text in ((left, left_color, self.LABELS[0]), (right, right_color, self.LABELS[1])):
            p.setPen(color)
            p.drawText(QRectF(centre.x() - d / 2, centre.y() - d / 2, d, d), Qt.AlignmentFlag.AlignCenter, text)


class ProgressLine(Themed, QWidget):
    """Barra sottile con bordo da 1,5 px; durante il lavoro scorre un segmento nel tratto non completato."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value, self.busy, self.phase = 0.0, False, 0.0
        self.setFixedHeight(8)
        self.timer = QTimer(self); self.timer.setInterval(30); self.timer.timeout.connect(self._tick)

    def set_value(self, value, busy=True):
        self.value, self.busy = max(0.0, min(1.0, value)), busy
        (self.timer.start() if busy else self.timer.stop())
        self.update()

    def _tick(self):
        self.phase = (self.phase + 0.012) % 1.0; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        fg = QColor(self.colors['fg'])
        p.setPen(QPen(fg, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        inner = rect.adjusted(2, 2, -2, -2)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(fg)
        done = inner.width() * self.value
        if done > 0:
            p.drawRoundedRect(QRectF(inner.left(), inner.top(), max(done, inner.height()), inner.height()), inner.height() / 2, inner.height() / 2)
        if self.busy:
            rest = QRectF(inner.left() + done, inner.top(), inner.width() - done, inner.height())
            if rest.width() > 12:
                seg = max(18.0, rest.width() * 0.18)
                x = rest.left() + (rest.width() + seg) * self.phase - seg
                left = max(rest.left(), x)
                piece = QRectF(left, rest.top(), min(seg, rest.right() - left), rest.height())
                if piece.width() > 0:
                    c = QColor(fg); c.setAlpha(110); p.setBrush(c)
                    p.drawRoundedRect(piece, piece.height() / 2, piece.height() / 2)

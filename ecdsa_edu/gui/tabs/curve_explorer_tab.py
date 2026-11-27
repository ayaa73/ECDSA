"""P1: interactive real and finite-field elliptic-curve explorer.

Real numbers tab: the curve is drawn as the solution set of
y^2 - x^3 - ax - b = 0 over the area on screen (a contour), recomputed for
every view, so it stays continuous at any zoom level instead of breaking up
where it turns vertical. Ctrl + mouse wheel (or a pinch) zooms at the
pointer, dragging pans, and the buttons zoom in/out, reset or fit the
construction. A plain mouse wheel is left to the page, which scrolls.
"""
from __future__ import annotations
import math
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QComboBox, QSlider, QTabWidget, QPlainTextEdit, QDoubleSpinBox, QScrollArea, QFrame)
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt
from ecdsa_edu.core.curve import Curve, enumerate_points, point_add, point_double, scalar_mult
from ecdsa_edu.gui.widgets.worker import run_in_background


def finite_field_figure(curve: Curve, selected=(), arrows=False) -> Figure:
    """Reusable plot for the Explorer and Learn page (no cryptography in GUI)."""
    fig = Figure(figsize=(6, 4)); ax = fig.add_subplot(111)
    if curve.p >= 5000:
        ax.text(
            0.5, 0.58,
            "Large finite field",
            ha="center", va="center",
            fontsize=16, fontweight="bold",
            color="#243b6b",
            transform=ax.transAxes
        )
        ax.text(
            0.5, 0.45,
            f"{curve.name} uses a {curve.p.bit_length()}-bit prime field.\n"
            "Plotting every point is computationally infeasible.\n\n"
            "The curve's mathematical operations still work.\n"
            "See the information panel for its parameters.",
            ha="center", va="center",
            fontsize=10, linespacing=1.7,
            transform=ax.transAxes
        )
        ax.set_axis_off()
        fig.tight_layout()
        return fig
    points = [q for q in enumerate_points(curve) if q is not None]
    ax.scatter([q[0] for q in points],[q[1] for q in points],s=24,alpha=.55)
    for label,pt in selected:
        if pt is not None:
            ax.scatter(*pt,s=100,label=label)
            ax.annotate(label,pt,xytext=(5,5),textcoords='offset points')
    if arrows:
        shown=[pt for _,pt in selected if pt is not None]
        for a,b in zip(shown,shown[1:]):
            ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','alpha':.45})
    ax.set(xlabel='x (mod p)',ylabel='y (mod p)',title=f'{curve.name}: points over F_{curve.p}')
    ax.grid(alpha=.2); fig.tight_layout(); return fig


DEFAULT_REAL_VIEW = (-5.0, 5.0, -12.0, 12.0)  # x_min, x_max, y_min, y_max
ZOOM_STEP = 1.25
REAL_NUMBERS_NOTE = ("Over the real numbers, points usually have decimal coordinates. This view shows the "
                     "geometry of point addition. ECDSA itself works over a finite field with whole numbers; "
                     "see the Finite field tab.")


class _ZoomCanvas(FigureCanvasQTAgg):
    """A plot canvas that zooms with Ctrl + wheel and leaves the plain wheel to the page."""

    def __init__(self, figure, on_zoom) -> None:
        super().__init__(figure)
        self._on_zoom = on_zoom

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.ignore()  # not for us: the page scrolls
            return
        steps = event.angleDelta().y() / 120
        if steps:
            ratio = self.device_pixel_ratio or 1
            pos = event.position()
            # matplotlib measures pixels from the bottom-left corner
            self._on_zoom(ZOOM_STEP ** -steps, pos.x() * ratio, (self.height() - pos.y()) * ratio)
        event.accept()


class CurveExplorerTab(QWidget):
    """A QWidget(state) with real chord/tangent and finite-field views."""
    HELP = (
        "The Curve Explorer demonstrates elliptic-curve point operations. "
        "In Real Numbers mode, select points to visualize addition using a chord or doubling using a tangent. "
        "Zoom with Ctrl + mouse wheel or the + and − buttons, and drag the plot to move around. "
        "In Finite Field mode, select two points to calculate their sum or animate multiples of the generator G. "
        "Large cryptographic curves cannot be fully plotted, so their parameters are displayed instead."
    )
    def __init__(self,state):
        super().__init__(); self.state=state; self.curve=state.curve
        self.real_points=[]; self.finite_points=[]; self.multiples=[]; self.index=0
        self.real_fit_all = False
        self.real_view = DEFAULT_REAL_VIEW
        self._drag = None  # (start pixel x, y, view at the start, moved?) while the mouse is down
        self.timer=QTimer(self); self.timer.timeout.connect(self._next_multiple)
        root=QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); self.views=QTabWidget(); root.addWidget(self.views)
        learn_link = QLabel('<a href="learn">Learn how the calculations work</a> — open Go deeper on the first Learn ECDSA page.')
        learn_link.setWordWrap(True)
        learn_link.linkActivated.connect(self._open_learn)
        root.addWidget(learn_link)
        self._setup_real(); self._setup_finite()
        state.curveChanged.connect(self.set_curve)
        self.set_curve(self.curve)

    def _open_learn(self, *_):
        self.state.open_first_learn_step = True
        try:
            self.state.go_to("Learn ECDSA")
        finally:
            self.state.open_first_learn_step = False

    def _canvas(self,layout,zoom=None):
        fig=Figure(figsize=(9,6)); fig.add_subplot(111)
        canvas=_ZoomCanvas(fig, zoom) if zoom else FigureCanvasQTAgg(fig)
        # Matplotlib's 9x6-inch size hint made the inner scroll area taller than
        # the visible page. Clicking the plot then scrolled its first control row
        # under the tab bar. Ignore that oversized hint and let the canvas fill
        # the space that is actually available.
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        canvas.setMinimumHeight(350); layout.addWidget(canvas,1)
        return canvas

    def _add_tab(self, page, title):
        """Each tab scrolls vertically when the window is short."""
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(page)
        scroll.verticalScrollBar().setValue(0)
        self.views.addTab(scroll, title)

    def _setup_real(self):
        page=QWidget(); v=QVBoxLayout(page); row=QHBoxLayout(); v.addLayout(row)
        self.a=QDoubleSpinBox(); self.b=QDoubleSpinBox()
        for widget,label,value in [(self.a,'a',-1.),(self.b,'b',1.)]:
            widget.setRange(-10,10); widget.setSingleStep(.25); widget.setValue(value)
            row.addWidget(QLabel(label));row.addWidget(widget)
            widget.valueChanged.connect(self._reset_real)
        self.real_mode=QComboBox();self.real_mode.addItems(['P + Q (chord)','2P (tangent)'])
        self.real_mode.currentIndexChanged.connect(self._reset_real);row.addWidget(self.real_mode)
        self.clear_points_button = QPushButton('Clear points')
        self.clear_points_button.clicked.connect(self._reset_real)
        row.addWidget(self.clear_points_button)
        row.addStretch(1)
        zoom_row=QHBoxLayout(); v.addLayout(zoom_row)
        self.zoom_in_button=QPushButton('+'); self.zoom_out_button=QPushButton('\u2212')
        self.zoom_in_button.setToolTip('Zoom in (Ctrl + mouse wheel)'); self.zoom_out_button.setToolTip('Zoom out (Ctrl + mouse wheel)')
        self.zoom_in_button.setAccessibleName('Zoom in'); self.zoom_out_button.setAccessibleName('Zoom out')
        self.zoom_in_button.clicked.connect(lambda: self.zoom_real(1 / ZOOM_STEP))
        self.zoom_out_button.clicked.connect(lambda: self.zoom_real(ZOOM_STEP))
        reset=QPushButton('Reset view'); reset.clicked.connect(self.reset_real_view)
        self.fit_points_button = QPushButton('Fit all points')
        self.fit_points_button.clicked.connect(self._fit_all_real)
        for widget in (QLabel('View:'), self.zoom_in_button, self.zoom_out_button, reset, self.fit_points_button):
            zoom_row.addWidget(widget)
        hint=QLabel('Ctrl + wheel to zoom · drag to move'); hint.setProperty('muted', True); zoom_row.addWidget(hint)
        zoom_row.addStretch(1)
        self.real_note=QLabel();self.real_note.setWordWrap(True);v.addWidget(self.real_note)
        self.real_canvas=self._canvas(v, zoom=self._zoom_at_pixel)
        self.real_canvas.mpl_connect('button_press_event',self._press_real)
        self.real_canvas.mpl_connect('motion_notify_event',self._drag_real)
        self.real_canvas.mpl_connect('button_release_event',self._release_real)
        self.real_explanation=QLabel(REAL_NUMBERS_NOTE); self.real_explanation.setWordWrap(True)
        self.real_explanation.setProperty('muted', True); v.addWidget(self.real_explanation)
        self._add_tab(page,'Real numbers');self._draw_real()

    def _reset_real(self,*_):
        self.real_points=[];self.real_fit_all=False;self._draw_real()

    def _fit_all_real(self):
        """Show the complete chord/tangent construction on demand."""
        self.real_fit_all=True
        self._draw_real()

    # ---- zoom and pan (the view is (x_min, x_max, y_min, y_max)) -----------------
    def zoom_real(self, factor, cx=None, cy=None):
        """Scale the view by ``factor`` (< 1 zooms in) around (cx, cy), the centre by default."""
        x0, x1, y0, y1 = self.real_view
        cx = (x0 + x1) / 2 if cx is None else cx
        cy = (y0 + y1) / 2 if cy is None else cy
        width, height = (x1 - x0) * factor, (y1 - y0) * factor
        if not 1e-3 < width < 1e4:
            return  # keep the numbers sensible
        fx, fy = (cx - x0) / (x1 - x0), (cy - y0) / (y1 - y0)  # keep the point under the mouse in place
        self.real_view = (cx - fx * width, cx + (1 - fx) * width, cy - fy * height, cy + (1 - fy) * height)
        self.real_fit_all = False
        self._draw_real()

    def _zoom_at_pixel(self, factor, px, py):
        ax = self.real_canvas.figure.axes[0]
        if ax.bbox.contains(px, py):
            cx, cy = ax.transData.inverted().transform((px, py))
            self.zoom_real(factor, cx, cy)
        else:
            self.zoom_real(factor)

    def reset_real_view(self):
        self.real_view = DEFAULT_REAL_VIEW
        self.real_fit_all = False
        self._draw_real()

    def _press_real(self, event):
        if event.inaxes is self.real_canvas.figure.axes[0]:
            self._drag = (event.x, event.y, self.real_view, False)

    def _drag_real(self, event):
        if self._drag is None or event.x is None:
            return
        sx, sy, view, moved = self._drag
        if not moved and math.hypot(event.x - sx, event.y - sy) < 6:
            return  # still a click, not a drag
        self._drag = (sx, sy, view, True)
        ax = self.real_canvas.figure.axes[0]
        box = ax.bbox
        dx = (event.x - sx) / box.width * (view[1] - view[0])
        dy = (event.y - sy) / box.height * (view[3] - view[2])
        self.real_view = (view[0] - dx, view[1] - dx, view[2] - dy, view[3] - dy)
        self.real_fit_all = False
        self._draw_real()

    def _release_real(self, event):
        drag, self._drag = self._drag, None
        if drag is not None and not drag[3]:
            self._click_real(event)  # a click without moving selects a point

    def _click_real(self, event):
        """Select the closest visible point on either branch of the real curve."""
        if event.inaxes is not self.real_canvas.figure.axes[0] or event.xdata is None or event.ydata is None:
            return
        ax = self.real_canvas.figure.axes[0]
        x_min, x_max = ax.get_xlim()
        xs = np.linspace(x_min, x_max, 2500)
        rad = xs**3 + self.a.value()*xs + self.b.value()
        valid = rad >= 0
        if not valid.any():
            return
        xs = xs[valid]
        ys = np.sqrt(rad[valid])
        # Use screen coordinates so selection works with differently scaled axes.
        candidates = np.concatenate((np.column_stack((xs, ys)), np.column_stack((xs, -ys))))
        pixels = ax.transData.transform(candidates)
        distance = np.hypot(pixels[:, 0] - event.x, pixels[:, 1] - event.y)
        nearest = int(np.argmin(distance))
        if distance[nearest] > 35:
            self.real_note.setText('Click within 35 pixels of a point on the blue or orange curve.')
            return
        point = tuple(map(float, candidates[nearest]))
        max_points = 1 if self.real_mode.currentIndex() == 1 else 2
        self.real_points = (self.real_points + [point])[-max_points:]
        self.real_fit_all = False
        self._draw_real()

    def _draw_curve(self, ax, a, b):
        """The real curve over the visible area, continuous at every zoom level.

        It is the zero set of F(x, y) = y^2 - x^3 - ax - b. A contour of F is
        traced along the curve itself, so it also follows the steep parts near
        y = 0 that sampling y = +-sqrt(x^3 + ax + b) at fixed x misses. The upper
        half (y >= 0) is blue and the lower half orange; they meet at y = 0.
        """
        x0, x1, y0, y1 = self.real_view
        xs = np.linspace(x0, x1, 500)
        for low, high, color in ((max(y0, 0.0), y1, '#2678c7'), (y0, min(y1, 0.0), '#ed8a22')):
            if high <= low:
                continue
            X, Y = np.meshgrid(xs, np.linspace(low, high, 400))
            ax.contour(X, Y, Y**2 - X**3 - a*X - b, levels=[0], colors=[color], linewidths=2)

    def _construction(self, a):
        """(slope, x3, y3) of the chord/tangent construction, (None, ...) for O, or None if not ready."""
        is_double = self.real_mode.currentIndex() == 1
        if not ((is_double and len(self.real_points) == 1) or (not is_double and len(self.real_points) == 2)):
            return None
        x1, y1 = self.real_points[0]
        if is_double:
            slope = (3*x1*x1 + a)/(2*y1) if abs(y1) > 1e-9 else None
            x2, y2 = x1, y1
        else:
            x2, y2 = self.real_points[1]
            slope = (y2-y1)/(x2-x1) if abs(x2-x1) > 1e-9 else None
            if slope is None and abs(y1+y2) > 1e-6:
                slope = (3*x1*x1+a)/(2*y1) if abs(y1) > 1e-9 else None
        if slope is None:
            return None, None, None
        x3 = slope*slope - x1 - x2
        return slope, x3, slope*(x1 - x3) - y1

    def _draw_real(self, *_):
        a, b = self.a.value(), self.b.value()
        singular = abs(4*a**3 + 27*b*b) < 1e-8
        is_double = self.real_mode.currentIndex() == 1
        result = self._construction(a)
        has_finite_result = result is not None and result[0] is not None
        self.clear_points_button.setEnabled(bool(self.real_points))
        self.fit_points_button.setEnabled(has_finite_result)
        if self.real_fit_all and has_finite_result:
            # Grow the view so P, Q, the third intersection and the result all show.
            _, x3, y3 = result
            xs = [x for x, _ in self.real_points] + [x3]
            ys = [y for _, y in self.real_points] + [y3, -y3]
            x_min, x_max, y_min, y_max = self.real_view
            self.real_view = (min(x_min, min(xs) - 1), max(x_max, max(xs) + 1),
                              min(y_min, min(ys) - 2), max(y_max, max(ys) + 2))
        x_min, x_max, y_min, y_max = self.real_view

        ax = self.real_canvas.figure.axes[0]
        ax.clear()
        self._draw_curve(ax, a, b)
        note = ('SINGULAR: 4a³ + 27b² = 0; not an elliptic curve' if singular
                else ('Tangent mode: click one point near the curve.' if is_double
                      else 'Chord mode: click two points near the curve.'))
        for i, (x, y) in enumerate(self.real_points):
            ax.scatter([x], [y], s=85, zorder=6, color='#6b42bb')
            ax.annotate('P' if i == 0 else 'Q', (x, y), xytext=(8, 9), textcoords='offset points', weight='bold')
        if result is not None:
            slope, x3, result_y = result
            x1, y1 = self.real_points[0]
            x2, y2 = self.real_points[-1]
            if slope is None:
                note = 'Result is O (point at infinity): vertical line.'
                ax.axvline(x1, linestyle='--', color='#aa4488')
            else:
                # The line meets the curve a third time at (x3, -y3); reflecting it gives P + Q.
                xx = np.linspace(min(x1, x2, x3, x_min) - 1, max(x1, x2, x3, x_max) + 1, 150)
                ax.plot(xx, y1 + slope*(xx - x1), '--', color='#a64080', lw=1.7)
                ax.scatter([x3], [-result_y], marker='x', s=95, color='#a64080', zorder=7)
                ax.plot([x3, x3], [-result_y, result_y], ':', color='#444444')
                ax.scatter([x3], [result_y], marker='*', s=180, color='#168654', zorder=8)
                ax.annotate('2P' if is_double else 'P + Q', (x3, result_y),
                            xytext=(10, 10), textcoords='offset points', weight='bold')
                visible = x_min <= x3 <= x_max and y_min <= result_y <= y_max
                note = (f'{"2P" if is_double else "P + Q"} = ({x3:.2f}, {result_y:.2f}); '
                        f'slope = {slope:.2f}; P = ({x1:.2f}, {y1:.2f})'
                        + ('' if is_double else f'; Q = ({x2:.2f}, {y2:.2f})')
                        + ('' if visible else '. The result is off-screen: zoom out or click Fit all points.'))
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title(f'y² = x³ + ({a:g})x + ({b:g})')
        ax.grid(alpha=.2)
        self.real_note.setText(note)
        self.real_canvas.figure.tight_layout(pad=1.6)
        self.real_canvas.draw_idle()

    def _setup_finite(self):
        page=QWidget();v=QVBoxLayout(page);controls=QHBoxLayout();v.addLayout(controls)
        self.finite_mode=QComboBox();self.finite_mode.addItems(['Add P + Q','Multiples of G'])
        self.finite_mode.currentIndexChanged.connect(self._change_finite_mode);controls.addWidget(self.finite_mode)
        self.play=QPushButton('Play / pause');self.play.clicked.connect(self._toggle_animation);controls.addWidget(self.play)
        self.speed_label=QLabel('Speed');controls.addWidget(self.speed_label);self.speed=QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1,10);self.speed.setValue(5);self.speed.valueChanged.connect(self._speed_changed);controls.addWidget(self.speed)
        middle=QHBoxLayout();v.addLayout(middle,1)
        self.finite_canvas=self._canvas(middle);self.finite_canvas.mpl_connect('button_press_event',self._click_finite)
        self.trace_text=QPlainTextEdit();self.trace_text.setReadOnly(True);middle.addWidget(self.trace_text,1)
        self.play.setEnabled(False);self.speed.setEnabled(False);self.speed_label.setEnabled(False)
        self._add_tab(page,'Finite field')

    def set_curve(self,curve):
        self.curve=curve;self.timer.stop();self.finite_points=[];self.multiples=[];self.index=0
        self.play.setEnabled(curve is not None and curve.p < 5000 and self.finite_mode.currentIndex() == 1)
        self.speed.setEnabled(self.play.isEnabled());self.speed_label.setEnabled(self.play.isEnabled())
        if curve is not None:self._refresh_finite()

    def _refresh_finite(self):
        if self.curve is None:return
        if self.curve.p >= 5000:
            self._replace_finite_plot([])

            curve = self.curve

            def format_hex(value):
                hexadecimal = f"{value:064x}"
                return "\n".join(
                    hexadecimal[i:i+32]
                    for i in range(0, len(hexadecimal), 32)
                )

            gx, gy = curve.G

            info = (
                "ELLIPTIC CURVE PARAMETERS\n"
                "========================================\n\n"
                f"Curve: {curve.name}\n"
                f"Field size: {curve.p.bit_length()} bits\n"
                f"Subgroup order: {curve.n.bit_length()} bits\n"
                f"Cofactor (h): {curve.h}\n\n"

                "FIELD PRIME (p)\n"
                "----------------------------------------\n"
                f"0x{format_hex(curve.p)}\n\n"

                "CURVE EQUATION\n"
                "----------------------------------------\n"
                "y² = x³ + ax + b (mod p)\n\n"

                "GENERATOR POINT (G)\n"
                "----------------------------------------\n"
                "Gx:\n"
                f"0x{format_hex(gx)}\n\n"
                "Gy:\n"
                f"0x{format_hex(gy)}\n\n"

                "GROUP ORDER (n)\n"
                "----------------------------------------\n"
                f"0x{format_hex(curve.n)}\n\n"

                "VISUALIZATION LIMITATION\n"
                "----------------------------------------\n"
                "This curve contains an enormous number\n"
                "of finite-field points.\n\n"
                "Enumerating and plotting every point\n"
                "is computationally infeasible.\n\n"
                "However, point addition, doubling,\n"
                "scalar multiplication, signing, and\n"
                "verification remain supported."
            )

            self.trace_text.setPlainText(info)

        elif self.finite_mode.currentIndex() == 0:
            self._show_finite(self.finite_points)
        else:self._show_multiple()

    def _show_finite(self,points):
        selected=[(f'P{i+1}',q) for i,q in enumerate(points)]
        if len(points)==2:
            trace=[];r=point_add(self.curve,*points,trace=trace)
            selected.append(('P+Q',r));self.trace_text.setPlainText('\n\n'.join(f'{s.title}\n{s.formula}\n{s.values}' for s in trace))
        else:self.trace_text.setPlainText('Click two plotted points to add them.')
        self._replace_finite_plot(selected)

    def _replace_finite_plot(self,selected,arrows=False):
        # Keep the same Figure and Axes objects. Replacing canvas.figure leaves
        # stale axes/artists attached and breaks matplotlib click handling.
        fig = self.finite_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.curve.p >= 5000:
            ax.text(
                0.5, 0.72,
                "256-bit Elliptic Curve",
                ha="center", va="center",
                fontsize=17, fontweight="bold",
                color="#243b6b",
                transform=ax.transAxes
            )

            ax.text(
                0.5, 0.60,
                f"Curve: {self.curve.name}\n"
                f"Field size: {self.curve.p.bit_length()} bits",
                ha="center", va="center",
                fontsize=11, linespacing=1.6,
                transform=ax.transAxes
            )

            ax.text(
                0.5, 0.42,
                "A complete finite-field plot is not practical\n"
                "for a cryptographic curve of this size.",
                ha="center", va="center",
                fontsize=11, linespacing=1.6,
                transform=ax.transAxes
            )

            ax.text(
                0.5, 0.25,
                "Point addition and scalar multiplication\n"
                "remain fully supported by the mathematical core.",
                ha="center", va="center",
                fontsize=10, linespacing=1.6,
                transform=ax.transAxes
            )

            ax.set_axis_off()


        else:
            points = [q for q in enumerate_points(self.curve) if q is not None]
            ax.scatter([q[0] for q in points], [q[1] for q in points],
                       s=38, alpha=.65, color='#3498db')
            for label, pt in selected:
                if pt is not None:
                    ax.scatter([pt[0]], [pt[1]], s=105, zorder=5, label=label)
                    ax.annotate(label, pt, xytext=(5, 5),
                                textcoords='offset points', fontsize=9)
            if arrows:
                shown = [pt for _, pt in selected if pt is not None]
                for start, end in zip(shown, shown[1:]):
                    ax.annotate('', xy=end, xytext=start,
                                arrowprops={'arrowstyle': '->', 'alpha': .4})
            ax.set(xlabel='x (mod p)', ylabel='y (mod p)',
                   title=f'{self.curve.name}: points over F_{self.curve.p}')
            ax.set_xlim(-.8, self.curve.p - .2)
            ax.set_ylim(-.8, self.curve.p - .2)
            ax.grid(alpha=.2)
        fig.tight_layout(pad=1.5)
        self.finite_canvas.draw_idle()

    def _click_finite(self,event):
        if self.curve is None or self.curve.p>=5000 or self.finite_mode.currentIndex()!=0 or event.xdata is None or event.ydata is None:return
        if event.inaxes is not self.finite_canvas.figure.axes[0]:return
        # Nearest valid point; enumeration happens only for small fields.
        points=[q for q in enumerate_points(self.curve) if q is not None]
        # Pixel-space distance makes picking reliable even when the window is resized.
        ax = self.finite_canvas.figure.axes[0]
        chosen = min(points, key=lambda q: math.dist(
            ax.transData.transform(q), (event.x, event.y)))
        if math.dist(ax.transData.transform(chosen), (event.x, event.y)) > 22:
            self.trace_text.setPlainText('Click closer to a plotted point.')
            return
        self.finite_points=(self.finite_points+[chosen])[-2:];self._show_finite(self.finite_points)

    def _change_finite_mode(self,*_):
        self.timer.stop();self.finite_points=[];self.index=0
        self.play.setEnabled(self.curve is not None and self.curve.p < 5000 and self.finite_mode.currentIndex() == 1)
        self.speed.setEnabled(self.play.isEnabled());self.speed_label.setEnabled(self.play.isEnabled())
        self._refresh_finite()

    def _speed_changed(self,*_):
        if self.timer.isActive():self.timer.start(1100-100*self.speed.value())

    def _toggle_animation(self):
        if self.curve is None or self.curve.p>=5000 or self.finite_mode.currentIndex()!=1:return
        if self.timer.isActive():self.timer.stop();return
        if not self.multiples:
            curve=self.curve
            run_in_background(lambda:[scalar_mult(curve,k,curve.G) for k in range(1,curve.n+1)],
                on_done=lambda points: self._loaded_multiples(points) if self.curve is curve else None,on_error=lambda exc:self.trace_text.setPlainText(str(exc)))
        else:
            if self.index == len(self.multiples)-1:
                self.index=0;self._show_multiple()
            self.timer.start(1100-100*self.speed.value())

    def _loaded_multiples(self,points):
        if self.finite_mode.currentIndex() != 1:return
        self.multiples=points;self.index=0;self.timer.start(1100-100*self.speed.value());self._show_multiple()

    def _next_multiple(self):
        if not self.multiples:return
        if self.index+1 >= len(self.multiples):
            self.timer.stop();return
        self.index+=1;self._show_multiple()

    def _show_multiple(self):
        if not self.multiples:
            self._replace_finite_plot([('G',self.curve.G)]);self.trace_text.setPlainText('Press Play to animate G, 2G, …, nG = O.');return
        k=self.index+1;shown=[(f'{i+1}G',q) for i,q in enumerate(self.multiples[:k])]
        self._replace_finite_plot(shown,arrows=True)
        self.trace_text.setPlainText("\n".join(f'{i+1}G = {q if q is not None else "O (point at infinity)"}' for i,q in enumerate(self.multiples[:k])))
        self.trace_text.moveCursor(QTextCursor.MoveOperation.End)

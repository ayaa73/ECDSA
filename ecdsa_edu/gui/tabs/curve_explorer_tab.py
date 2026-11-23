"""P1: interactive real and finite-field elliptic-curve explorer."""
from __future__ import annotations
import math
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QComboBox, QSlider, QTabWidget, QPlainTextEdit, QDoubleSpinBox)
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


class CurveExplorerTab(QWidget):
    """A QWidget(state) with real chord/tangent and finite-field views."""
    def __init__(self,state):
        super().__init__(); self.state=state; self.curve=state.curve
        self.real_points=[]; self.finite_points=[]; self.multiples=[]; self.index=0
        self.real_fit_all = False
        self.timer=QTimer(self); self.timer.timeout.connect(self._next_multiple)
        root=QVBoxLayout(self); self.views=QTabWidget(); root.addWidget(self.views)
        self._setup_real(); self._setup_finite()
        state.curveChanged.connect(self.set_curve)
        self.set_curve(self.curve)

    def _canvas(self,layout):
        fig=Figure(figsize=(9,6)); fig.add_subplot(111); canvas=FigureCanvasQTAgg(fig); canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); canvas.setMinimumHeight(350); layout.addWidget(canvas,1)
        return canvas

    def _setup_real(self):
        page=QWidget(); v=QVBoxLayout(page); row=QHBoxLayout(); v.addLayout(row)
        self.a=QDoubleSpinBox(); self.b=QDoubleSpinBox()
        for widget,label,value in [(self.a,'a',-1.),(self.b,'b',1.)]:
            widget.setRange(-10,10); widget.setSingleStep(.25); widget.setValue(value)
            row.addWidget(QLabel(label));row.addWidget(widget)
            widget.valueChanged.connect(self._reset_real)
        self.real_mode=QComboBox();self.real_mode.addItems(['P + Q (chord)','2P (tangent)'])
        self.real_mode.currentIndexChanged.connect(self._reset_real);row.addWidget(self.real_mode)
        fit=QPushButton('Fit all points');fit.clicked.connect(self._fit_all_real);row.addWidget(fit)
        clear=QPushButton('Clear points');clear.clicked.connect(self._reset_real);row.addWidget(clear)
        self.real_note=QLabel();v.addWidget(self.real_note)
        self.real_canvas=self._canvas(v);self.real_canvas.mpl_connect('button_press_event',self._click_real)
        self.views.addTab(page,'Real numbers');self._draw_real()

    def _real_y(self,x):
        val=x**3+self.a.value()*x+self.b.value()
        return math.sqrt(val) if val>=0 else None

    def _reset_real(self,*_):
        self.real_points=[];self.real_fit_all=False;self._draw_real()

    def _fit_all_real(self):
        """Show the complete chord/tangent construction on demand."""
        self.real_fit_all=True
        self._draw_real()

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

    def _draw_real(self, *_):
        a, b = self.a.value(), self.b.value()
        singular = abs(4*a**3 + 27*b*b) < 1e-8
        ax = self.real_canvas.figure.axes[0]
        ax.clear()
        xs = np.linspace(-5, 5, 2200)
        rad = xs**3 + a*xs + b
        ys = np.sqrt(np.maximum(rad, 0))
        ax.plot(xs, np.where(rad >= 0, ys, np.nan), color='#2678c7', lw=2)
        ax.plot(xs, np.where(rad >= 0, -ys, np.nan), color='#ed8a22', lw=2)
        ax.set_xlim(-5, 5)
        ax.set_ylim(-12, 12)
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title(f'y² = x³ + ({a:g})x + ({b:g})')
        ax.grid(alpha=.2)
        note = ('SINGULAR: 4a³ + 27b² = 0; not an elliptic curve' if singular
                else ('Tangent mode: click one point near the curve.' if self.real_mode.currentIndex()
                      else 'Chord mode: click two points near the curve.'))
        for i, (x, y) in enumerate(self.real_points):
            ax.scatter([x], [y], s=85, zorder=6, color='#6b42bb')
            ax.annotate('P' if i == 0 else 'Q', (x, y), xytext=(8, 9), textcoords='offset points', weight='bold')
        is_double = self.real_mode.currentIndex() == 1
        if (is_double and len(self.real_points) == 1) or (not is_double and len(self.real_points) == 2):
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
                note = 'Result is O (point at infinity): vertical line.'
                ax.axvline(x1, linestyle='--', color='#aa4488')
            else:
                x3 = slope*slope-x1-x2
                y3 = slope*(x1-x3)-y1
                result_y = y3
                # The third intersection is (x3, -result_y); reflect it to obtain P+Q.
                xx = np.linspace(min(x1,x2,x3)-.6, max(x1,x2,x3)+.6, 150)
                ax.plot(xx, y1+slope*(xx-x1), '--', color='#a64080', lw=1.7)
                ax.scatter([x3], [-result_y], marker='x', s=95, color='#a64080', zorder=7)
                ax.plot([x3,x3], [-result_y,result_y], ':', color='#444444')
                ax.scatter([x3], [result_y], marker='*', s=180, color='#168654', zorder=8)
                ax.annotate('2P' if is_double else 'P + Q', (x3,result_y),
                            xytext=(10,10), textcoords='offset points', weight='bold')
                if self.real_fit_all:
                    ax.set_xlim(min(-5, x3-1), max(5, x3+1))
                    ax.set_ylim(min(-12, y1-2, y2-2, -result_y-2, result_y-2),
                                max(12, y1+2, y2+2, -result_y+2, result_y+2))
                note = (f'{"2P" if is_double else "P + Q"} = ({x3:.3f}, {result_y:.3f}); '
                        f'slope = {slope:.3f}; P=({x1:.3f}, {y1:.3f})'
                        + ('' if is_double else f'; Q=({x2:.3f}, {y2:.3f})')
                        + ('' if self.real_fit_all else '; result may be off-screen — click Fit all points'))
        self.real_note.setText(note)
        self.real_canvas.figure.tight_layout(pad=1.6)
        self.real_canvas.draw_idle()

    def _setup_finite(self):
        page=QWidget();v=QVBoxLayout(page);controls=QHBoxLayout();v.addLayout(controls)
        self.finite_mode=QComboBox();self.finite_mode.addItems(['Add P + Q','Multiples of G'])
        self.finite_mode.currentIndexChanged.connect(self._change_finite_mode);controls.addWidget(self.finite_mode)
        self.play=QPushButton('Play / pause');self.play.clicked.connect(self._toggle_animation);controls.addWidget(self.play)
        controls.addWidget(QLabel('Speed'));self.speed=QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1,10);self.speed.setValue(5);self.speed.valueChanged.connect(self._speed_changed);controls.addWidget(self.speed)
        middle=QHBoxLayout();v.addLayout(middle,1)
        self.finite_canvas=self._canvas(middle);self.finite_canvas.mpl_connect('button_press_event',self._click_finite)
        self.trace_text=QPlainTextEdit();self.trace_text.setReadOnly(True);middle.addWidget(self.trace_text,1)
        self.play.setEnabled(False)
        self.views.addTab(page,'Finite field')

    def set_curve(self,curve):
        self.curve=curve;self.timer.stop();self.finite_points=[];self.multiples=[];self.index=0
        self.play.setEnabled(curve is not None and curve.p < 5000 and self.finite_mode.currentIndex() == 1)
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
        self._refresh_finite()

    def _speed_changed(self,*_):
        if self.timer.isActive():self.timer.start(1100-100*self.speed.value())

    def _toggle_animation(self):
        if self.curve is None or self.curve.p>=5000 or self.finite_mode.currentIndex()!=1:return
        if self.timer.isActive():self.timer.stop();return
        if not self.multiples:
            curve=self.curve
            run_in_background(lambda:[scalar_mult(curve,k,curve.G) for k in range(1,curve.n+1)],
                on_done=self._loaded_multiples,on_error=lambda exc:self.trace_text.setPlainText(str(exc)))
        else:self.timer.start(1100-100*self.speed.value())

    def _loaded_multiples(self,points):
        if self.finite_mode.currentIndex() != 1:return
        self.multiples=points;self.index=0;self.timer.start(1100-100*self.speed.value());self._show_multiple()

    def _next_multiple(self):
        if not self.multiples:return
        self.index=(self.index+1)%len(self.multiples);self._show_multiple()

    def _show_multiple(self):
        if not self.multiples:
            self._replace_finite_plot([('G',self.curve.G)]);self.trace_text.setPlainText('Press Play to animate G, 2G, …, nG = O.');return
        k=self.index+1;shown=[(f'{i+1}G',q) for i,q in enumerate(self.multiples[:k])]
        self._replace_finite_plot(shown,arrows=True)
        self.trace_text.setPlainText(f'{k}G = {self.multiples[self.index] or "O (point at infinity)"}')

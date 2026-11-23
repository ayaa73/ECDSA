"""P1: interactive real and finite-field elliptic-curve explorer."""
from __future__ import annotations
import math
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QTabWidget, QPlainTextEdit, QDoubleSpinBox)
from PySide6.QtCore import Qt
from ecdsa_edu.core.curve import Curve, enumerate_points, point_add, point_double, scalar_mult
from ecdsa_edu.gui.widgets.worker import run_in_background


def finite_field_figure(curve: Curve, selected=(), arrows=False) -> Figure:
    """Reusable plot for the Explorer and Learn page (no cryptography in GUI)."""
    fig = Figure(figsize=(6, 4)); ax = fig.add_subplot(111)
    if curve.p >= 5000:
        ax.text(.5,.55, 'A 256-bit field cannot be enumerated or plotted',ha='center',transform=ax.transAxes)
        ax.text(.5,.4,f'G = {curve.G}',ha='center',wrap=True,fontsize=8,transform=ax.transAxes)
        ax.set_axis_off(); return fig
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
        self.timer=QTimer(self); self.timer.timeout.connect(self._next_multiple)
        root=QVBoxLayout(self); self.views=QTabWidget(); root.addWidget(self.views)
        self._setup_real(); self._setup_finite()
        state.curveChanged.connect(self.set_curve)
        self.set_curve(self.curve)

    def _canvas(self,layout):
        canvas=FigureCanvasQTAgg(Figure(figsize=(6,4))); layout.addWidget(canvas,1)
        return canvas

    def _setup_real(self):
        page=QWidget(); v=QVBoxLayout(page); row=QHBoxLayout(); v.addLayout(row)
        self.a=QDoubleSpinBox(); self.b=QDoubleSpinBox()
        for widget,label,value in [(self.a,'a',-1.),(self.b,'b',1.)]:
            widget.setRange(-10,10); widget.setSingleStep(.25); widget.setValue(value)
            row.addWidget(QLabel(label));row.addWidget(widget)
            widget.valueChanged.connect(self._draw_real)
        self.real_mode=QComboBox();self.real_mode.addItems(['P + Q (chord)','2P (tangent)'])
        self.real_mode.currentIndexChanged.connect(self._reset_real);row.addWidget(self.real_mode)
        clear=QPushButton('Clear points');clear.clicked.connect(self._reset_real);row.addWidget(clear)
        self.real_note=QLabel();v.addWidget(self.real_note)
        self.real_canvas=self._canvas(v);self.real_canvas.mpl_connect('button_press_event',self._click_real)
        self.views.addTab(page,'Real numbers');self._draw_real()

    def _real_y(self,x):
        val=x**3+self.a.value()*x+self.b.value()
        return math.sqrt(val) if val>=0 else None

    def _reset_real(self,*_):
        self.real_points=[];self._draw_real()

    def _click_real(self,event):
        if event.inaxes is None or event.xdata is None or event.ydata is None:return
        x=float(event.xdata);y=self._real_y(x)
        if y is None:return
        y=math.copysign(y,event.ydata)
        self.real_points.append((x,y))
        if len(self.real_points)> (1 if self.real_mode.currentIndex() else 2):
            self.real_points=self.real_points[-(1 if self.real_mode.currentIndex() else 2):]
        self._draw_real()

    def _draw_real(self,*_):
        a,b=self.a.value(),self.b.value();singular=abs(4*a**3+27*b*b)<1e-8
        self.real_note.setText('SINGULAR: 4a³ + 27b² = 0; not an elliptic curve' if singular else 'Click curve points; nearest x is snapped onto the curve')
        fig=Figure(figsize=(6,4));ax=fig.add_subplot(111)
        xs=np.linspace(-5,5,1600);rad=xs**3+a*xs+b;ys=np.sqrt(np.maximum(rad,0))
        ax.plot(xs,np.where(rad>=0,ys,np.nan));ax.plot(xs,np.where(rad>=0,-ys,np.nan))
        for i,(x,y) in enumerate(self.real_points):ax.scatter(x,y,s=70);ax.annotate('P' if i==0 else 'Q',(x,y))
        if len(self.real_points)==2 or (self.real_mode.currentIndex() and self.real_points):
            (x1,y1)=self.real_points[0]
            if self.real_mode.currentIndex():
                slope=(3*x1*x1+a)/(2*y1) if abs(y1)>1e-9 else None
            else:
                x2,y2=self.real_points[1];slope=(y2-y1)/(x2-x1) if abs(x2-x1)>1e-9 else None
            if slope is not None:
                x3=slope*slope-2*x1 if self.real_mode.currentIndex() else slope*slope-x1-x2
                y3=slope*(x1-x3)-y1
                line_x=np.linspace(min(x1,x3)-.4,max(x1,x3)+.4,100)
                ax.plot(line_x,y1+slope*(line_x-x1),'--',alpha=.7)
                ax.scatter([x3,x3],[y3,-y3],s=60);ax.plot([x3,x3],[y3,-y3],':')
                ax.annotate('P + Q' if not self.real_mode.currentIndex() else '2P',(x3,-y3))
        ax.set(xlim=(-5,5),ylim=(-8,8),xlabel='x',ylabel='y',title='y² = x³ + ax + b');ax.grid(alpha=.2)
        fig.tight_layout();self.real_canvas.figure=fig;self.real_canvas.draw_idle()

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
        self.views.addTab(page,'Finite field')

    def set_curve(self,curve):
        self.curve=curve;self.timer.stop();self.finite_points=[];self.multiples=[];self.index=0
        if curve is not None:self._refresh_finite()

    def _refresh_finite(self):
        if self.curve is None:return
        if self.curve.p>=5000:
            self.trace_text.setPlainText(f'{self.curve.name}: p has {self.curve.p.bit_length()} bits.\nG = {self.curve.G}\nCannot enumerate approximately 2^256 points.')
        elif self.finite_mode.currentIndex()==0:
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
        self.finite_canvas.figure=finite_field_figure(self.curve,selected,arrows);self.finite_canvas.draw_idle()

    def _click_finite(self,event):
        if self.curve is None or self.curve.p>=5000 or self.finite_mode.currentIndex()!=0 or event.xdata is None:return
        # Nearest valid point; enumeration happens only for small fields.
        points=[q for q in enumerate_points(self.curve) if q is not None]
        chosen=min(points,key=lambda q:(q[0]-event.xdata)**2+(q[1]-event.ydata)**2)
        self.finite_points=(self.finite_points+[chosen])[-2:];self._show_finite(self.finite_points)

    def _change_finite_mode(self,*_):
        self.timer.stop();self.finite_points=[];self.index=0;self._refresh_finite()

    def _speed_changed(self,*_):
        if self.timer.isActive():self.timer.start(1100-100*self.speed.value())

    def _toggle_animation(self):
        if self.curve is None or self.curve.p>=5000:return
        if self.timer.isActive():self.timer.stop();return
        if not self.multiples:
            curve=self.curve
            run_in_background(lambda:[scalar_mult(curve,k,curve.G) for k in range(1,curve.n+1)],
                on_done=self._loaded_multiples,on_error=lambda exc:self.trace_text.setPlainText(str(exc)))
        else:self.timer.start(1100-100*self.speed.value())

    def _loaded_multiples(self,points):
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

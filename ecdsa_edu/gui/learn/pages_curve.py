"""P1 Learn wizard: the curve and its generator."""
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.gui.learn.wizard import LearnPage, LearnState
from ecdsa_edu.gui.tabs.curve_explorer_tab import finite_field_figure

class CurvePage(LearnPage):
    title = 'Step 1: the curve and G'
    def __init__(self,parent=None):
        super().__init__(parent)
        self.plot=FigureCanvasQTAgg(finite_field_figure(get_curve('toy-17')))
        self.layout().insertWidget(3,self.plot)
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['k','kG'])
        self.layout().addWidget(self.table)

    def enter(self,st: LearnState)->None:
        curve=get_curve('toy-17');st.curve=curve
        self.set_text('An elliptic curve is a set of points satisfying an equation. '
            'Here all arithmetic happens modulo 17, so there are only 17 possible x-values. '
            'G is our starting point, called the generator. '
            'Repeatedly adding G produces the table below and eventually returns to O.')
        self.set_formula('y² = x³ + 2x + 2 (mod 17)     G = (5, 1)')
        self.set_values({'p':curve.p,'a':curve.a,'b':curve.b,'G':curve.G,'n':curve.n})
        self.table.setRowCount(curve.n)
        for i in range(1,curve.n+1):
            q=scalar_mult(curve,i,curve.G)
            self.table.setItem(i-1,0,QTableWidgetItem(str(i)))
            self.table.setItem(i-1,1,QTableWidgetItem(str(q) if q is not None else 'O'))

PAGES=[CurvePage]

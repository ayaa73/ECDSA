"""P1 Learn wizard: the curve and its generator."""
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.gui.learn.wizard import LearnPage, LearnState
from ecdsa_edu.gui.tabs.curve_explorer_tab import finite_field_figure

class CurvePage(LearnPage):
    title = 'Step 1: the curve and G'

    HELP = (
        "This page introduces the elliptic curve and its generator point G. "
        "The generator is used to produce other points through repeated addition. "
        "For small curves, the page displays the valid points and a table of multiples of G. "
        "Enable real-size numbers to explore the parameters of secp256k1."
    )
    def __init__(self,parent=None):
        super().__init__(parent)
        self.plot=FigureCanvasQTAgg(finite_field_figure(get_curve('toy-17')))
        self.layout().insertWidget(3,self.plot)
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['k','kG'])
        self.layout().addWidget(self.table)


    def enter(self, st: LearnState) -> None:
        if st.curve is None:
            st.curve = get_curve('toy-17')

        curve = st.curve

        self.set_text(
            'An elliptic curve consists of points satisfying an equation '
            'over a mathematical field. The generator G is a starting point '
            'used to produce other points through repeated addition. '
            'These operations form the mathematical foundation of ECDSA.'
        )

        self.set_formula(
            f'y² = x³ + ({curve.a})x + ({curve.b}) (mod p)'
        )

        self.set_values({
            'curve': curve.name,
            'p': curve.p,
            'a': curve.a,
            'b': curve.b,
            'G': curve.G,
            'n': curve.n,
            'h': curve.h
        })

        if curve.p < 5000:
            self.plot.figure = finite_field_figure(curve)
            self.plot.figure.set_canvas(self.plot)  # link the new figure to this canvas so resizing/redraws work
            self.plot.draw_idle()
            self.plot.show()
            self.table.show()

            self.table.setRowCount(curve.n)

            for i in range(1, curve.n + 1):
                q = scalar_mult(curve, i, curve.G)
                self.table.setItem(
                    i - 1, 0, QTableWidgetItem(str(i))
                )
                self.table.setItem(
                    i - 1, 1,
                    QTableWidgetItem(
                        str(q) if q is not None else 'O'
                    )
                )
        else:
            self.plot.hide()
            self.table.setRowCount(0)
            self.table.hide()


PAGES=[CurvePage]

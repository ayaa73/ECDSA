"""Key Collision: synthetic ECDSA nonce-reuse puzzle."""
from hashlib import sha256
from secrets import randbelow, token_hex
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QScrollArea, QFrame, QComboBox, QApplication)
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.gui.app import current_theme, theme_colors

def refresh_property(widget, name, value):
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def new_puzzle(curve):
    n = curve.n
    while True:
        d, k = randbelow(n-1)+1, randbelow(n-1)+1
        r = scalar_mult(curve, k, curve.G)[0] % n
        messages = ['Puzzle message '+token_hex(4) for _ in range(2)]
        z = [int.from_bytes(sha256(m.encode()).digest(), 'big') >> max(0,256-n.bit_length()) for m in messages]
        s = [pow(k,-1,n)*(v+r*d)%n for v in z]
        if r and all(s) and s[0]!=s[1]:
            return dict(d=d,k=k,r=r,z=z,s=s,messages=messages,Q=scalar_mult(curve,d,curve.G))


class CollisionDiagram(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedHeight(195); self.r='?'; self.k='?'; self.correct=False
        QApplication.instance().installEventFilter(self)
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.DynamicPropertyChange and event.propertyName() == b'theme':
            self.update()
        return super().eventFilter(obj, event)
    def paintEvent(self,event):
        colors = theme_colors(current_theme())
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width()/600, self.height()/195)
        width = min(1100, self.width()/scale)
        p.translate((self.width()-width*scale)/2, (self.height()-195*scale)/2)
        p.scale(scale, scale)
        center = width/2
        card_width = min(360, width*0.38)
        left, right = width*0.06, width*0.94-card_width
        def card(x,y,w,h,fill,edge):
            p.setPen(QPen(QColor(edge),1.2)); p.setBrush(QColor(fill)); p.drawRoundedRect(QRectF(x,y,w,h),12,12)
        def text(x,y,w,h,t,color,size=14,bold=False):
            f=p.font(); f.setPixelSize(size); f.setBold(bold); p.setFont(f); p.setPen(QColor(color)); p.drawText(QRectF(x,y,w,h),Qt.AlignmentFlag.AlignCenter,t)
        def line(a,b):
            p.setPen(QPen(QColor(colors['accent']),2.5)); p.drawLine(QPointF(*a),QPointF(*b))
        for i,x in enumerate((left,right)):
            card(x,4,card_width,65,colors['panel'],colors['border'])
            text(x,6,card_width,25,f'SIGNATURE {i+1}',colors['muted'],15,True)
            card(x+card_width*.15,33,card_width*.7,28,colors['pink'],colors['pink'])
            text(x,33,card_width,28,'r = '+self.r,colors['pastel_text'],19,True)
        for x in (left+card_width/2,right+card_width/2):
            line((x,69),(x,87)); line((x,87),(center,87))
        p.setBrush(QColor(colors['accent'])); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QRectF(center-7,80,14,14)); line((center,94),(center,105))
        nonce_width = min(340,width*.42)
        card(center-nonce_width/2,105,nonce_width,52,colors['mint'] if self.correct else colors['accent'],colors['accent'])
        c=colors['ok'] if self.correct else colors['accent_text']
        text(center-nonce_width/2,107,nonce_width,20,'SHARED NONCE',c,14,True)
        text(center-nonce_width/2,127,nonce_width,27,'k = '+self.k,c,22,True)
        line((center,157),(center,173)); line((center-5,168),(center,173)); line((center+5,168),(center,173))
        text(center-200,175,400,20,'Private key recovery',colors['accent'],16,True)
        p.end()


class KeyCollisionTab(QWidget):
    HELP='Recover the nonce and private key from two synthetic signatures using the same nonce. Enter decimal integers or hexadecimal with a 0x prefix. Mathematical assistance provides formulas, not solutions. Choose toy-17 or toy-97 for hand calculations.'
    def __init__(self,state=None):
        super().__init__()
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        panel=QWidget(); panel.setObjectName('collisionPanel'); scroll.setWidget(panel)
        layout=QVBoxLayout(panel); layout.setContentsMargins(16,8,16,8); layout.setSpacing(8)
        header=QHBoxLayout(); layout.addLayout(header)
        title=QLabel('Key Collision'); title.setProperty('heading','hero'); header.addWidget(title); header.addStretch()
        reset=QPushButton('New puzzle'); reset.setObjectName('secondary'); reset.clicked.connect(self.reset); header.addWidget(reset)
        intro=QHBoxLayout(); layout.addLayout(intro)
        intro.addWidget(self.label('Two signatures. One shared nonce. A hidden private key.'),1)
        self.selector=QComboBox(); self.selector.addItems(['toy-17','toy-97']); self.selector.setMinimumWidth(120); intro.addWidget(self.selector)
        self.diagram=CollisionDiagram(); layout.addWidget(self.diagram)
        evidence=QHBoxLayout(); layout.addLayout(evidence); self.evidence=[]
        for i in range(2):
            card=QFrame(); card.setProperty('card','white'); box=QVBoxLayout(card); box.setContentsMargins(12,8,12,8); box.setSpacing(4); box.addWidget(self.label(f'MESSAGE {i+1}',True)); lab=self.label(''); lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); box.addWidget(lab); self.evidence.append(lab); evidence.addWidget(card,1)
        self.params=self.label(''); self.params.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.params)
        card=QFrame(); card.setProperty('card','white'); form=QHBoxLayout(card); form.setContentsMargins(12,8,12,8); form.setSpacing(12); layout.addWidget(card)
        self.inputs=[]; self.marks=[]
        for name in ('Recover the shared nonce (k)','Recover the private key (d)'):
            column=QVBoxLayout(); column.setSpacing(4); form.addLayout(column,1); column.addWidget(self.label(name,True)); row=QHBoxLayout(); field=QLineEdit(); field.setProperty('mono',True); field.setPlaceholderText('Decimal or 0x hexadecimal'); mark=QLabel(''); row.addWidget(field,1); row.addWidget(mark); column.addLayout(row); self.inputs.append(field); self.marks.append(mark); field.textChanged.connect(self.changed); field.returnPressed.connect(self.submit)
        actions=QHBoxLayout(); layout.addLayout(actions)
        self.unlock=QPushButton('Unlock private key'); self.unlock.setProperty('primary',True); self.unlock.clicked.connect(self.submit); actions.addWidget(self.unlock,1)
        self.feedback=self.label(''); self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter); self.feedback.hide(); layout.addWidget(self.feedback)
        assist=QPushButton('Mathematical assistance  ▾'); assist.setObjectName('secondary'); assist.setCheckable(True); actions.addWidget(assist,1)
        self.formulas=self.label('k = (z₁ − z₂)(s₁ − s₂)⁻¹ mod n\n\nd = (s₁k − z₁)r⁻¹ mod n\n\nCheck: Q = dG. Use the modular inverse, not ordinary division.'); self.formulas.setProperty('formula',True); self.formulas.setProperty('mono',True); self.formulas.hide(); layout.addWidget(self.formulas); assist.toggled.connect(self.formulas.setVisible)
        layout.addStretch(); self.selector.currentTextChanged.connect(self.reset); self.reset()
    @staticmethod
    def label(text,bold=False):
        l=QLabel(text); l.setWordWrap(True); l.setTextFormat(Qt.TextFormat.PlainText)
        if bold: l.setStyleSheet('font-weight:bold;')
        return l
    def set_curve(self,curve):
        # The puzzle selector is intentionally independent of the global curve.
        pass
    def short(self,v):
        s=str(v); return s if len(s)<18 else s[:7]+'…'+s[-6:]
    def reset(self,*args):
        self.curve=get_curve(self.selector.currentText()); self.puzzle=new_puzzle(self.curve); p=self.puzzle
        for i,l in enumerate(self.evidence):
            l.setText(f"{p['messages'][i]}\nz = {p['z'][i]}     r = {p['r']}     s = {p['s'][i]}")
        self.params.setText(f"{self.selector.currentText()}  |  n = {self.curve.n}    |    Q = {p['Q']}")
        self.diagram.r=self.short(p['r']); self.diagram.setToolTip('Shared r = '+str(p['r']))
        for f in self.inputs: f.clear()
        self.changed()
    def changed(self,*args):
        self.feedback.hide(); self.diagram.correct=False; self.diagram.k=self.inputs[0].text().strip()[:16] or '?'; self.diagram.update()
        for m in self.marks: m.clear()
        self.unlock.setEnabled(all(f.text().strip() for f in self.inputs))
    def submit(self):
        if not self.unlock.isEnabled(): return
        try:
            vals=[int(t,16) if t.lower().startswith('0x') else int(t,10) for t in (f.text().strip() for f in self.inputs)]
        except ValueError:
            self.feedback.setText('Enter valid integers.'); refresh_property(self.feedback,'result','bad'); self.feedback.show(); return
        p=self.puzzle; ok=[vals[0]==p['k'],vals[1]==p['d'] and scalar_mult(self.curve,vals[1],self.curve.G)==p['Q']]
        for m,v in zip(self.marks,ok): m.setText('✓' if v else '✗'); refresh_property(m,'kind','ok' if v else 'error')
        self.diagram.correct=ok[0]; self.diagram.k=self.short(vals[0]); self.diagram.update()
        self.feedback.setText('🔓 Private key unlocked!\nThe recovered key matches the original public key.' if all(ok) else 'Key recovery incomplete. Check the marked calculations.')
        refresh_property(self.feedback,'result','good' if all(ok) else 'bad'); self.feedback.show()

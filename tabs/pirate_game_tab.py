"""Self-contained educational pirate adventure for the ECDSA Lab."""
import html
import math
import random
from hashlib import sha256
from secrets import randbelow
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import (QPainter, QColor, QPen, QPolygonF, QPainterPath,
                           QLinearGradient, QRadialGradient, QFont, QFontMetrics)
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QLineEdit, QScrollArea, QFrame, QDialog)
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.curve import scalar_mult, point_add

# ───────────────────────────── drawing helpers ─────────────────────────────
def ell(p, x, y, w, h, c):
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(c)); p.drawEllipse(QRectF(x, y, w, h))

def rct(p, x, y, w, h, c, r=4):
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(c)); p.drawRoundedRect(QRectF(x, y, w, h), r, r)

def poly(p, pts, c):
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(c)); p.drawPolygon(QPolygonF([QPointF(*v) for v in pts]))

def line(p, x1, y1, x2, y2, c, w=2):
    p.setPen(QPen(QColor(c), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

def txt(p, rect, s, px, color='#ffffff', align=Qt.AlignmentFlag.AlignCenter):
    f = QFont(p.font()); f.setPixelSize(int(px)); f.setBold(True); p.setFont(f)
    p.setPen(QColor(color)); p.drawText(rect, align, s)

def outlined(p, cx, cy, s, px, fill='#ffd35c', outline='#3a2411', lw=7):
    """Big arcade-style lettering: coloured fill with a thick dark outline."""
    f = QFont('Georgia'); f.setPixelSize(max(8, int(px))); f.setBold(True)
    path = QPainterPath(); path.addText(0.0, 0.0, f, s)
    br = path.boundingRect(); path.translate(cx - br.center().x(), cy - br.center().y())
    p.setPen(QPen(QColor(outline), lw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(fill)); p.drawPath(path)

def plank(p, r):
    g = QLinearGradient(r.topLeft(), r.bottomLeft()); g.setColorAt(0, QColor('#7a4e28')); g.setColorAt(1, QColor('#4a2d17'))
    p.setPen(QPen(QColor('#24140a'), 3)); p.setBrush(g); p.drawRoundedRect(r, 11, 11)

def heart(p, x, y, s, full):
    path = QPainterPath(); path.moveTo(x + s / 2, y + s * 0.92)
    path.cubicTo(x - s * 0.25, y + s * 0.45, x + s * 0.05, y - s * 0.2, x + s / 2, y + s * 0.28)
    path.cubicTo(x + s * 0.95, y - s * 0.2, x + s * 1.25, y + s * 0.45, x + s / 2, y + s * 0.92)
    p.setPen(QPen(QColor('#24140a'), 2))
    p.setBrush(QColor('#e8453c') if full else QColor('#3a2411')); p.drawPath(path)
    if full: ell(p, x + s * 0.16, y + s * 0.14, s * 0.2, s * 0.14, '#ffb3ab')

def draw_captain(p):
    """Captain Finn, feet at the origin."""
    rct(p, -12, -29, 24, 29, '#bd4738', 6)
    rct(p, -12, -13, 24, 4, '#3a2a1c', 1); rct(p, -3, -14, 6, 6, '#f2c14e', 1)
    ell(p, -2, -26, 4, 4, '#f2c14e'); ell(p, -2, -20, 4, 4, '#f2c14e')
    ell(p, -15, -54, 30, 30, '#f3c18b')
    poly(p, [(-27, -50), (-19, -67), (0, -61), (19, -67), (27, -50)], '#373039')
    ell(p, -4, -64, 8, 6, '#e9e2d0')
    ell(p, 2, -44, 10, 8, '#373039'); ell(p, -8, -43, 4, 4, '#373039')
    line(p, 3, -41, -12, -52, '#373039', 1.5)
    p.setPen(QPen(QColor('#8a4b2a'), 1.6)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawArc(QRectF(-8, -37, 14, 8), 200 * 16, 140 * 16)

def draw_parrot(p):
    poly(p, [(-3, -3), (-9, 10), (1, 2)], '#e8453c')
    ell(p, -5, -15, 10, 15, '#35b36a'); ell(p, -6, -11, 6, 9, '#2d8dd6')
    ell(p, -3, -21, 9, 9, '#35b36a'); poly(p, [(5, -18), (10, -16), (5, -14)], '#f5a623'); ell(p, 3, -19, 2.5, 2.5, '#111')


# ───────────────────────────── the game scene ─────────────────────────────
class SeaScene(QWidget):
    """Animated sea, islands, ship, HUD — and the dialogue panel the questions appear in."""
    DW, DH = 720, 260
    CENTERS = [(182, 185), (400, 150), (625, 115)]
    SCALES = [1.0, 0.92, 0.84]
    NAMES = ['Key Island', 'Signature Cove', 'Treasure Island']

    def __init__(self):
        super().__init__()
        self.setMinimumSize(660, 680)
        self.mode = 'title'          # title | play | win | lose
        self.stage = 0; self.hp = 3; self.gold = 0; self.qnum = 0; self.qtotal = 4; self.max_gold = 400
        self.inventory = ''; self.t = 0
        self.ship = list(self.dock(0)); self.target = self.dock(0); self.moving = False
        self.shake = 0.0; self.flash = 0.0; self.chest = 0.0; self.sink = 0.0; self.squawk = 0
        self.coins = []; self.floats = []
        self.confetti = []; self.fired = False; self.cannon_t = 0

        lay = QVBoxLayout(self); lay.setContentsMargins(12, 10, 12, 12)
        top = QHBoxLayout(); top.addStretch(1)
        self.restart_btn = QPushButton('Restart voyage'); self.restart_btn.setObjectName('restart')
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor); top.addWidget(self.restart_btn)
        lay.addLayout(top); lay.addStretch(1)
        self.dialog = QFrame(); self.dialog.setObjectName('dialog'); self.dialog.setMinimumHeight(380)
        lay.addWidget(self.dialog)
        dl = QHBoxLayout(self.dialog); dl.setContentsMargins(14, 14, 16, 14); dl.setSpacing(14)
        dl.addWidget(CaptainPortrait(), 0, Qt.AlignmentFlag.AlignTop)
        self.content = QVBoxLayout(); self.content.setSpacing(8); dl.addLayout(self.content, 1)

        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)

    def showEvent(self, e): self.timer.start(33); super().showEvent(e)
    def hideEvent(self, e): self.timer.stop(); super().hideEvent(e)

    # ── state ──
    def dock(self, j):
        cx, cy = self.CENTERS[j]; sc = self.SCALES[j]; return (cx - 112 * sc, cy + 30 * sc)
    def set_stage(self, stage): self.stage = stage; self.target = self.dock(min(stage, 2))
    def snap(self): self.ship = list(self.target)
    def hit(self): self.shake = 9.0; self.flash = 1.0
    def burst(self, n, x, y):
        for _ in range(n): self.coins.append([x, y, random.uniform(-2.6, 2.6), random.uniform(-5.8, -2.4), random.randint(40, 75)])
    def cheer(self, earned):
        self.burst(26, self.ship[0], self.ship[1] - 30); self.floats.append([self.ship[0], self.ship[1] - 80, f'+{earned}', 55])

    CONFETTI = ['#ff4d6d', '#ffd23f', '#3ddc97', '#4cc9f0', '#b980f0', '#ff9f1c', '#ffffff']
    def cannon_pos(self, side):
        W = self.width(); sh = self.dialog.y() if self.dialog.y() > 0 else int(self.height() * 0.55)
        return (34, sh - 8) if side == 0 else (W - 34, sh - 8)

    def fire_confetti(self):
        for side in (0, 1):
            cx, cy = self.cannon_pos(side); d = 1 if side == 0 else -1
            ox = cx + d * 55 * math.cos(math.radians(55)); oy = cy - 55 * math.sin(math.radians(55))
            for _ in range(70):
                a = math.radians(random.uniform(55, 85)); sp = random.uniform(9, 20)
                self.confetti.append([ox, oy, d * math.cos(a) * sp, -math.sin(a) * sp, random.uniform(0, 360), random.uniform(-9, 9),
                                      random.uniform(0, 6.28), random.choice(self.CONFETTI), random.uniform(6, 11), random.randint(150, 230)])

    def tick(self):
        self.t += 1
        dx = self.target[0] - self.ship[0]; dy = self.target[1] - self.ship[1]
        self.moving = abs(dx) + abs(dy) > 3
        if self.moving: self.ship[0] += dx * 0.045; self.ship[1] += dy * 0.045
        else: self.ship = list(self.target)
        if self.mode == 'win' and not self.moving:
            self.chest = min(1.0, self.chest + 0.025)
            if self.chest > 0.4 and self.t % 3 == 0: self.burst(1, 651, 92)
        if self.mode == 'win' and self.chest > 0.4:
            if not self.fired: self.fired = True; self.cannon_t = 0
            if self.cannon_t in (0, 16, 32, 52, 76): self.fire_confetti()
            self.cannon_t += 1
        for c in self.confetti:
            c[0] += c[2]; c[1] += c[3]; c[2] = c[2] * 0.985 + math.sin(self.t * 0.15 + c[6]) * 0.12; c[3] += 0.26; c[3] *= 0.985; c[4] += c[5]; c[9] -= 1
        H = self.height() + 20; self.confetti = [c for c in self.confetti if c[9] > 0 and c[1] < H]
        if self.mode == 'lose': self.sink = min(1.0, self.sink + 0.012)
        self.shake *= 0.86; self.flash *= 0.9
        if self.shake < 0.3: self.shake = 0.0
        self.squawk = max(0, self.squawk - 1)
        for c in self.coins: c[0] += c[2]; c[1] += c[3]; c[3] += 0.18; c[4] -= 1
        self.coins = [c for c in self.coins if c[4] > 0]
        for f in self.floats: f[1] -= 0.8; f[3] -= 1
        self.floats = [f for f in self.floats if f[3] > 0]
        self.update()

    # ── painting ──
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()
        sh = self.dialog.y() if self.dialog.y() > 0 else int(H * 0.55)
        top = 96
        s = max(0.3, min(W / self.DW, (sh - top) / self.DH))
        ox = (W - self.DW * s) / 2; oy = top + ((sh - top) - self.DH * s) / 2
        hz = oy + 78 * s
        g = QLinearGradient(0, 0, 0, hz); g.setColorAt(0, QColor('#3f9fe0')); g.setColorAt(1, QColor('#c3ebf4')); p.fillRect(QRectF(0, 0, W, hz), g)
        g = QLinearGradient(0, hz, 0, H); g.setColorAt(0, QColor('#4bbdd1')); g.setColorAt(1, QColor('#14607f')); p.fillRect(QRectF(0, hz, W, H - hz), g)
        p.save()
        p.translate(ox + random.uniform(-1, 1) * self.shake, oy + random.uniform(-1, 1) * self.shake); p.scale(s, s)
        xmin = -ox / s - 40; xmax = (W - ox) / s + 40; ymax = (H - oy) / s
        self.draw_sky(p, xmin, xmax); self.draw_waves(p, xmin, xmax, ymax)
        for j in (2, 1, 0): self.draw_island(p, j)
        self.draw_ship(p); self.draw_fx(p)
        p.restore()
        if self.flash > 0.02: p.fillRect(QRectF(0, 0, W, sh), QColor(220, 30, 30, int(110 * self.flash)))
        self.draw_hud(p, W); self.draw_overlay(p, W, sh)
        p.end()

    def draw_sky(self, p, xmin, xmax):
        g = QRadialGradient(QPointF(560, 36), 70); g.setColorAt(0, QColor(255, 246, 194, 255)); g.setColorAt(0.35, QColor(255, 230, 140, 230)); g.setColorAt(1, QColor(255, 230, 140, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(g); p.drawEllipse(QPointF(560, 36), 70, 70)
        span = xmax - xmin
        for bx, by, sc, sp in [(80, 34, 1.0, 0.12), (330, 22, 0.8, 0.08), (470, 52, 1.2, 0.15)]:
            cx = xmin + ((bx - xmin + self.t * sp) % span)
            for dx, dy, w, h in [(0, 8, 70, 22), (18, 0, 50, 26), (42, 8, 56, 20)]:
                ell(p, cx + dx * sc, by + dy * sc, w * sc, h * sc, QColor(255, 255, 255, 235))
        p.fillRect(QRectF(xmin, 76, xmax - xmin, 6), QColor(255, 255, 255, 70))

    def draw_waves(self, p, xmin, xmax, ymax):
        p.setBrush(Qt.BrushStyle.NoBrush); y = 88; row = 0
        while y < ymax:
            p.setPen(QPen(QColor(255, 255, 255, 70 + (row % 3) * 22), 2))
            x = xmin - 64 + (row % 2) * 32 + (self.t * (0.35 + 0.15 * (row % 3))) % 64
            while x < xmax: p.drawArc(QRectF(x, y, 20, 7), 0, 180 * 16); x += 64
            y += 22; row += 1

    def draw_island(self, p, j):
        cx, cy = self.CENTERS[j]; sc = self.SCALES[j]
        done = j < self.stage or self.mode == 'win'
        cur = (j == min(self.stage, 2) and self.mode == 'play')
        p.save(); p.translate(cx, cy); p.scale(sc, sc)
        if cur: ell(p, -102, -44, 204, 96, QColor(255, 224, 120, int(45 + 35 * math.sin(self.t * 0.12))))
        ell(p, -92, -30, 184, 72, QColor(95, 200, 210, 110))
        ell(p, -83, -27, 166, 65, '#58a9b7'); ell(p, -78, -32, 156, 60, '#f5d18a'); ell(p, -59, -28, 118, 39, '#8bb76b')
        sway = math.sin(self.t * 0.05 + j) * 2; bob = math.sin(self.t * 0.1 + j) * 3
        rct(p, -48, -65, 8, 48, '#92623a')
        for dx, dy in [(-24, -10), (5, -23), (18, -8)]: ell(p, -45 + dx + sway, -67 + dy, 34, 15, '#40864c')
        if j == 0:
            rct(p, 15, -40, 30, 32, '#b68b55'); poly(p, [(9, -40), (30, -57), (51, -40)], '#895332'); rct(p, 25, -24, 10, 16, '#5a3a1e')
            p.setPen(QPen(QColor('#f2b01e'), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(-20, -62 + bob, 12, 12)); p.drawLine(QPointF(-8, -56 + bob), QPointF(10, -56 + bob))
            p.drawLine(QPointF(5, -56 + bob), QPointF(5, -50 + bob)); p.drawLine(QPointF(10, -56 + bob), QPointF(10, -50 + bob))
        elif j == 1:
            poly(p, [(8, -10), (16, -42), (32, -52), (50, -34), (58, -10)], '#8c919b')
            poly(p, [(32, -52), (50, -34), (58, -10), (40, -10)], '#6f747e')
            rct(p, -20, -64 + bob, 24, 30, '#f4e2b0', 4); ell(p, -22, -66 + bob, 28, 7, '#e0c98a'); ell(p, -22, -38 + bob, 28, 7, '#e0c98a')
            for k in range(3): line(p, -15, -55 + k * 6 + bob, -1, -55 + k * 6 + bob, '#8a5a2b', 1.5)
        else:
            for a, b, c2, d in [(-45, -14, -27, 2), (-27, -14, -45, 2)]: line(p, a, b, c2, d, '#c0392b', 4)
            o = self.chest
            if o > 0:
                g = QRadialGradient(QPointF(31, -40), 30 + 70 * o); g.setColorAt(0, QColor(255, 235, 130, int(200 * o))); g.setColorAt(1, QColor(255, 235, 130, 0))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(g); p.drawEllipse(QPointF(31, -40), 30 + 70 * o, 30 + 70 * o)
            p.save(); p.translate(10, -34)
            rct(p, 0, 0, 42, 26, '#92582e'); rct(p, 7, 0, 6, 26, '#e9b84e', 1); rct(p, 29, 0, 6, 26, '#e9b84e', 1)
            if o > 0:
                ell(p, 1, -4, 40, 10, '#f6c943'); ell(p, 6, -7, 10, 6, '#ffe27a'); ell(p, 22, -8, 12, 6, '#ffe27a')
            p.save(); p.translate(0, -o * 14)
            rct(p, -2, -13, 46, 14, '#b47b3b', 5); rct(p, 7, -13, 6, 14, '#e9b84e', 1); rct(p, 29, -13, 6, 14, '#e9b84e', 1)
            if o == 0: rct(p, 18, -4, 7, 7, '#f6c943', 2)
            p.restore()
            if o > 0:
                for k in range(6):
                    a = self.t * 0.09 + k * 1.1
                    ell(p, 21 + math.cos(a) * (18 + k * 3), -14 + math.sin(a * 1.3) * (16 + k * 2), 4, 4, QColor(255, 255, 255, 220))
            p.restore()
        # pennant + badge + name ribbon
        line(p, 70, -26, 70, -78, '#5a3a1e', 3)
        poly(p, [(70, -78), (96, -71), (70, -64)], '#43a047' if done else '#f2b01e' if cur else '#9aa5a0')
        col = '#43844c' if done else '#d9962b' if cur else '#7e8a84'
        if cur:
            ph = (self.t % 30) / 30; p.setPen(QPen(QColor(255, 220, 120, int(200 * (1 - ph))), 3)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(0, 19), 13 + 12 * ph, 13 + 12 * ph)
        p.setPen(QPen(QColor('#24140a'), 2)); p.setBrush(QColor(col)); p.drawEllipse(QPointF(0, 19), 13, 13)
        txt(p, QRectF(-13, 6, 26, 26), '✓' if done else str(j + 1), 15)
        rct(p, -64, 39, 128, 22, QColor(58, 36, 17, 225), 7); txt(p, QRectF(-64, 39, 128, 22), self.NAMES[j], 13, '#ffe9b0')
        if cur and not self.moving:
            b = abs(math.sin(self.t * 0.15)) * 8
            p.setPen(QPen(QColor('#3a2411'), 2)); p.setBrush(QColor('#ffd35c')); p.drawPolygon(QPolygonF([QPointF(-10, -104 - b), QPointF(10, -104 - b), QPointF(0, -90 - b)]))
        p.restore()

    def draw_ship(self, p):
        x, y = self.ship; bob = math.sin(self.t * 0.08) * 2.5; rock = math.sin(self.t * 0.06) * 2
        p.save()
        if self.mode == 'lose': p.setOpacity(1 - 0.6 * self.sink)
        p.translate(x, y + bob + self.sink * 26); p.rotate(rock + self.sink * 28)
        if self.moving:
            for k in range(4): ell(p, -62 - k * 18, 9 + (k % 2) * 3, 24 - k * 4, 5, QColor(255, 255, 255, 160 - k * 36))
        ell(p, -54, 9, 108, 9, QColor(255, 255, 255, 150))
        rct(p, -3, -96, 6, 90, '#5c3a21', 2)
        poly(p, [(-48, -6), (48, -6), (36, 18), (-36, 18)], '#8a5330')
        poly(p, [(-48, -6), (-48, -22), (-26, -22), (-26, -6)], '#7a4726')
        rct(p, -48, -10, 96, 5, '#5c3519', 2)
        line(p, -44, 2, 42, 2, '#5c3519', 1.5); line(p, -40, 10, 38, 10, '#5c3519', 1.5)
        line(p, 47, -8, 70, -22, '#5c3519', 4)
        for px in (-14, 4, 22): ell(p, px - 3, 4, 6, 6, '#2a1a0e')
        p.setPen(QPen(QColor('#c9b07a'), 1.5))
        for pts, col in [((4, -90, 44, -84, 46, -44, 4, -30), '#fbf1d4'), ((-4, -82, -30, -76, -30, -48, -4, -40), '#f3e4bd')]:
            path = QPainterPath(); path.moveTo(pts[0], pts[1]); path.cubicTo(pts[2], pts[3], pts[4], pts[5], pts[6], pts[7]); path.closeSubpath()
            p.setBrush(QColor(col)); p.drawPath(path)
        rct(p, -26, -92, 64, 4, '#5c3a21', 2)
        line(p, 0, -96, 0, -114, '#5c3a21', 2); rct(p, 0, -118, 24, 16, '#1f1f24', 2)
        ell(p, 8.5, -114, 7, 7, '#f2f2f2'); line(p, 5, -104, 19, -100, '#f2f2f2', 1.4); line(p, 5, -100, 19, -104, '#f2f2f2', 1.4)
        p.save(); p.translate(-37, -22); p.scale(0.5, 0.5); draw_captain(p); p.restore()
        hop = abs(math.sin(self.t * 0.5)) * 7 if self.squawk else 0
        p.save(); p.translate(30, -10 - hop); draw_parrot(p); p.restore()
        p.restore()

    def draw_fx(self, p):
        for x, y, vx, vy, life in self.coins:
            p.setOpacity(min(1.0, life / 20)); ell(p, x - 5, y - 5, 10, 10, '#c58a14'); ell(p, x - 4, y - 4, 8, 8, '#ffd23f'); ell(p, x - 2.5, y - 3.5, 3, 3, '#fff3b0')
        for x, y, s, life in self.floats:
            p.setOpacity(min(1.0, life / 15)); outlined(p, x, y, s, 22, '#ffe27a', '#3a2411', 5)
        p.setOpacity(1.0)

    def draw_hud(self, p, W):
        if self.mode == 'title': return
        plank(p, QRectF(12, 10, 200, 76))
        for i in range(3): heart(p, 24 + i * 36, 18, 28, i < self.hp)
        p.setPen(QPen(QColor('#7a4f10'), 2)); p.setBrush(QColor('#ffd23f')); p.drawEllipse(QPointF(37, 65), 11, 11)
        txt(p, QRectF(26, 54, 22, 22), '$', 14, '#7a4f10')
        txt(p, QRectF(56, 52, 150, 26), f'{self.gold} gold', 20, '#ffe9a8', Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if self.inventory and self.mode == 'play':
            f = QFont(); f.setPixelSize(13); f.setBold(True); w = min(W - 24, QFontMetrics(f).horizontalAdvance('Inventory: ' + self.inventory) + 26)
            r = QRectF(12, 92, w, 26); p.setPen(QPen(QColor('#8a6a38'), 2)); p.setBrush(QColor(244, 226, 176, 240)); p.drawRoundedRect(r, 8, 8)
            txt(p, r, 'Inventory: ' + self.inventory, 13, '#4a2d17')
        if self.mode == 'play':
            r = QRectF(W / 2 - 100, 10, 200, 34); plank(p, r)
            txt(p, QRectF(W / 2 - 94, 10, 92, 34), f'Quest {min(self.qnum + 1, self.qtotal)}/{self.qtotal}', 15, '#ffe9b0')
            for k in range(self.qtotal):
                p.setPen(QPen(QColor('#24140a'), 2)); p.setBrush(QColor('#ffd23f') if k < self.qnum else QColor('#3a2411')); p.drawEllipse(QPointF(W / 2 + 14 + k * 22, 27), 7, 7)

    def draw_cannons(self, p):
        for side in (0, 1):
            x, y = self.cannon_pos(side); kick = max(0.0, 1 - self.cannon_t % 16 / 6) if self.cannon_t < 90 else 0
            p.save(); p.translate(x, y)
            if side: p.scale(-1, 1)
            p.rotate(-55); p.translate(-6 * kick, 0)
            rct(p, -10, -14, 60, 28, '#2b2d33', 8); rct(p, 44, -17, 14, 34, '#43464e', 4); rct(p, -14, -9, 8, 18, '#1b1c20', 4)
            if kick > 0.2: ell(p, 52, -16, 32 * kick, 32, QColor(255, 210, 80, int(230 * kick)))
            p.restore()
            rct(p, x - 22, y - 6, 44, 14, '#5c3519', 4); ell(p, x - 17, y - 14, 30, 30, '#6b4423'); ell(p, x - 10, y - 7, 16, 16, '#3a2411')
        for px, py, vx, vy, rot, vr, ph, col, sz, life in self.confetti:
            p.save(); p.translate(px, py); p.rotate(rot); p.scale(1, math.cos(self.t * 0.2 + ph))
            p.setOpacity(min(1.0, life / 30)); p.fillRect(QRectF(-sz / 2, -sz / 4, sz, sz / 2), QColor(col)); p.restore()
        p.setOpacity(1.0)

    def draw_overlay(self, p, W, sh):
        cx = W / 2; base = min(W / 720, sh / 380)
        if self.mode == 'title':
            p.fillRect(QRectF(0, 0, W, sh), QColor(10, 30, 50, 70))
            outlined(p, cx, sh * 0.22, 'PIRATES OF THE', 30 * base, '#fff1c9')
            outlined(p, cx, sh * 0.36, 'ELLIPTIC CURVE', 62 * base, '#ffd35c', '#3a2411', 10)
            r = QRectF(cx - 130 * base, sh * 0.50, 260 * base, 34 * base); plank(p, r); txt(p, r, 'The Lost Treasure', 18 * base, '#ffe9b0')
        elif self.mode == 'win' and self.chest > 0.4:
            self.draw_cannons(p)
            outlined(p, cx, sh * 0.27, 'TREASURE FOUND!', 50 * base, '#ffd35c', '#3a2411', 10)
            outlined(p, cx, sh * 0.39, f'{self.gold} / {self.max_gold} gold', 24 * base, '#ffffff', '#3a2411', 6)
        elif self.mode == 'lose' and self.sink > 0.2:
            p.fillRect(QRectF(0, 0, W, sh), QColor(10, 10, 30, int(90 * self.sink)))
            outlined(p, cx, sh * 0.27, 'SHIPWRECKED!', 50 * base, '#ff6b5a', '#2a0d0a', 10)
            outlined(p, cx, sh * 0.39, 'No lives remaining', 22 * base, '#ffffff', '#2a0d0a', 6)


class CaptainPortrait(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedSize(104, 128)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath(); clip.addRoundedRect(QRectF(3, 3, 98, 122), 12, 12); p.setClipPath(clip)
        g = QLinearGradient(0, 0, 0, 100); g.setColorAt(0, QColor('#6ab8e8')); g.setColorAt(1, QColor('#d7f1f2')); p.fillRect(QRectF(0, 0, 104, 128), g)
        p.fillRect(QRectF(0, 88, 104, 40), QColor('#2f93b0'))
        p.save(); p.translate(52, 112); p.scale(1.5, 1.5); draw_captain(p); p.restore()
        rct(p, 6, 104, 92, 18, '#4a2d17', 5); txt(p, QRectF(6, 104, 92, 18), 'Capt. Finn', 12, '#ffe9b0')
        p.setClipping(False); p.setPen(QPen(QColor('#4a2d17'), 4)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(QRectF(3, 3, 98, 122), 12, 12)
        p.end()


# ───────────────────────────── styling ─────────────────────────────
STYLE = """
QFrame#dialog { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f8e8bd, stop:1 #ead29a); border:5px solid #5b3a1e; border-radius:16px; }
QLabel { color:#3e2a14; background:transparent; }
QLabel#qtitle { font-size:15px; font-weight:bold; color:#8a4b12; }
QLabel#qbody { font-size:17px; font-weight:600; color:#2f2010; background:rgba(255,255,255,100); border:2px dashed #b99b65; border-radius:10px; padding:8px 12px; }
QLabel#speech { font-family:Georgia,'Times New Roman',serif; font-size:19px; font-weight:bold; color:#2f2010; background:#fffdf2; border:3px solid #5b3a1e; border-radius:16px; padding:14px 18px; }
QLabel#explain { font-size:15px; font-weight:600; color:#2f2010; background:rgba(255,255,255,150); border:2px solid #5c9a45; border-radius:10px; padding:8px 12px; }
QLabel#feedback { font-size:15px; font-weight:bold; padding:6px 10px; border-radius:8px; }
QLabel#feedback[kind="good"] { background:#cfe8b5; color:#235c1f; border:2px solid #5c9a45; }
QLabel#feedback[kind="bad"]  { background:#f6c9c3; color:#7a1f16; border:2px solid #c0483c; }
QLabel#feedback[kind="hint"] { background:#fbeaa6; color:#6a4a08; border:2px solid #d3a62a; }
QPushButton#crate { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ab743c, stop:1 #7a4a22); color:#fff3d6; border:3px solid #3f2610; border-radius:10px; font-size:19px; font-weight:bold; padding:11px 14px; text-align:left; }
QPushButton#crate:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #c98c4c, stop:1 #92592b); border-color:#ffd35c; }
QPushButton#crate:disabled { color:#cdb994; background:#6b4423; }
QPushButton#crate[state="right"] { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #6fc46a, stop:1 #3f8f3d); color:white; border-color:#1f5a1e; }
QPushButton#crate[state="wrong"] { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #d9574a, stop:1 #9c2e24); color:#ffe0dc; border-color:#5a1510; }
QPushButton#goBtn { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffe27a, stop:1 #e0a421); color:#3a2411; border:3px solid #7a4f10; border-radius:12px; font-size:18px; font-weight:bold; padding:11px 24px; }
QPushButton#goBtn:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #fff0a8, stop:1 #f0b832); }
QPushButton#goBtn:disabled { background:#cdbb8a; color:#8f8062; border-color:#9b8a5e; }
QPushButton#smallBtn { background:#d9b873; color:#4a2d17; border:2px solid #8a6a38; border-radius:8px; padding:7px 14px; font-size:13px; font-weight:bold; }
QPushButton#smallBtn:hover { background:#e8c987; }
QPushButton#smallBtn:disabled { color:#9b8a68; background:#e4d1a3; }
QLabel#storyFolio { font-size:12px; font-weight:bold; color:#8a4b12; letter-spacing:2px; }
QLabel#story { font-family:Georgia,'Times New Roman',serif; font-size:19px; color:#2f2010; background:rgba(255,248,226,170); border:2px dashed #b99b65; border-radius:10px; padding:14px 16px; }
QPushButton#restart { background:rgba(60,36,17,215); color:#ffe9b0; border:2px solid #2a170a; border-radius:8px; padding:6px 12px; font-weight:bold; font-size:13px; }
QPushButton#restart:hover { background:rgba(100,62,30,235); }
QLineEdit#answerEntry { background:#fff9e9; color:#3e2a14; border:3px solid #8a6a38; border-radius:10px; padding:10px 12px; font-size:19px; font-weight:bold; }
QDialog#tableDialog { background:#f4e2b0; }
QLabel#tableCell { background:rgba(255,255,255,120); border:1px solid #b99b65; border-radius:6px; padding:5px 8px; font-size:14px; font-weight:600; }
"""


def _restyle(w):
    w.style().unpolish(w); w.style().polish(w)


class PirateGameTab(QWidget):
    HELP = 'Sail through three islands: make a public key, sign a map, then check a signature and catch a forgery. Each answer comes with an explanation. Use hints or the curve table if needed. The game uses toy-17 only for hand calculations.'

    def __init__(self, state=None):
        super().__init__(); self.curve = get_curve('toy-17'); self.mode = 'guided'
        self.i = 0; self.hp = 3; self.gold = 0; self.questions = []; self.options = []
        self.solved = False; self.hinted = False; self.choice = ''
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); outer.addWidget(scroll)
        self.scene = SeaScene(); scroll.setWidget(self.scene); self.content = self.scene.content
        self.scene.restart_btn.clicked.connect(self.reset)
        self.reset()

    def set_curve(self, curve):
        pass  # Game deliberately stays on toy-17 regardless of toolbar selection.

    # ── small UI helpers ──
    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0); w = item.widget()
            if w: w.hide(); w.deleteLater()
            elif item.layout(): self._clear(item.layout()); item.layout().deleteLater()

    @staticmethod
    def _rich(s):
        """Escape plain text, then render inverses (k⁻¹) as a real superscript power."""
        return html.escape(s).replace('⁻¹', '<sup>&minus;1</sup>').replace('\n', '<br>')

    def label(self, s, name='qbody', layout=None):
        w = QLabel(self._rich(s)); w.setWordWrap(True); w.setTextFormat(Qt.TextFormat.RichText); w.setObjectName(name)
        (layout or self.content).addWidget(w); return w

    def button(self, s, fn, name='goBtn', layout=None):
        w = QPushButton(s); w.setObjectName(name); w.setCursor(Qt.CursorShape.PointingHandCursor); w.clicked.connect(fn)
        (layout or self.content).addWidget(w); return w

    def _feedback(self, text, kind):
        self.feedback.setText(self._rich(text)); self.feedback.setProperty('kind', kind); _restyle(self.feedback)

    # ── flow ──
    THANKS = [
        "Arrr, thank ye fer yer help, matey! Without yer sharp mind I'd still be lost at sea. The treasure be yours as much as mine!",
        "Yo ho ho! Ye cracked me key and sealed the map true. Thank ye, brave navigator. The Toy Seas be safe because o' ye!",
        "Blow me down! Ye signed that map like a born captain. Me heartfelt thanks, sailor. Ye've earned a place on me crew!",
    ]
    STORY = [
        "The bottle washed ashore at dusk, sealed with black wax.\n\nInside was a torn sea-map signed by Captain Finn, the most feared navigator of the Toy Seas, and a warning: no crew has ever proved the treasure is real.",
        "Three islands stand between you and the chest, and each is guarded by arithmetic instead of cannons.\n\nKey Island hides the captain's public key. Signature Cove is where you seal a map. Treasure Island's gatekeeper checks every seal, and he can spot a forged map.",
        "Only the holder of Finn's private key d can sign a map the crew will trust. You will work out his public key Q, seal a map with a signature (r, s), then play the gatekeeper and check it, all by hand.\n\nThe sea is small: every number lives modulo 17, so each step fits on a scrap of parchment.",
        "Mind your lives, sailor. Three wrong answers and the ship goes down. The parrot knows a few hints, but each one costs you 25 gold.\n\nHow do you want to sail?",
    ]

    def reset(self):
        self.i = 0; self.hp = 3; self.gold = 0; self.questions = []; self.options = []
        sc = self.scene; sc.mode = 'title'; sc.hp = 3; sc.gold = 0; sc.chest = 0.0; sc.sink = 0.0; sc.coins = []; sc.floats = []; sc.confetti = []; sc.fired = False; sc.cannon_t = 0
        sc.qnum = 0; sc.inventory = ''; sc.set_stage(0); sc.snap()
        self.story_page = 0; self.show_story()

    # ── story preview (typed page by page, like the Case File intro) ──
    def show_story(self):
        self._clear(self.content)
        n = len(self.STORY); text = self.STORY[self.story_page]; last = self.story_page == n - 1
        self.label(f'LOGBOOK  ·  PAGE {self.story_page + 1} OF {n}', 'storyFolio')
        self.story_label = self.label('', 'story'); self.story_label.setMinimumHeight(150); self.story_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.content.addStretch(1)
        row = QHBoxLayout(); row.setSpacing(10); self.content.addLayout(row)
        self.button('Skip story', self.end_story, 'smallBtn', row); row.addStretch(1)
        self.story_next = self.button('Choose your voyage ▸' if last else 'Next ▸', self.next_story, 'goBtn', row)
        self.story_label.setText(self._rich(text)); self.story_next.setEnabled(True); self.story_next.setFocus()

    def next_story(self):
        if self.story_page < len(self.STORY) - 1: self.story_page += 1; self.show_story()
        else: self.end_story()

    def end_story(self):
        self._clear(self.content)
        self.label('Ahoy, matey! Solve the cryptographic challenges to find the lost treasure. Choose your difficulty.')
        self.content.addStretch(1)
        self.button('Easy Seas  —  pick from four answers', lambda: self.start('guided'))
        self.button("Captain's Challenge  —  type your own answers", lambda: self.start('expert'))
        self.button('Demo Mode  —  fixed answers for presentations', lambda: self.start('demo'), 'smallBtn')
        self.content.addStretch(1)

    def start(self, mode):
        self.mode = mode; self.build_questions(); self.render()

    # Each map has a "forged twin" that differs by exactly one letter.
    MAPS = [
        ('Meet at Skull Rock at dawn.', 'Meet at Skull Rock at down.'),
        ('Bury the gold under the palm tree.', 'Bury the gold under the pale tree.'),
        ('Sail north when the moon is full.', 'Sail north when the moon is dull.'),
        ('The parrot knows the secret.', 'The carrot knows the secret.'),
        ('Hoist the black flag at midnight.', 'Hoist the black flap at midnight.'),
        ('Beware the reef near Crab Cove.', 'Beware the reef near Crab Cave.'),
    ]

    def build_questions(self):
        c = self.curve; G = c.G; n = c.n; p = 17
        mul = lambda k, P=G: scalar_mult(c, k, P)
        # SHA-256 truncated to the order bit length, as in ECDSA.
        def hash_int(m): return int.from_bytes(sha256(m.encode()).digest(), 'big') >> (256 - n.bit_length())
        def check_sig(m, Q, r, s):
            """Bob's verification. Returns (valid, w, u1, u2, P)."""
            w = pow(s, -1, n); z_ = hash_int(m); u1 = z_ * w % n; u2 = r * w % n
            P = point_add(c, mul(u1), mul(u2, Q))
            return (P is not None and P[0] % n == r), w, u1, u2, P

        demo = self.mode == 'demo'
        original, forged = self.MAPS[0] if demo else self.MAPS[randbelow(len(self.MAPS))]
        z = hash_int(original)
        while True:
            # Demo mode uses fixed values (d=3, k=2) so the answers can be written down in advance.
            d, k = (3, 2) if demo else (3 + randbelow(n - 3), 1 + randbelow(n - 1))
            Q = mul(d); K = mul(k); r = K[0] % n; s = pow(k, -1, n) * (z + r * d) % n
            if r and s: break
        kinv = pow(k, -1, n)
        self.inventory = (d, Q, r, s)

        # Bob's check on the genuine map, and on the forged twin (one letter changed).
        _, w, u1, u2, P = check_sig(original, Q, r, s)
        if check_sig(forged, Q, r, s)[0]:
            # On this tiny curve a wrong signature can pass by luck (about 1 in 19): pick another one-letter change.
            for i in range(len(original) - 1, -1, -1):
                cand = original[:i] + ('x' if original[i] != 'x' else 'y') + original[i + 1:]
                if not check_sig(cand, Q, r, s)[0]: forged = cand; break
        ok2, w2, u12, u22, P2 = check_sig(forged, Q, r, s); z2 = hash_int(forged)
        fx = f'x(P) mod {n} = {P2[0] % n}' if P2 is not None else 'P is the point at infinity'

        def pt(P_): return 'O (infinity)' if P_ is None else str(P_)
        def uniq(pairs, answer):
            """Keep plausible wrong answers (value, note), dropping duplicates and the right answer."""
            seen = {str(answer)}; out = []
            for v, note in pairs:
                if v is None or str(v) in seen: continue
                seen.add(str(v)); out.append((str(v), note))
            return out

        # question: stage, title, body, answer, hint, explain, wrong [(value, note)], choices, shuffle, table
        def q(stage, title, body, answer, hint, explain, wrong=(), choices=None, shuffle=True, table=False):
            return dict(stage=stage, title=title, body=body, answer=str(answer), hint=hint, explain=explain,
                        wrong=uniq(wrong, answer), choices=choices, shuffle=shuffle, table=table)

        mirror = (Q[0], (-Q[1]) % p)
        self.questions = [
            q(0, 'Key Island — make the public key',
              f'Captain Finn\'s private key is d = {d}.\nG = {G}.\nCalculate his public key Q = d·G (add G to itself d times).',
              Q, 'Add G to itself, one step at a time (G, 2G, 3G, ...), modulo 17. The curve table has them all.',
              f'Q = d·G means adding G to itself d times: G → 2G → … → {d}G = {Q}. Q is public. Nobody can work '
              'backwards from Q to d, and that is what keeps the private key safe.',
              [(mul(d - 1), f'That is (d−1)·G = {mul(d - 1)}, one addition short.'),
               (mul(d + 1), f'That is (d+1)·G = {mul(d + 1)}, one addition too many.'),
               (mirror, 'Close! That is −Q, the mirror image: same x, flipped y.')], table=True),
            q(1, 'Signature Cove — find r',
              f'Original map: {original}\nIts truncated SHA-256 hash (fingerprint) is z = {z}.\n'
              f'Fresh secret nonce k = {k}, so kG = {K}.\nCalculate r = x(kG) mod {n}.',
              r, 'r only uses the x-coordinate of kG.',
              f'kG = {K}. Keep only the x-coordinate, reduced mod {n}: {K[0]} mod {n} = {r}. '
              f'So r = {r}. This is the first half of the signature, and it is public.',
              [(K[1] % n, 'That is the y-coordinate of kG. r uses x.'),
               (mul(k + 1)[0] % n if mul(k + 1) else None, 'That is x of (k+1)·G, one addition too many.'),
               (mul(k - 1)[0] % n if k > 1 and mul(k - 1) else None, 'That is x of (k−1)·G, one addition too few.')],
              table=True),
            q(1, 'Find the nonce inverse', f'Calculate k⁻¹ mod {n}, where k = {k}.',
              kinv, 'Find a number that, multiplied by k, leaves remainder 1 when divided by 19.',
              f'k⁻¹ is the number that gives 1 when multiplied by k, mod {n}. Check: {k} × {kinv} = {k * kinv} '
              f'= {k * kinv % n} (mod {n}). So k⁻¹ = {kinv}. We need it because s is built from k⁻¹.',
              [((n - k) % n, 'That is n − k, the negative of k, not its inverse.'),
               (k, 'k × k is not 1 (mod 19), so k is not its own inverse.'),
               ((kinv + 1) % n, 'Close, but k × that does not leave remainder 1.')]),
            q(1, 'Seal the map', f'Calculate s = k⁻¹(z + r·d) mod n.\nk⁻¹ = {kinv}, z = {z}, r = {r}, d = {d}, n = {n}.',
              s, 'Multiply and add first, then reduce modulo n at the end.',
              f's = k⁻¹(z + r·d) mod n = {kinv} × ({z} + {r}×{d}) = {kinv} × {z + r * d} = {kinv * (z + r * d)}, '
              f'and {kinv * (z + r * d)} mod {n} = {s}. The signature is (r, s) = ({r}, {s}). '
              'Because s contains the private key d, only Finn could have made it.',
              [(kinv * (z + r * d), f'You forgot to reduce modulo {n} at the end.'),
               (k * (z + r * d) % n, 'You multiplied by k instead of k⁻¹.'),
               (kinv * z % n, 'You left out r·d, the part that carries the private key.'),
               (kinv * (r * d) % n, 'You left out z, the hash of the map.')]),
            q(2, 'Treasure Island — Bob checks the seal',
              f'The gatekeeper (Bob) receives the map and the signature (r, s) = ({r}, {s}).\n'
              f'He starts with w = s⁻¹ mod {n}. Calculate w.',
              w, 'Find a number that, multiplied by s, leaves remainder 1 modulo 19.',
              f'Bob does not know k or d. He starts with w = s⁻¹ = {w} (check: {s} × {w} mod {n} = {s * w % n}). '
              f'Then u1 = z·w = {u1} and u2 = r·w = {u2} (mod {n}), and P = u1·G + u2·Q = {pt(P)}. '
              f'Its x-coordinate mod {n} is {P[0] % n}, which equals r, so the seal is genuine.',
              [(s, 'That is s itself, not s⁻¹.'), ((n - w) % n, 'That is −s⁻¹, with the sign flipped.')]),
            q(2, 'Spot the forged map',
              f'Someone swaps the map for a forged copy but keeps the same signature ({r}, {s}).\n'
              f'Genuine: {original}\nForged:  {forged}\nBob checks the signature against the forged map. What does he find?',
              'INVALID', 'Changing one letter changes the hash z. What does that do to Bob\'s point P?',
              f'One letter changed, so the hash is now z = {z2} instead of {z}. Bob\'s check gives {fx}, which '
              f'is not r = {r}, so the map is rejected. Bob caught the forgery without knowing any secret.',
              [('VALID', 'The forged map has a different hash, so the same signature no longer fits it.')],
              choices=['VALID', 'INVALID'], shuffle=False),
            q(2, 'Why the nonce must stay fresh',
              'Finn gets lazy and signs two different maps with the same secret nonce k. '
              'A pirate sees both signatures. What can the pirate work out?',
              "Finn's private key d",
              'Both signatures share the same r. Look at s = k⁻¹(z + r·d): which unknown could you solve for?',
              'With the same k, both signatures share r. Subtracting the two s values gives s₁ − s₂ = k⁻¹(z₁ − z₂), '
              'so the pirate can solve for k, and then for d = (s·k − z)·r⁻¹ mod n. '
              'Lesson: every signature needs a fresh, random k.',
              [('Nothing. Signatures are always safe.', 'Not so: reusing k leaks the private key.'),
               ('Only the hash of each map', 'Hashes are not secret. The real damage is much worse.'),
               ('How many points are on the curve', 'That is public information anyway.')],
              choices=["Finn's private key d", 'Nothing. Signatures are always safe.', 'Only the hash of each map',
                       'How many points are on the curve']),
        ]

    # ── rendering ──
    def render(self):
        self._clear(self.content); self.hinted = False; self.solved = False; self.choice = ''; self.options = []
        sc = self.scene; n = len(self.questions)
        sc.hp = self.hp; sc.gold = self.gold; sc.qnum = self.i; sc.qtotal = n; sc.max_gold = 100 * n
        d, Q, r, s = self.inventory
        sc.inventory = 'Private key held by Captain Finn' + (f'  |  Public key Q = {Q}' if self.i > 0 else '')
        if self.hp == 0 or self.i == n:
            if self.hp: sc.set_stage(3); sc.mode = 'win'
            else: sc.mode = 'lose'
            if self.hp:
                self.label('Captain Finn says:', 'qtitle')
                self.label(random.choice(self.THANKS), 'speech')
                self.label(f'Score: {self.gold}/{100 * n} gold', 'qtitle')
                self.explain_box('What you learned',
                                 "Q = d·G is public, but d stays secret. A signature (r, s) needs the secret d and a fresh k. "
                                 "Anyone can verify it with Q, and one changed letter breaks it.")
                sc.squawk = 90
            else:
                failed = self.questions[self.i]
                self.label('Shipwrecked! No lives remaining.', 'qtitle')
                self.label(f'The answer to the last quest was: {failed["answer"]}', 'qbody')
                self.explain_box('How it works', failed['explain'])
                self.label(f'Score: {self.gold}/{100 * n} gold')
            self.content.addStretch(1); self.button('Sail again', self.reset); return
        qd = self.questions[self.i]; answer = qd['answer']
        sc.set_stage(qd['stage']); sc.mode = 'play'
        self.label(f'QUEST {self.i + 1} OF {n}   —   {qd["title"]}', 'qtitle')
        self.label(qd['body']).setMinimumHeight(96)
        self.click_mode = bool(qd['choices']) or self.mode in ('guided', 'demo')
        if self.click_mode:
            demo = self.mode == 'demo'
            rnd = random.Random(1000 + self.i) if demo else None
            pick_i = (lambda m: rnd.randrange(m)) if rnd else randbelow
            if qd['choices']:
                options = list(qd['choices'])
            else:
                options = [answer]; wrongs = [v for v, _ in qd['wrong']]
                while len(wrongs) > 3: wrongs.pop(pick_i(len(wrongs)))   # at most three plausible mistakes
                options += wrongs
                if answer.startswith('('):
                    pool = [str(scalar_mult(self.curve, j, self.curve.G)) for j in range(1, 19)]
                else:
                    pool = [str(j) for j in range(19)]
                pool = [v for v in pool if v not in options]
                while len(options) < 4: options.append(pool.pop(pick_i(len(pool))))
            if qd['shuffle']:
                shuffled = []
                while options: shuffled.append(options.pop(pick_i(len(options))))
                options = shuffled
            grid = QGridLayout(); grid.setSpacing(10)
            for idx, opt in enumerate(options):
                b = QPushButton(f'{"ABCD"[idx]}    {opt}'); b.setObjectName('crate'); b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda checked=False, v=opt, bt=b: self.pick(v, bt))
                grid.addWidget(b, idx // 2, idx % 2); self.options.append((b, opt))
            self.content.addLayout(grid)
        else:
            self.entry = QLineEdit(); self.entry.setObjectName('answerEntry'); self.entry.setPlaceholderText('Enter coordinates x, y or a number')
            self.content.addWidget(self.entry); self.entry.textChanged.connect(self.select); self.entry.returnPressed.connect(self._enter)
        row = QHBoxLayout(); row.setSpacing(10); self.content.addLayout(row)
        self.hint_button = self.button('Ask the parrot for a hint', lambda: self.show_hint(qd['hint']), 'smallBtn', row)
        if qd['table']: self.button('Curve reference table', self.show_table, 'smallBtn', row)
        row.addStretch(1)
        self.submit = self.button('Submit answer', self.check, 'goBtn', row)
        if self.click_mode: self.submit.setVisible(False)
        else: self.submit.setEnabled(False)
        self.feedback = self.label('', 'feedback'); self.feedback.setMinimumHeight(46); self.feedback.setProperty('kind', 'none')
        self.explain = self.explain_box('How it works', qd['explain']); self.explain.hide()
        self.content.addStretch(1)

    def explain_box(self, title, text):
        w = QLabel(f'<b>{html.escape(title)}</b><br>' + self._rich(text)); w.setWordWrap(True)
        w.setTextFormat(Qt.TextFormat.RichText); w.setObjectName('explain'); self.content.addWidget(w); return w

    def _enter(self):
        if self.submit.isEnabled(): self.check()

    def show_table(self):
        dlg = QDialog(self); dlg.setObjectName('tableDialog'); dlg.setWindowTitle('Curve reference table'); g = QGridLayout(dlg); g.setSpacing(6)
        for j in range(1, 20):
            pt = scalar_mult(self.curve, j, self.curve.G)
            c = QLabel(f'{j}G = {pt if pt is not None else "O"}'); c.setObjectName('tableCell'); g.addWidget(c, (j - 1) // 4, (j - 1) % 4)
        dlg.exec()

    def select(self, value):
        if self.solved: return
        self.choice = value; self.submit.setEnabled(bool(value.strip()))

    def pick(self, value, btn):
        if self.solved: return
        self.choice = value; self.check(btn)

    def show_hint(self, hint):
        self.hinted = True; self._feedback('Parrot: ' + hint, 'hint'); self.scene.squawk = 45

    def check(self, btn=None):
        if self.solved: self.i += 1; self.render(); return
        norm = lambda s: ''.join(s.lower().split()).replace('(', '').replace(')', '')
        qd = self.questions[self.i]; answer = qd['answer']
        if norm(self.choice) == norm(answer):
            self.solved = True; earned = 75 if self.hinted else 100; self.gold += earned
            shown = answer if len(answer) < 30 else 'Correct answer!'
            self._feedback(f'Correct! {shown}     +{earned} gold', 'good'); self.hint_button.setEnabled(False); self.scene.cheer(earned)
            for b, v in self.options:
                b.setEnabled(False)
                if v == answer: b.setProperty('state', 'right'); _restyle(b)
            if not self.options: self.entry.setEnabled(False)
            self.explain.show()
            self.submit.setText('Claim the treasure!' if self.i == len(self.questions) - 1 else 'Continue voyage')
            self.submit.setVisible(True); self.submit.setEnabled(True)
        else:
            self.hp -= 1; self.scene.hit()
            notes = {norm(v): note for v, note in qd['wrong']}
            note = notes.get(norm(self.choice), '')
            self._feedback('Not quite, matey! One life lost.' + (f'\n{note}' if note else ''), 'bad')
            if btn is not None: btn.setProperty('state', 'wrong'); btn.setEnabled(False); _restyle(btn)
            if not self.hp: self.scene.hp = 0; self.render(); return
        self.scene.hp = self.hp; self.scene.gold = self.gold

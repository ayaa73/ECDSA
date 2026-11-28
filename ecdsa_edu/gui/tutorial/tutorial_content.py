# ====================================================================== cards
class QuestCard(QPushButton):
    """A big clickable card that opens one page of the app."""

    def __init__(self, page: str, title: str, blurb: str, badge: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self.setObjectName("questCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(212, 92)
        self.setAccessibleName(f"{title}: {blurb}")
        self.setToolTip(f"Open {page}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        top = QHBoxLayout()
        name = QLabel(title)
        name.setObjectName("cardTitle")
        top.addWidget(name)
        top.addStretch(1)
        if badge:
            tag = QLabel(badge)
            tag.setObjectName("cardBadge")
            tag.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            top.addWidget(tag)
        lay.addLayout(top)
        text = QLabel(blurb)
        text.setObjectName("cardBlurb")
        text.setWordWrap(True)
        lay.addWidget(text)
        lay.addStretch(1)
        for child in (name, text):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


# ====================================================================== page
def _restyle(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


PAGE_STYLE = """
QLabel#heroEyebrow { color: #ffd35c; font-weight: 800; letter-spacing: 3px; font-size: 9pt; background: transparent; }
QLabel#heroTitle { color: #ffffff; font-size: 30pt; font-weight: 800; background: transparent; }
QLabel#heroSub { color: #f6e3e9; font-size: 13pt; background: transparent; }
QPushButton#heroPrimary { background: #ffd35c; color: #33091a; border: 0; border-radius: 14px; padding: 11px 22px;
    font-weight: 800; font-size: 12pt; }
QPushButton#heroPrimary:hover { background: #ffe38f; }
QPushButton#heroGhost { background: rgba(255,255,255,26); color: #ffffff; border: 1px solid rgba(255,255,255,120);
    border-radius: 14px; padding: 10px 18px; font-weight: 700; font-size: 11pt; }
QPushButton#heroGhost:hover { background: rgba(255,255,255,80); }
QLabel#sectionTitle { font-size: 15pt; font-weight: 800; }
QLabel#sectionHint { font-size: 10.5pt; }
QFrame#panel { background: @BOX@; border: 1px solid @EDGE@; border-radius: 18px; }
QFrame#factStrip { background: @BOX@; border: 1px solid @EDGE@; border-radius: 14px; }
QLabel#factIcon { font-size: 8.5pt; font-weight: 800; letter-spacing: 2px; background: transparent; }
QLabel#factText { font-size: 11pt; background: transparent; }
QPushButton#stepChip { background: @CHIP@; border: 1px solid @EDGE@; border-radius: 14px;
    padding: 6px 14px; font-weight: 700; }
QPushButton#stepChip:hover { border-color: palette(highlight); }
QPushButton#stepChip:checked { background: palette(highlight); color: palette(highlighted-text); border-color: palette(highlight); }
QLabel#frameTitle { font-size: 14pt; font-weight: 800; }
QLabel#frameText { font-size: 12pt; }
QPushButton#demoStep { background: @CHIP@; border: 1px solid @EDGE@; border-radius: 12px; padding: 10px 18px; font-weight: 700; font-size: 11pt; }
QPushButton#demoStep:hover:enabled { border-color: palette(highlight); }
QPushButton#demoStep[next="true"] { background: palette(highlight); color: palette(highlighted-text); border-color: palette(highlight); }
QPushButton#demoStep[next="true"]:disabled { background: palette(highlight); color: palette(highlighted-text); }
QLabel#badge { border: 1px solid @EDGE@; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QLabel#badge[done="true"] { background: palette(highlight); color: palette(highlighted-text); border: 1px solid palette(highlight); }
QLabel#cheer { background: palette(window); border: 1px solid palette(highlight); border-radius: 12px; padding: 10px 14px;
    font-size: 11pt; font-weight: 600; }
QLabel#trackPill { color: palette(text); border: 1px solid @EDGE@; border-radius: 10px; padding: 2px 12px; font-weight: 800; letter-spacing: 2px; font-size: 8.5pt; }
QPushButton#questCard { background: @BOX@; border: 1px solid @EDGE@; border-radius: 14px; text-align: left; }
QPushButton#questCard:hover, QPushButton#questCard:focus { border: 2px solid palette(highlight); }
QPushButton#questCard QLabel { background: transparent; }
QLabel#cardTitle { font-size: 12pt; font-weight: 800; }
QLabel#cardBlurb { font-size: 9.5pt; }
QPushButton#questCard QLabel#cardBadge { background: palette(highlight); color: palette(highlighted-text); border-radius: 8px; padding: 1px 8px; font-weight: 800; font-size: 7.5pt; letter-spacing: 1px; }
QLineEdit#messageEdit { background: @CHIP@; border: 1px solid @EDGE@; border-radius: 10px; padding: 4px 12px; font-size: 12pt; }
QLineEdit#messageEdit:focus { border-color: palette(highlight); }
QToolButton#helpToggle { border: 0; font-weight: 700; font-size: 11pt; padding: 6px 2px; }
"""


def _section(title: str, hint: str = "") -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(2, 0, 2, 0)
    lay.setSpacing(0)
    t = QLabel(title)
    t.setObjectName("sectionTitle")
    lay.addWidget(t)
    if hint:
        h = QLabel(hint)
        h.setObjectName("sectionHint")
        h.setWordWrap(True)
        lay.addWidget(h)
    return box


class TutorialTab(QWidget):
    """Start here: an animated welcome, the 60-second story, a live demo and a map of every page."""

    HELP = ("Start here if ECDSA is new to you. Watch the 60-second story, type your own message and sign it in "
            "the live demo, then pick an adventure card to jump to any other page. The sidebar is always on "
            "the left too.")

    def __init__(self, state: Any = None) -> None:
        super().__init__()
        self.state = state
        self._demo_keys: tuple[Any, Any] | None = None
        self._demo_sig: Any = None
        self._demo_msg = DEMO_MESSAGE
        self._done = {"keys": False, "signed": False, "verified": False, "caught": False}
        self.curve = get_curve(DEMO_CURVE)
        self._style_key: tuple[str, ...] | None = None
        self._apply_style()

        # ---- hero
        self.hero = HeroBanner()
        hero_row = QHBoxLayout(self.hero)
        hero_row.setContentsMargins(34, 26, 34, 26)
        left = QVBoxLayout()
        left.setSpacing(8)
        eyebrow = QLabel("DIGITAL SIGNATURES · HANDS-ON")
        eyebrow.setObjectName("heroEyebrow")
        self.welcome_heading = QLabel("Welcome to ECDSA Lab")
        self.welcome_heading.setObjectName("heroTitle")
        self.welcome_heading.setWordWrap(True)
        sub = QLabel(WELCOME)
        sub.setObjectName("heroSub")
        sub.setWordWrap(True)
        cta = QHBoxLayout()
        cta.setSpacing(10)
        self.story_cta = QPushButton("Watch the 60-second story")
        self.story_cta.setObjectName("heroPrimary")
        self.try_cta = QPushButton("Try it live")
        self.try_cta.setObjectName("heroGhost")
        for b in (self.story_cta, self.try_cta):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            cta.addWidget(b)
        cta.addStretch(1)
        left.addStretch(1)
        left.addWidget(eyebrow)
        left.addWidget(self.welcome_heading)
        left.addWidget(sub)
        left.addSpacing(8)
        left.addLayout(cta)
        left.addStretch(1)
        hero_row.addLayout(left, 11)
        hero_row.addStretch(9)

        # ---- did you know
        self._fact_i = random.randrange(len(FACTS))
        self.fact_strip = QFrame()
        self.fact_strip.setObjectName("factStrip")
        fact_row = QHBoxLayout(self.fact_strip)
        fact_row.setContentsMargins(16, 10, 14, 10)
        icon = QLabel("DID YOU KNOW")
        icon.setObjectName("factIcon")
        self.fact_label = QLabel(FACTS[self._fact_i])
        self.fact_label.setObjectName("factText")
        self.fact_label.setWordWrap(True)
        self.fact_button = QPushButton("Another fact")
        self.fact_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fact_button.clicked.connect(lambda *_: self.next_fact())
        fact_row.addWidget(icon)
        fact_row.addWidget(self.fact_label, 1)
        fact_row.addWidget(self.fact_button)

        # ---- part 1: story
        self.canvas = StoryCanvas()
        self.chips: list[QPushButton] = []
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        for i, label in enumerate(STEP_CHIPS):
            chip = QPushButton(f"{i + 1}  {label}")
            chip.setObjectName("stepChip")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda checked=False, k=i: self.show_frame(k))
            chip_row.addWidget(chip)
            self.chips.append(chip)
        chip_row.addStretch(1)
        self.frame_title = QLabel()
        self.frame_title.setObjectName("frameTitle")
        self.frame_text = QLabel()
        self.frame_text.setObjectName("frameText")
        self.frame_text.setWordWrap(True)
        self.frame_text.setMinimumHeight(44)
        self.prev_button = QPushButton("◀ Previous")
        self.next_button = QPushButton("Next ▶")
        self.prev_button.clicked.connect(lambda *_: self.show_frame(self.canvas.frame - 1))
        self.next_button.clicked.connect(lambda *_: self.show_frame(self.canvas.frame + 1))
        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        self.story = QFrame()
        self.story.setObjectName("panel")
        story_layout = QVBoxLayout(self.story)
        story_layout.setContentsMargins(18, 16, 18, 16)
        story_layout.setSpacing(10)
        story_layout.addLayout(chip_row)
        story_layout.addWidget(self.canvas)
        story_layout.addWidget(self.frame_title)
        story_layout.addWidget(self.frame_text)
        story_layout.addLayout(nav)

        # ---- part 2: try it live
        self.message_edit = QLineEdit(DEMO_MESSAGE)
        self.message_edit.setPlaceholderText("Type any message…")
        self.message_edit.setMaxLength(60)
        self.message_edit.setObjectName("messageEdit")
        self.message_edit.setMinimumHeight(38)
        self.message_edit.textEdited.connect(self._message_changed)
        msg_row = QHBoxLayout()
        msg_label = QLabel("<b>Your message:</b>")
        msg_row.addWidget(msg_label)
        msg_row.addWidget(self.message_edit, 1)
        self.keys_button = QPushButton("1. Make keys")
        self.sign_button = QPushButton("2. Sign it")
        self.verify_button = QPushButton("3. Verify")
        self.tamper_button = QPushButton("Change one letter")
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            b.setObjectName("demoStep")
            b.setMinimumHeight(40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keys_button.clicked.connect(self.make_keys)
        self.sign_button.clicked.connect(self.sign_message)
        self.verify_button.clicked.connect(self.verify_message)
        self.tamper_button.clicked.connect(self.tamper_message)
        steps = QHBoxLayout()
        steps.setSpacing(10)
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            steps.addWidget(b)
        self.badges: dict[str, QLabel] = {}
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self._badge_text = {"keys": "Keys made", "signed": "Signed", "verified": "Verified", "caught": "Forgery caught"}
        for key, text in self._badge_text.items():
            badge = QLabel(text)
            badge.setObjectName("badge")
            badge.setProperty("done", False)
            badge_row.addWidget(badge)
            self.badges[key] = badge
        badge_row.addStretch(1)
        self.keys_card, self.sign_card = QLabel(), QLabel()
        for card in (self.keys_card, self.sign_card):
            card.setWordWrap(True)
            card.setTextFormat(Qt.TextFormat.RichText)
            card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.banner = ResultBanner()
        self.cheer = QLabel("Quest complete! You just did what ECDSA does billions of times a day. "
                            "Now pick an adventure below.")
        self.cheer.setObjectName("cheer")
        self.cheer.setWordWrap(True)
        self.cheer.hide()
        for hidden in (self.keys_card, self.sign_card, self.banner):
            hidden.hide()
        self.try_box = QFrame()
        self.try_box.setObjectName("panel")
        try_layout = QVBoxLayout(self.try_box)
        try_layout.setContentsMargins(18, 16, 18, 16)
        try_layout.setSpacing(10)
        try_layout.addLayout(msg_row)
        try_layout.addLayout(steps)
        try_layout.addLayout(badge_row)
        try_layout.addWidget(self.keys_card)
        try_layout.addWidget(self.sign_card)
        try_layout.addWidget(self.banner)
        try_layout.addWidget(self.cheer)

        # ---- part 3: pick your adventure
        self.cards: list[QuestCard] = []
        self.adventures = QWidget()
        adv = QVBoxLayout(self.adventures)
        adv.setContentsMargins(0, 0, 0, 0)
        adv.setSpacing(12)
        adv.addWidget(_section("Pick your adventure", "Every card opens a page. New here? Start with the first one."))
        for track in TRACKS:
            pill_row = QHBoxLayout()
            pill = QLabel(track.name)
            pill.setObjectName("trackPill")
            hint = QLabel(track.tagline)
            hint.setObjectName("sectionHint")
            pill_row.addWidget(pill)
            pill_row.addWidget(hint)
            pill_row.addStretch(1)
            adv.addLayout(pill_row)
            row_cards = []
            for c in track.cards:
                card = QuestCard(c.page, c.title, c.blurb, c.badge)
                card.clicked.connect(lambda checked=False, page=c.page: go_to(self, self.state, page))
                self.cards.append(card)
                row_cards.append(card)
            holder = QWidget()
            flow = FlowLayout(holder, 14)
            for card in row_cards:
                flow.addWidget(card)
            policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            policy.setHeightForWidth(True)
            holder.setSizePolicy(policy)
            adv.addWidget(holder)

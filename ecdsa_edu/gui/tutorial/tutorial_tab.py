        # ---- collapsible help
        self.help_toggle = QToolButton()
        self.help_toggle.setObjectName("helpToggle")
        self.help_toggle.setText("How do I use this app?")
        self.help_toggle.setCheckable(True)
        self.help_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.help_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.help_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_box = QFrame()
        self.help_box.setObjectName("panel")
        help_layout = QVBoxLayout(self.help_box)
        help_layout.setContentsMargins(18, 14, 18, 14)
        self.how_label = explanation(html.escape(HOW_TO_USE))
        steps_html = "".join(f"<li><b>{html.escape(stop.page)}</b>: {html.escape(stop.what)}</li>"
                             for stop in SUGGESTED_ORDER)
        self.order_label = explanation(f"Suggested order:<ol style='margin-top:4px'>{steps_html}</ol>")
        help_layout.addWidget(self.how_label)
        help_layout.addWidget(self.order_label)
        self.help_box.hide()
        self.help_toggle.toggled.connect(self._toggle_help)

        # ---- startup checkbox
        self.startup_box = QCheckBox("Show this page when the app starts")
        self.startup_box.setChecked(self.show_at_startup())
        self.startup_box.toggled.connect(lambda on: settings().setValue(SETTINGS_KEY, bool(on)))

        # ---- assemble
        self.story_section = QWidget()
        sl = QVBoxLayout(self.story_section)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)
        sl.addWidget(_section("ECDSA in 60 seconds", ANALOGY))
        sl.addWidget(self.story)
        self.try_section = QWidget()
        tl = QVBoxLayout(self.try_section)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(10)
        tl.addWidget(_section("Try it live", "Type a message, then click the glowing button. It uses a tiny practice "
                                              "curve and its own key, so nothing else in the app changes."))
        tl.addWidget(self.try_box)

        content = QWidget()
        page = QVBoxLayout(content)
        page.setContentsMargins(4, 4, 12, 16)
        page.setSpacing(22)
        page.addWidget(self.hero)
        page.addWidget(self.fact_strip)
        page.addWidget(self.story_section)
        page.addWidget(self.try_section)
        page.addWidget(self.adventures)
        page.addWidget(self.help_toggle)
        page.addWidget(self.help_box)
        page.addWidget(self.startup_box)
        page.addStretch(1)
        self.content = content
        content.setObjectName("startContent")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)

        self.story_cta.clicked.connect(lambda *_: self.scroll_to(self.story_section))
        self.try_cta.clicked.connect(lambda *_: self.scroll_to(self.try_section))

        self._apply_style()
        self.show_frame(0)
        self._update_demo_buttons()

    # ------------------------------------------------------------ look
    def _apply_style(self) -> None:
        """Boxes stand out from the (unchanged) page in both themes: bright white with an edge and soft shadow in
        light mode, a clearly lighter panel colour in dark mode."""
        pal = self.palette()
        window, panel = pal.window().color(), pal.button().color()
        if window.lightness() > 128:  # light theme: bright white boxes on a slightly deeper tinted page
            box, chip, edge, shadow = QColor("#ffffff"), window, window.darker(128), True
        else:  # dark theme: a clearly lighter panel on a deeper page
            box, chip, edge, shadow = panel.lighter(150), window, panel.lighter(210), False
        key = (box.name(), chip.name(), edge.name())
        if key != self._style_key:
            self._style_key = key
            self.setStyleSheet(PAGE_STYLE.replace("@BOX@", box.name()).replace("@CHIP@", chip.name())
                               .replace("@EDGE@", edge.name()))
        lifted = list(getattr(self, "cards", [])) + [getattr(self, n) for n in ("fact_strip", "story", "try_box")
                                                     if hasattr(self, n)]
        for w in lifted:
            if shadow and w.graphicsEffect() is None:
                fx = QGraphicsDropShadowEffect(w)
                fx.setBlurRadius(24)
                fx.setOffset(0, 4)
                fx.setColor(QColor(60, 20, 30, 80))
                w.setGraphicsEffect(fx)
            elif not shadow and w.graphicsEffect() is not None:
                w.setGraphicsEffect(None)

    def changeEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "cards"):
            self._apply_style()

    # ------------------------------------------------------------ tab contract
    def set_curve(self, curve: Any) -> None:
        """The tutorial always uses toy-17 so the numbers stay small."""

    @staticmethod
    def show_at_startup() -> bool:
        value = settings().value(SETTINGS_KEY, True)
        return value not in (False, "false", "0", 0)

    # ------------------------------------------------------------ small interactions
    def scroll_to(self, widget: QWidget) -> None:
        """Glide the page down to a section."""
        bar = self.scroll.verticalScrollBar()
        target = max(0, widget.mapTo(self.content, QPoint(0, 0)).y() - 8)
        self._glide = QPropertyAnimation(bar, b"value", self)
        self._glide.setDuration(450)
        self._glide.setStartValue(bar.value())
        self._glide.setEndValue(min(target, bar.maximum()) if bar.maximum() else target)
        self._glide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._glide.start()

    def next_fact(self) -> None:
        self._fact_i = (self._fact_i + random.randrange(1, len(FACTS))) % len(FACTS)
        self.fact_label.setText(FACTS[self._fact_i])

    def _toggle_help(self, on: bool) -> None:
        self.help_box.setVisible(on)
        self.help_toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    # ------------------------------------------------------------ story
    def show_frame(self, i: int) -> None:
        self.canvas.set_frame(i)
        frame = FRAMES[self.canvas.frame]
        self.frame_title.setText(frame.title)
        self.frame_text.setText(frame.text)
        self.prev_button.setEnabled(self.canvas.frame > 0)
        self.next_button.setEnabled(self.canvas.frame < len(FRAMES) - 1)
        for k, chip in enumerate(self.chips):
            chip.setChecked(k == self.canvas.frame)

    # ------------------------------------------------------------ live demo
    def _message(self) -> str:
        return self.message_edit.text().strip() or DEMO_MESSAGE

    def _message_changed(self, _text: str = "") -> None:
        """Editing the message makes the old signature stale, like in real life."""
        if self._demo_sig is not None:
            self._demo_sig = None
            self._set_card(self.sign_card, "")
            self._show_banner("info", "", "")
            self._done.update(signed=False, verified=False, caught=False)
            self._refresh_badges()
        self._update_demo_buttons()

    def _show_banner(self, kind: str, headline: str, detail: str) -> None:
        self.banner.show_message(kind, headline, detail)
        self.banner.setVisible(bool(headline))

    def _set_card(self, card: QLabel, text: str) -> None:
        card.setText(text)
        card.setVisible(bool(text))

    def _refresh_badges(self) -> None:
        for key, badge in self.badges.items():
            badge.setProperty("done", bool(self._done[key]))
            badge.setText(("✓  " if self._done[key] else "") + self._badge_text[key])
            _restyle(badge)
        self.cheer.setVisible(all(self._done.values()))

    def _update_demo_buttons(self, busy: bool = False) -> None:
        self.keys_button.setEnabled(not busy)
        self.sign_button.setEnabled(not busy and self._demo_keys is not None)
        self.verify_button.setEnabled(not busy and self._demo_sig is not None)
        self.tamper_button.setEnabled(not busy and self._demo_sig is not None)
        # the next thing to click glows, so a beginner always knows where to go
        if self._demo_keys is None:
            nxt = self.keys_button
        elif self._demo_sig is None:
            nxt = self.sign_button
        elif not self._done["verified"]:
            nxt = self.verify_button
        else:
            nxt = self.tamper_button
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            b.setProperty("next", b is nxt and not self._done["caught"])
            _restyle(b)

    def make_keys(self, *_: Any) -> None:
        self._demo_sig = None
        self._demo_msg = self._message()
        self._set_card(self.sign_card, "")
        self._show_banner("info", "", "")
        self._done.update(keys=False, signed=False, verified=False, caught=False)
        self._refresh_badges()
        self._update_demo_buttons(busy=True)
        run_in_background(generate_keypair, self.curve, on_done=self._keys_done, on_error=self._failed)

    def _keys_done(self, keys: tuple[Any, Any]) -> None:
        self._demo_keys = keys
        priv, pub = keys
        self._set_card(self.keys_card, (
            f"<b>Private key</b> d = {fmt_number(priv.d, self.curve)} <i>(secret: in real life never shown)</i><br>"
            f"<b>Public key</b> Q = {fmt_point(pub.Q, self.curve)} <i>(shared with everyone)</i>"))
        self._done["keys"] = True
        self._refresh_badges()
        self._update_demo_buttons()

    def sign_message(self, *_: Any) -> None:
        if self._demo_keys is None:
            return
        self._demo_msg = self._message()
        self._update_demo_buttons(busy=True)
        run_in_background(sign, self._demo_keys[0], self._demo_msg.encode(), on_done=self._sign_done,
                          on_error=self._failed)

    def _sign_done(self, sig: Any) -> None:
        self._demo_sig = sig
        self._set_card(self.sign_card, f"<b>Signature</b> on \"{html.escape(self._demo_msg)}\": "
                               f"r = {fmt_number(sig.r, self.curve)}, s = {fmt_number(sig.s, self.curve)}")
        self._show_banner("info", "Signed", "Now press Verify to check it as Bob would.")
        self._done["signed"] = True
        self._refresh_badges()
        self._update_demo_buttons()

    def verify_message(self, message: str | None = None, note: str = "") -> None:
        if self._demo_keys is None or self._demo_sig is None:
            return
        text = message if isinstance(message, str) else self._demo_msg
        self._update_demo_buttons(busy=True)
        run_in_background(verify, self._demo_keys[1], text.encode(), self._demo_sig,
                          on_done=lambda ok: self._verify_done(ok, text, note), on_error=self._failed)

    def _verify_done(self, ok: bool, text: str, note: str) -> None:
        shown = html.escape(text)
        if ok:
            self._show_banner("good", "VALID", f"\"{text}\" was signed with Alice's private key.")
            self._done["verified"] = True
        else:
            self._show_banner("bad", "INVALID", f"{note} The message is now \"{text}\", which is not what "
                                                       "Alice signed, so the same signature no longer fits.")
            self._done["caught"] = True
        self.banner.setToolTip(shown)
        self._refresh_badges()
        self._update_demo_buttons()

    def _tamper_that_fails(self, text: str) -> tuple[str, str]:
        """Like tamper_text, but guaranteed to break the signature. The practice curve is so small (about 19
        values) that a wrong signature verifies by luck roughly 1 time in 19, which would ruin the demo. So
        try changes outward from the middle of the message until one really fails to verify."""
        changed, what = tamper_text(text)
        if not text or self._demo_keys is None or self._demo_sig is None:
            return changed, what
        pub, sig = self._demo_keys[1], self._demo_sig
        try:
            if not verify(pub, changed.encode(), sig):
                return changed, what
            for i in sorted(range(len(text)), key=lambda k: abs(k - len(text) // 2)):
                c = text[i]
                for new in ((c.swapcase(),) if c.isalpha() and c.swapcase() != c else ()) + ("!", "?", "#", "x", "7"):
                    if new == c:
                        continue
                    cand = text[:i] + new + text[i + 1:]
                    if not verify(pub, cand.encode(), sig):
                        return cand, f"changed character {i + 1} from {c!r} to {new!r}"
        except Exception:  # never let a demo nicety break the page
            pass
        return changed, what

    def tamper_message(self, *_: Any) -> None:
        changed, what = self._tamper_that_fails(self._demo_msg)
        self.verify_message(changed, note=f"We {what}.")

    def _failed(self, exc: Exception) -> bool:
        self._update_demo_buttons()
        self._show_banner("bad", "Something went wrong", str(exc))
        return True

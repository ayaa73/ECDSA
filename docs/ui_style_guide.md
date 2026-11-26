# ECDSA Lab UI style guide

The Fusion theme in `ecdsa_edu/gui/app.py` is the source of colour tokens. The light canvas is cream `#F6F0E4`, the surface `#FBF7EF`, and the rail `#111111`; text is `#141414`. Block colours are yellow `#F4D35E`, pink `#F5A8D0`, olive `#A7B26A`, periwinkle `#9FB3F2`, peach `#F7C59F`, and lilac `#CDB8F2`. The dark theme supplies muted equivalents and light text for ordinary surfaces. Use dark text on colour blocks. Feedback colours are `ok`, `error`, and `warning`; existing token names remain available through `theme_colors()`.

Suggested page colours: Start here and Keys yellow; Sign pink and lilac; Verify olive and periwinkle; Curve Explorer periwinkle; Attack Demo pink and yellow; Learn ECDSA lilac. History colours follow the event category.

Set Qt dynamic properties instead of embedding colours in widgets:

- `card`: `yellow`, `pink`, `olive`, `periwinkle`, `peach`, or `lilac`.
- `chip`: `True` for a filter button; make it checkable for the active state.
- `badge`: `True` for a small pill label.
- `heading`: `hero` or `section` for a label.
- `muted`: `True` for supporting text.
- `mono`: `True` for numbers and formulas; `primary`: `True` for the main action.
- `result`: `good`, `bad`, or `info` for result banners.

When changing a property after a widget is shown, unpolish and polish it to refresh QSS. DM Sans is bundled; numeric fields retain their monospace font.

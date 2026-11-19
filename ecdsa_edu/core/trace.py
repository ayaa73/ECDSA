"""
This code records mathematical calculations so we can see how ECDSA works instead of only seeing the final answer.
Human-readable arithmetic traces shared by core and GUI.
"""
from dataclasses import dataclass

"""Create a structure containing the name of the calculation, the formula used, and the actual numbers involved."""
@dataclass
class TraceStep:
    title: str
    formula: str
    values: dict[str, str]


Trace = list[TraceStep]


def add_step(trace, title, formula, **values) -> None:
    """Add a step converting integers to decimal (and hex if > 2^32)."""
    if trace is None:
        return

    def stringify(value: object) -> str:
        if isinstance(value, int) and not isinstance(value, bool):
            return f"{value} (0x{value:x})" if value > 2**32 else str(value)
        return str(value)

    trace.append(TraceStep(title, formula, {k: stringify(v) for k, v in values.items()}))

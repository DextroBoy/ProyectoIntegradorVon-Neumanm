"""Modelo formal del procesador como autómata finito (Q, Σ, δ, q0, F).

  Q  = {FETCH, DECODE, EXECUTE, HALT}     estados del ciclo de instrucción
  Σ  = I ∪ {ε}                            instrucciones del ISA (ε: sin entrada)
  q0 = FETCH       (con PC = 0, AC = 0)
  F  = {HALT}
  δ  = ver DELTA

Los valores de PC, AC, IR y memoria forman el "contexto" de la máquina: δ
actúa sobre el estado de control, y el contexto lo modifica cada instrucción.
"""
from core.isa import MNEMONICS

Q = ("FETCH", "DECODE", "EXECUTE", "HALT")
SIGMA = tuple(MNEMONICS[k] for k in sorted(MNEMONICS))
Q0 = "FETCH"
F = ("HALT",)

# (estado, etiqueta de la arista, estado siguiente)
TRANSITIONS = [
    ("FETCH",   "ε  (IR ← M[PC])",        "DECODE"),
    ("DECODE",  "opcode válido",          "EXECUTE"),
    ("DECODE",  "opcode inválido",        "HALT"),
    ("EXECUTE", "i ∈ I \\ {HALT}",        "FETCH"),
    ("EXECUTE", "i = HALT",               "HALT"),
]


def delta(state: str, instruction: str = "") -> str:
    """Función de transición δ: Q × Σ → Q."""
    if state == "FETCH":
        return "DECODE"
    if state == "DECODE":
        return "EXECUTE" if instruction in SIGMA else "HALT"
    if state == "EXECUTE":
        return "HALT" if instruction == "HALT" else "FETCH"
    return "HALT"


def definition_text() -> str:
    return (
        "M = (Q, Σ, δ, q0, F)\n"
        f"Q  = {{{', '.join(Q)}}}\n"
        f"Σ  = {{{', '.join(SIGMA)}}} ∪ {{ε}}\n"
        f"q0 = {Q0}   (PC = 0)\n"
        f"F  = {{{', '.join(F)}}}"
    )


def to_dot() -> str:
    """Exporta el autómata en formato Graphviz DOT."""
    lines = ["digraph Procesador {", "  rankdir=LR;", "  node [shape=circle];",
             '  HALT [shape=doublecircle];', '  start [shape=point];',
             "  start -> FETCH;"]
    for a, label, b in TRANSITIONS:
        lines.append(f'  {a} -> {b} [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


# ------------------------------------------------------- tablas de verdad
def truth_table(op: str):
    """Tabla de verdad de una operación lógica de 1 bit.
    Devuelve (encabezados, filas)."""
    if op == "NOT":
        return ["p", "NOT p"], [[int(p), int(not p)] for p in (False, True)]
    fn = {"AND": lambda p, q: p and q, "OR": lambda p, q: p or q}[op]
    rows = [[int(p), int(q), int(fn(p, q))]
            for p in (False, True) for q in (False, True)]
    return ["p", "q", f"p {op} q"], rows


def jump_table(op: str):
    """Tabla de verdad de un salto condicional (JZ o JN)."""
    prop = "AC = 0" if op == "JZ" else "AC < 0"
    rows = [[prop + " → V", "PC ← dirección destino"],
            [prop + " → F", "PC ← PC + 1 (sin salto)"]]
    return ["Proposición", "Acción"], rows


def format_table(headers, rows) -> str:
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    fmt = lambda r: " │ ".join(str(x).center(w) for x, w in zip(r, widths))
    sep = "─┼─".join("─" * w for w in widths)
    return "\n".join([fmt(headers), sep] + [fmt(r) for r in rows])

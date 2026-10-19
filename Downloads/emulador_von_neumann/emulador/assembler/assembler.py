"""Ensamblador de dos pasadas para el ISA del emulador.

Sintaxis (una instrucción por línea, sin distinguir mayúsculas):

    ETIQUETA:  MNEMÓNICO  operando    ; comentario
    ETIQUETA:  DAT        valor       ; reserva una celda de datos

El programa se carga desde la dirección 0 en el orden en que aparece.
"""
import re
from dataclasses import dataclass, field

from core.isa import (MEM_SIZE, NO_OPERAND, OPCODES, WORD_MAX, WORD_MIN,
                      encode)

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AsmError(Exception):
    """Contiene todos los errores encontrados: lista de (línea, mensaje)."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join(f"Línea {n}: {m}" for n, m in errors))


@dataclass
class Program:
    words: list = field(default_factory=list)
    kinds: dict = field(default_factory=dict)        # dirección -> "code"/"data"
    lines: dict = field(default_factory=dict)        # dirección -> n.º de línea
    labels: dict = field(default_factory=dict)       # etiqueta -> dirección
    mnemonics: dict = field(default_factory=dict)    # dirección -> mnemónico
    operands: dict = field(default_factory=dict)     # dirección -> operando


def _parse_int(token):
    try:
        return int(token, 10)
    except ValueError:
        return None


def assemble(text: str) -> Program:
    errors = []
    items = []              # (línea, dirección, mnemónico, token_operando)
    labels = {}
    addr = 0

    # ---------------------------------------------------------- 1.ª pasada
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.split(";")[0].split("//")[0].strip()
        if not line:
            continue

        if ":" in line:
            label, line = line.split(":", 1)
            label, line = label.strip().upper(), line.strip()
            if not IDENT.match(label):
                errors.append((n, f"Etiqueta inválida: '{label}'"))
            elif label in OPCODES or label == "DAT":
                errors.append((n, f"'{label}' es una palabra reservada"))
            elif label in labels:
                errors.append((n, f"Etiqueta duplicada: '{label}'"))
            else:
                labels[label] = addr
            if not line:
                continue

        parts = line.split()
        mnem, operands = parts[0].upper(), parts[1:]

        if mnem != "DAT" and mnem not in OPCODES:
            errors.append((n, f"Instrucción desconocida: '{parts[0]}'"))
            continue
        if len(operands) > 1:
            errors.append((n, "Demasiados operandos"))
            continue
        if mnem in NO_OPERAND and operands:
            errors.append((n, f"{mnem} no lleva operando"))
            continue
        if mnem not in NO_OPERAND and mnem != "DAT" and not operands:
            errors.append((n, f"{mnem} necesita un operando (dirección o etiqueta)"))
            continue
        if addr >= MEM_SIZE:
            errors.append((n, f"El programa excede la memoria ({MEM_SIZE} celdas)"))
            break

        items.append((n, addr, mnem, operands[0] if operands else None))
        addr += 1

    # ---------------------------------------------------------- 2.ª pasada
    prog = Program(labels=labels)
    for n, a, mnem, tok in items:
        if mnem == "DAT":
            value = 0 if tok is None else _parse_int(tok)
            if value is None or not WORD_MIN <= value <= WORD_MAX:
                errors.append((n, f"Valor inválido para DAT: '{tok}'"))
                value = 0
            prog.words.append(value)
            prog.kinds[a] = "data"
        else:
            operand = 0
            if tok is not None:
                value = _parse_int(tok)
                if value is None:
                    value = labels.get(tok.upper())
                    if value is None:
                        errors.append((n, f"Etiqueta no definida: '{tok}'"))
                        value = 0
                if not 0 <= value < MEM_SIZE:
                    errors.append((n, f"Dirección fuera de rango: {value}"))
                    value = 0
                operand = value
            prog.words.append(encode(mnem, operand))
            prog.kinds[a] = "code"
            prog.mnemonics[a] = mnem
            prog.operands[a] = operand
        prog.lines[a] = n

    if errors:
        raise AsmError(sorted(errors))
    return prog

"""ISA (conjunto de instrucciones) del computador didáctico.

Modelo formal:  I = {HALT, LOAD, STORE, ADD, SUB, JUMP, JZ, JN, INPUT,
                     OUTPUT, AND, OR, NOT}
                M = {0, 1, ..., MEM_SIZE-1}
Cada palabra de memoria es un entero:  palabra = opcode * 100 + operando
(así las instrucciones y los datos viven en la MISMA memoria: Von Neumann).
"""

MEM_SIZE = 100
WORD_MIN, WORD_MAX = -32768, 32767          # palabra de 16 bits con signo

OPCODES = {
    "HALT": 0, "LOAD": 1, "STORE": 2, "ADD": 3, "SUB": 4,
    "JUMP": 5, "JZ": 6, "JN": 7, "INPUT": 8, "OUTPUT": 9,
    "AND": 10, "OR": 11, "NOT": 12,
}
MNEMONICS = {v: k for k, v in OPCODES.items()}

NO_OPERAND = {"HALT", "INPUT", "OUTPUT", "NOT"}   # no usan dirección
JUMPS = {"JUMP", "JZ", "JN"}

DESCRIPTIONS = {
    "HALT":   "Detiene el procesador",
    "LOAD":   "AC ← M[x]",
    "STORE":  "M[x] ← AC",
    "ADD":    "AC ← AC + M[x]",
    "SUB":    "AC ← AC − M[x]",
    "JUMP":   "PC ← x",
    "JZ":     "si AC = 0 entonces PC ← x",
    "JN":     "si AC < 0 entonces PC ← x",
    "INPUT":  "AC ← valor ingresado",
    "OUTPUT": "Muestra AC en la consola",
    "AND":    "AC ← AC AND M[x]  (bit a bit)",
    "OR":     "AC ← AC OR M[x]   (bit a bit)",
    "NOT":    "AC ← NOT AC       (bit a bit)",
}


def wrap(value: int) -> int:
    """Ajusta un entero al rango de 16 bits con signo (desbordamiento)."""
    return ((value - WORD_MIN) % (WORD_MAX - WORD_MIN + 1)) + WORD_MIN


def encode(mnemonic: str, operand: int = 0) -> int:
    return OPCODES[mnemonic] * 100 + operand


def decode(word: int):
    """Devuelve (opcode, operando). Un opcode inválido no está en MNEMONICS."""
    return divmod(word, 100)


def disassemble(word: int) -> str:
    opcode, operand = decode(word)
    name = MNEMONICS.get(opcode)
    if name is None:
        return "???"
    return name if name in NO_OPERAND else f"{name} {operand:02d}"

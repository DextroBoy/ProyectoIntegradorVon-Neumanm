"""Procesador Von Neumann didáctico con ciclo fetch-decode-execute.

El procesador es una máquina de estados con Q = {FETCH, DECODE, EXECUTE, HALT}.
Cada llamada a step_phase() aplica UNA transición δ y devuelve los eventos
(micro-operaciones) que ocurrieron, para que la GUI pueda animarlos.
"""
from collections import deque, namedtuple

from .isa import MEM_SIZE, MNEMONICS, NO_OPERAND, decode, wrap

PHASES = ("FETCH", "DECODE", "EXECUTE", "HALT")

# src / dst son nombres de componentes: PC MAR MDR IR AC ALU MEM CU IN OUT
Event = namedtuple("Event", "src dst text")


class CPU:
    def __init__(self, size: int = MEM_SIZE):
        self.size = size
        self.mem = [0] * size
        self.input_queue = deque()
        self.reset()

    # ------------------------------------------------------------ estado
    def reset(self, clear_memory: bool = False):
        """Vuelve al estado inicial q0 (PC = 0, AC = 0, fase FETCH)."""
        if clear_memory:
            self.mem = [0] * self.size
        self.pc = self.ac = self.ir = self.mar = self.mdr = 0
        self.cur_addr = 0               # dirección de la instrucción en curso
        self.opcode = self.operand = 0
        self.mnemonic = ""
        self.phase = "FETCH"
        self.output = []
        self.error = None
        self.waiting_input = False
        self.instructions_done = 0
        self.last_mem_write = None      # dirección escrita en la última fase
        self.last_events = []

    def load(self, words):
        if len(words) > self.size:
            raise ValueError("El programa no cabe en la memoria")
        self.mem = list(words) + [0] * (self.size - len(words))
        self.reset()

    @property
    def zero(self) -> bool:             # proposición p: "AC = 0"
        return self.ac == 0

    @property
    def negative(self) -> bool:         # proposición q: "AC < 0"
        return self.ac < 0

    @property
    def halted(self) -> bool:
        return self.phase == "HALT"

    def state(self):
        """Estado actual como tupla (fase, PC, AC, IR)."""
        return (self.phase, self.pc, self.ac, self.ir)

    def provide_input(self, value: int):
        self.input_queue.append(wrap(int(value)))

    # ------------------------------------------------------------- ciclo
    def step_phase(self):
        """Aplica una transición de fase. Devuelve la lista de Event."""
        self.last_mem_write = None
        self.last_events = []
        if self.phase == "HALT":
            return self.last_events
        if self.phase == "FETCH":
            self._fetch()
        elif self.phase == "DECODE":
            self._decode()
        else:
            self._execute()
        return self.last_events

    def step_instruction(self):
        """Ejecuta un ciclo completo (FETCH → DECODE → EXECUTE)."""
        events = []
        while not self.halted:
            events += self.step_phase()
            if self.waiting_input:
                break
            if self.phase == "FETCH":        # terminó el EXECUTE
                break
        return events

    def run(self, max_steps: int = 100_000):
        """Ejecuta hasta HALT, espera de INPUT o límite de instrucciones."""
        steps = 0
        while not self.halted and steps < max_steps:
            self.step_instruction()
            if self.waiting_input:
                break
            steps += 1
        if steps >= max_steps and not self.halted:
            self.error = "Límite de instrucciones alcanzado (¿bucle infinito?)"
            self.phase = "HALT"
        return steps

    # ------------------------------------------------------- fases internas
    def _log(self, src, dst, text):
        self.last_events.append(Event(src, dst, text))

    def _fetch(self):
        self.cur_addr = self.pc
        self.mar = self.pc
        self._log("PC", "MAR", f"MAR ← PC  ({self.mar})")
        self.mdr = self.mem[self.mar]
        self._log("MEM", "MDR", f"MDR ← M[{self.mar}]  ({self.mdr})")
        self.ir = self.mdr
        self._log("MDR", "IR", f"IR ← MDR  ({self.ir})")
        self.pc = (self.pc + 1) % self.size
        self._log("PC", "PC", f"PC ← PC + 1  ({self.pc})")
        self.phase = "DECODE"

    def _decode(self):
        self.opcode, self.operand = decode(self.ir)
        name = MNEMONICS.get(self.opcode)
        if name is None:
            self.error = f"Opcode inválido ({self.ir}) en la dirección {self.mar}"
            self.mnemonic = "???"
            self._log("IR", "CU", self.error)
            self.phase = "HALT"
            return
        self.mnemonic = name
        txt = name if name in NO_OPERAND else f"{name} {self.operand}"
        self._log("IR", "CU", f"Decodificar: {txt}")
        self.phase = "EXECUTE"

    def _read_operand(self):
        """MAR ← operando; MDR ← M[MAR]  (lectura de memoria)."""
        self.mar = self.operand
        self._log("IR", "MAR", f"MAR ← {self.operand}")
        self.mdr = self.mem[self.mar]
        self._log("MEM", "MDR", f"MDR ← M[{self.mar}]  ({self.mdr})")

    def _execute(self):
        op = self.mnemonic
        if op == "HALT":
            self._log("CU", "CU", "HALT: el procesador se detiene")
            self.phase = "HALT"
            self.instructions_done += 1
            return

        if op == "LOAD":
            self._read_operand()
            self.ac = self.mdr
            self._log("MDR", "AC", f"AC ← MDR  ({self.ac})")

        elif op == "STORE":
            self.mar = self.operand
            self._log("IR", "MAR", f"MAR ← {self.operand}")
            self.mdr = self.ac
            self._log("AC", "MDR", f"MDR ← AC  ({self.mdr})")
            self.mem[self.mar] = self.mdr
            self.last_mem_write = self.mar
            self._log("MDR", "MEM", f"M[{self.mar}] ← MDR  ({self.mdr})")

        elif op in ("ADD", "SUB", "AND", "OR"):
            self._read_operand()
            self._log("MDR", "ALU", f"ALU ← MDR  ({self.mdr})")
            self._log("AC", "ALU", f"ALU ← AC  ({self.ac})")
            a, b = self.ac, self.mdr
            result = {"ADD": a + b, "SUB": a - b, "AND": a & b, "OR": a | b}[op]
            self.ac = wrap(result)
            self._log("ALU", "AC", f"AC ← {a} {op} {b} = {self.ac}")

        elif op == "NOT":
            self._log("AC", "ALU", f"ALU ← AC  ({self.ac})")
            self.ac = wrap(~self.ac)
            self._log("ALU", "AC", f"AC ← NOT AC = {self.ac}")

        elif op == "JUMP":
            self.pc = self.operand
            self._log("IR", "PC", f"PC ← {self.operand}")

        elif op in ("JZ", "JN"):
            cond = self.zero if op == "JZ" else self.negative
            label = "AC = 0" if op == "JZ" else "AC < 0"
            if cond:
                self.pc = self.operand
                self._log("IR", "PC", f"{label} es verdadero → PC ← {self.operand}")
            else:
                self._log("CU", "CU", f"{label} es falso → no hay salto")

        elif op == "INPUT":
            if not self.input_queue:
                self.waiting_input = True
                self._log("IN", "AC", "Esperando un valor de entrada…")
                return                      # se queda en EXECUTE
            self.waiting_input = False
            self.ac = self.input_queue.popleft()
            self._log("IN", "AC", f"AC ← entrada  ({self.ac})")

        elif op == "OUTPUT":
            self.output.append(self.ac)
            self._log("AC", "OUT", f"Salida: {self.ac}")

        self.instructions_done += 1
        self.phase = "FETCH"

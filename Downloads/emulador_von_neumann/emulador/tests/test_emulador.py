import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assembler.assembler import AsmError, assemble          # noqa: E402
from core.cpu import CPU                                    # noqa: E402
from core.isa import disassemble, encode, wrap              # noqa: E402
from formal import automata                                 # noqa: E402
from formal.cfg import analyze, build_cfg                   # noqa: E402
from gui import notes                                       # noqa: E402
from core.isa import OPCODES                                # noqa: E402

PROG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "programas")


def run_file(name, inputs=()):
    with open(os.path.join(PROG_DIR, name), encoding="utf-8") as f:
        prog = assemble(f.read())
    cpu = CPU()
    cpu.load(prog.words)
    for v in inputs:
        cpu.provide_input(v)
    cpu.run()
    return cpu, prog


class TestISA(unittest.TestCase):
    def test_encode_disassemble(self):
        self.assertEqual(encode("ADD", 7), 307)
        self.assertEqual(disassemble(307), "ADD 07")
        self.assertEqual(disassemble(0), "HALT")
        self.assertEqual(disassemble(9999), "???")

    def test_wrap(self):
        self.assertEqual(wrap(32768), -32768)
        self.assertEqual(wrap(-32769), 32767)
        self.assertEqual(wrap(5), 5)


class TestAssembler(unittest.TestCase):
    def test_labels_and_data(self):
        p = assemble("START: LOAD X\n HALT\nX: DAT -4")
        self.assertEqual(p.words, [102, 0, -4])
        self.assertEqual(p.labels["X"], 2)
        self.assertEqual(p.kinds[2], "data")

    def test_errors_are_collected(self):
        with self.assertRaises(AsmError) as ctx:
            with open(os.path.join(PROG_DIR, "99_error_demo.asm"), encoding="utf-8") as f:
                assemble(f.read())
        lines = [n for n, _ in ctx.exception.errors]
        self.assertGreaterEqual(len(lines), 4)

    def test_duplicate_label(self):
        with self.assertRaises(AsmError):
            assemble("A: HALT\nA: HALT")


class TestCPU(unittest.TestCase):
    def test_fetch_decode_execute_phases(self):
        cpu = CPU()
        cpu.load([encode("LOAD", 2), 0, 42])
        self.assertEqual(cpu.state(), ("FETCH", 0, 0, 0))
        cpu.step_phase()
        self.assertEqual(cpu.state(), ("DECODE", 1, 0, 102))
        cpu.step_phase()
        self.assertEqual(cpu.phase, "EXECUTE")
        cpu.step_phase()
        self.assertEqual((cpu.phase, cpu.ac), ("FETCH", 42))

    def test_suma(self):
        cpu, _ = run_file("01_suma.asm", [7, 5])
        self.assertEqual(cpu.output, [12])
        self.assertTrue(cpu.halted)
        self.assertIsNone(cpu.error)

    def test_cuenta_regresiva(self):
        cpu, _ = run_file("02_cuenta_regresiva.asm", [4])
        self.assertEqual(cpu.output, [4, 3, 2, 1])

    def test_signo(self):
        self.assertEqual(run_file("03_signo.asm", [9])[0].output, [1])
        self.assertEqual(run_file("03_signo.asm", [0])[0].output, [0])
        self.assertEqual(run_file("03_signo.asm", [-5])[0].output, [-1])

    def test_multiplicacion(self):
        self.assertEqual(run_file("04_multiplicacion.asm", [6, 7])[0].output, [42])
        self.assertEqual(run_file("04_multiplicacion.asm", [5, 0])[0].output, [0])

    def test_logica(self):
        cpu, _ = run_file("05_logica.asm", [12, 10])
        self.assertEqual(cpu.output, [12 & 10, 12 | 10, ~12])

    def test_factorial(self):
        for n, f in [(0, 1), (1, 1), (5, 120), (7, 5040)]:
            self.assertEqual(run_file("06_factorial.asm", [n])[0].output, [f])

    def test_overflow_wraps(self):
        cpu = CPU()
        cpu.load([encode("LOAD", 3), encode("ADD", 3), encode("HALT"), 32767])
        cpu.run()
        self.assertEqual(cpu.ac, wrap(65534))

    def test_input_waits(self):
        cpu = CPU()
        cpu.load([encode("INPUT"), encode("OUTPUT"), encode("HALT")])
        cpu.run()
        self.assertTrue(cpu.waiting_input)
        self.assertFalse(cpu.halted)
        cpu.provide_input(9)
        cpu.run()
        self.assertEqual(cpu.output, [9])
        self.assertTrue(cpu.halted)

    def test_invalid_opcode(self):
        cpu = CPU()
        cpu.load([5000])
        cpu.run()
        self.assertTrue(cpu.halted)
        self.assertIn("inválido", cpu.error)

    def test_infinite_loop_guard(self):
        cpu = CPU()
        cpu.load([encode("JUMP", 0)])
        cpu.run(max_steps=500)
        self.assertIn("bucle infinito", cpu.error)

    def test_program_and_data_share_memory(self):
        # Von Neumann: un programa puede modificarse a sí mismo.
        cpu = CPU()
        cpu.load([encode("LOAD", 3), encode("STORE", 2), 0, encode("HALT")])
        cpu.run()
        self.assertEqual(cpu.mem[2], encode("HALT"))


class TestFormal(unittest.TestCase):
    def test_delta_matches_cpu(self):
        """δ del modelo formal coincide con las fases reales del CPU."""
        cpu = CPU()
        cpu.load([encode("LOAD", 3), encode("HALT"), 0, 5])
        state = automata.Q0
        for _ in range(20):
            if cpu.halted:
                break
            before_phase = cpu.phase
            cpu.step_phase()
            instr = cpu.mnemonic if before_phase in ("DECODE", "EXECUTE") else ""
            state = automata.delta(before_phase, instr)
            self.assertEqual(state, cpu.phase)
        self.assertIn(cpu.phase, automata.F)

    def test_truth_tables(self):
        _, rows = automata.truth_table("AND")
        self.assertEqual(rows, [[0, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 1]])
        _, rows = automata.truth_table("OR")
        self.assertEqual(rows, [[0, 0, 0], [0, 1, 1], [1, 0, 1], [1, 1, 1]])
        _, rows = automata.truth_table("NOT")
        self.assertEqual(rows, [[0, 1], [1, 0]])

    def test_cfg_countdown(self):
        _, prog = run_file("02_cuenta_regresiva.asm", [2])
        nodes, edges = build_cfg(prog)
        summary, warnings = analyze(prog)
        self.assertTrue(summary["tiene ciclos"])
        self.assertEqual(warnings, [])
        self.assertEqual(summary["alcanzables"], summary["nodos"])
        self.assertIn((prog.labels["LOOP"] + 1, prog.labels["FIN"], "true"), edges)

    def test_cfg_detects_problems(self):
        prog = assemble("LOOP: JUMP LOOP\nHALT")
        _, warnings = analyze(prog)
        text = " ".join(warnings)
        self.assertIn("inalcanzable", text)
        self.assertIn("no se puede llegar a HALT", text)

    def test_all_examples_pass_verification(self):
        for name in sorted(os.listdir(PROG_DIR)):
            if name.startswith("99"):
                continue
            with open(os.path.join(PROG_DIR, name), encoding="utf-8") as f:
                prog = assemble(f.read())
            _, warnings = analyze(prog)
            self.assertEqual(warnings, [], name)


class TestNotes(unittest.TestCase):
    def test_every_instruction_has_a_note(self):
        self.assertEqual(set(OPCODES), set(notes.INSTR))

    def test_explain_never_fails_and_is_never_empty(self):
        for name in sorted(os.listdir(PROG_DIR)):
            if name.startswith("99"):
                continue
            with open(os.path.join(PROG_DIR, name), encoding="utf-8") as f:
                cpu = CPU()
                cpu.load(assemble(f.read()).words)
            for v in (3, 4, 5):
                cpu.provide_input(v)
            last = None
            title, text = notes.explain(cpu, last)
            self.assertTrue(title and text)
            for _ in range(400):
                if cpu.halted:
                    break
                prev = cpu.phase
                cpu.step_phase()
                title, text = notes.explain(cpu, prev)
                self.assertTrue(title and text, (name, prev))
                self.assertNotIn("None", text)

    def test_error_note(self):
        cpu = CPU()
        cpu.load([5000])
        cpu.run()
        self.assertEqual(notes.explain(cpu, "DECODE")[0], "Error de ejecución")


if __name__ == "__main__":
    unittest.main()

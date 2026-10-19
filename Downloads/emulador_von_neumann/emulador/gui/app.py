"""Ventana principal del emulador Von Neumann (customtkinter)."""
import os
import sys
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from assembler.assembler import AsmError, assemble          # noqa: E402
from core.cpu import CPU                                    # noqa: E402
from core.isa import DESCRIPTIONS, OPCODES, disassemble     # noqa: E402
from formal import automata                                 # noqa: E402
from formal.cfg import analyze                              # noqa: E402
from gui import notes                                       # noqa: E402
from gui.views import (C, MONO, SANS, ArchView, AutomatonView,  # noqa: E402
                       CFGView, MemView)

PROG_DIR = os.path.join(ROOT, "programas")
SPEEDS = {1: 1000, 2: 700, 3: 450, 4: 300, 5: 200, 6: 120, 7: 70, 8: 40, 9: 15, 10: 1}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Emulador Von Neumann · Arquitectura de Computadores + Matemáticas Discretas")
        self.geometry("1400x880")
        self.minsize(1150, 720)
        self.configure(fg_color=C["bg"])

        self.cpu = CPU()
        self.program = None
        self.source = None
        self.running = False
        self.resume_after_input = False
        self.after_id = None
        self.visited = set()
        self.alu_last = "—"
        self.out_shown = 0
        self.last_transition = "—"
        self.last_phase = None
        self.wait_shown = False

        self._build_topbar()
        self.tabs = ctk.CTkTabview(self, fg_color=C["bg"])
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self._build_sim_tab(self.tabs.add("Simulador"))
        self._build_formal_tab(self.tabs.add("Modelo formal"))
        self._build_notes_tab(self.tabs.add("Notas para exponer"))
        self._build_help_tab(self.tabs.add("ISA y ayuda"))
        self._build_statusbar()

        for key, fn in (("<F5>", self.toggle_run), ("<F6>", self.step_phase),
                        ("<F7>", self.step_instruction), ("<F8>", self.reset_program)):
            self.bind(key, lambda e, f=fn: f())

        self.examples = sorted(f for f in os.listdir(PROG_DIR) if f.endswith(".asm")) \
            if os.path.isdir(PROG_DIR) else []
        if self.examples:
            self.example_menu.configure(values=self.examples)
            self.example_menu.set(self.examples[0])
            self.load_example(self.examples[0])

    # ================================================================ UI
    def _btn(self, parent, text, cmd, color=None, width=120):
        return ctk.CTkButton(parent, text=text, command=cmd, width=width, height=32,
                             fg_color=color or C["box"], hover_color=C["line"],
                             text_color=C["text"], corner_radius=8,
                             font=(SANS, 12, "bold"))

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=10)
        bar.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(bar, text="⚙  Emulador Von Neumann", font=(SANS, 16, "bold"),
                     text_color=C["text"]).pack(side="left", padx=(14, 18), pady=8)
        self.btn_run = self._btn(bar, "▶ Ejecutar  F5", self.toggle_run, C["accent"], 140)
        self.btn_run.pack(side="left", padx=4)
        self._btn(bar, "→ Fase  F6", self.step_phase, width=110).pack(side="left", padx=4)
        self._btn(bar, "⇥ Instrucción  F7", self.step_instruction, width=150).pack(side="left", padx=4)
        self._btn(bar, "↻ Reiniciar  F8", self.reset_program, width=130).pack(side="left", padx=4)
        ctk.CTkLabel(bar, text="Velocidad", text_color=C["muted"],
                     font=(SANS, 11)).pack(side="left", padx=(24, 6))
        self.speed = ctk.CTkSlider(bar, from_=1, to=10, number_of_steps=9, width=170)
        self.speed.set(4)
        self.speed.pack(side="left", padx=4)

    def _build_sim_tab(self, tab):
        tab.grid_columnconfigure(0, weight=0)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_columnconfigure(2, weight=0)
        tab.grid_rowconfigure(0, weight=1)

        # --- columna izquierda: editor + consola E/S
        left = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10, width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        left.grid_propagate(False)
        ctk.CTkLabel(left, text="PROGRAMA (ensamblador)", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=10)
        self.example_menu = ctk.CTkOptionMenu(row, values=["—"], command=self.load_example, width=190)
        self.example_menu.pack(side="left")
        self._btn(row, "Abrir", self.open_file, width=50).pack(side="left", padx=(6, 0))
        self.editor = ctk.CTkTextbox(left, width=290, height=290, fg_color=C["bg"],
                                     text_color=C["text"], font=(MONO, 12), wrap="none",
                                     border_width=1, border_color=C["line"])
        self.editor.pack(fill="both", expand=False, padx=10, pady=8)
        self.editor.tag_config("cur", background="#264a7a")
        self.editor.tag_config("err", background="#6b2230")
        row2 = ctk.CTkFrame(left, fg_color="transparent")
        row2.pack(fill="x", padx=10)
        self._btn(row2, "Ensamblar", self.assemble_current, C["accent"], 110).pack(side="left")
        self._btn(row2, "Guardar", self.save_file, width=80).pack(side="left", padx=6)

        ctk.CTkLabel(left, text="CONSOLA  (haz clic y escribe; Enter envía)", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(12, 2))
        self.console = ctk.CTkTextbox(left, width=290, height=110, fg_color=C["bg"],
                                      font=(MONO, 12), border_width=1, border_color=C["line"])
        self.console.pack(fill="x", padx=10)
        self.console.tag_config("out", foreground=C["green"])
        self.console.tag_config("in", foreground=C["cyan"])
        self.console.tag_config("wait", foreground=C["orange"])
        self.console.configure(state="disabled")
        # lo que se teclee sobre la consola se redirige a la línea de entrada
        self.console.bind("<Key>", self._console_key)
        self.console.bind("<Button-1>", lambda e: self.after(1, self.entry.focus_set))
        row3 = ctk.CTkFrame(left, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=(6, 12))
        ctk.CTkLabel(row3, text="›", text_color=C["cyan"], font=(MONO, 16, "bold"),
                     width=14).pack(side="left")
        self.entry = ctk.CTkEntry(row3, placeholder_text="número + Enter", width=190,
                                  border_width=2, border_color=C["line"])
        self.entry.pack(side="left", padx=(2, 0))
        self.entry.bind("<Return>", self.submit_input)
        self._btn(row3, "Enviar", self.submit_input, width=70).pack(side="left", padx=6)

        # --- columna central: arquitectura + bitácora
        mid = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10)
        mid.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        ctk.CTkLabel(mid, text="ARQUITECTURA  (flechas = flujo de datos · clic en un componente = explicación)",
                     text_color=C["muted"], font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        self.arch = ArchView(mid, self.show_component)
        self.arch.canvas.pack(padx=10, pady=4)
        self.note_title = ctk.CTkLabel(mid, text="", text_color=C["cyan"], font=(SANS, 12, "bold"),
                                       anchor="w")
        self.note_title.pack(fill="x", padx=12)
        self.note_box = ctk.CTkTextbox(mid, height=84, fg_color=C["bg"], text_color=C["text"],
                                       font=(SANS, 12), wrap="word", border_width=1,
                                       border_color=C["cyan"])
        self.note_box.pack(fill="x", padx=10, pady=(2, 6))
        self.note_box.configure(state="disabled")
        ctk.CTkLabel(mid, text="BITÁCORA DE MICRO-OPERACIONES", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12)
        self.log = ctk.CTkTextbox(mid, height=110, fg_color=C["bg"], font=(MONO, 11),
                                  border_width=1, border_color=C["line"])
        self.log.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        for tag, color in (("head", C["accent"]), ("err", C["red"]), ("ok", C["green"]),
                           ("dim", C["muted"])):
            self.log.tag_config(tag, foreground=color)
        self.log.configure(state="disabled")

        # --- columna derecha: memoria
        right = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10)
        right.grid(row=0, column=2, sticky="nsew", padx=(8, 0), pady=4)
        ctk.CTkLabel(right, text="MEMORIA RAM  (100 celdas)", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        self.mem = MemView(right, self.show_cell)
        self.mem.canvas.pack(padx=10, pady=6)
        legend = ctk.CTkFrame(right, fg_color="transparent")
        legend.pack(fill="x", padx=10)
        for text, color in (("■ código", C["accent"]), ("■ dato", C["green"]),
                            ("▭ PC", C["cyan"]), ("▭ MAR", C["purple"]), ("▭ escrita", C["orange"])):
            ctk.CTkLabel(legend, text=text, text_color=color, font=(SANS, 10)).pack(side="left", padx=4)
        self.cell_info = ctk.CTkLabel(right, text="Haz clic en una celda para ver su contenido",
                                      text_color=C["muted"], font=(MONO, 11), justify="left",
                                      wraplength=420)
        self.cell_info.pack(anchor="w", padx=12, pady=10)

    def _build_formal_tab(self, tab):
        tab.grid_columnconfigure((0, 1, 2), weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
        ctk.CTkLabel(left, text="ÁLGEBRA BOOLEANA · TABLAS DE VERDAD", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self._caption(left, notes.FORMAL_NOTES["tables"])
        tables = ctk.CTkTextbox(left, fg_color=C["bg"], font=(MONO, 11), wrap="none")
        tables.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        blocks = []
        for op in ("AND", "OR", "NOT"):
            h, r = automata.truth_table(op)
            blocks.append(f"Instrucción {op}  (por bit)\n" + automata.format_table(h, r))
        for op in ("JZ", "JN"):
            h, r = automata.jump_table(op)
            blocks.append(f"Instrucción {op}\n" + automata.format_table(h, r))
        tables.insert("1.0", "\n\n".join(blocks))
        tables.configure(state="disabled")

        mid = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10)
        mid.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)
        ctk.CTkLabel(mid, text="AUTÓMATA FINITO  M = (Q, Σ, δ, q0, F)", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self._caption(mid, notes.FORMAL_NOTES["automata"])
        self.auto = AutomatonView(mid)
        self.auto.canvas.pack(padx=10)
        self.tuple_label = ctk.CTkLabel(mid, text="", font=(MONO, 12, "bold"), text_color=C["cyan"])
        self.tuple_label.pack(anchor="w", padx=12, pady=(8, 0))
        self.delta_label = ctk.CTkLabel(mid, text="", font=(MONO, 11), text_color=C["text"])
        self.delta_label.pack(anchor="w", padx=12)
        definition = ctk.CTkTextbox(mid, height=120, fg_color=C["bg"], font=(MONO, 11))
        definition.pack(fill="x", padx=10, pady=10)
        definition.insert("1.0", automata.definition_text())
        definition.configure(state="disabled")

        right = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=4)
        ctk.CTkLabel(right, text="GRAFO DE FLUJO DE CONTROL", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        self._caption(right, notes.FORMAL_NOTES["cfg"])
        self.coverage = ctk.CTkLabel(right, text="Cobertura: —", text_color=C["green"],
                                     font=(SANS, 11, "bold"))
        self.coverage.pack(anchor="w", padx=12)
        holder = ctk.CTkFrame(right, fg_color="transparent")
        holder.pack(fill="both", expand=True, padx=10, pady=4)
        self.cfg = CFGView(holder, height=330)
        sb = ctk.CTkScrollbar(holder, command=self.cfg.canvas.yview)
        self.cfg.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cfg.canvas.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(right, text="VERIFICACIÓN DEL GRAFO", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12)
        self.analysis = ctk.CTkTextbox(right, height=130, fg_color=C["bg"], font=(MONO, 11))
        self.analysis.pack(fill="x", padx=10, pady=(2, 10))
        self.analysis.configure(state="disabled")

    def _build_help_tab(self, tab):
        box = ctk.CTkTextbox(tab, fg_color=C["panel"], font=(MONO, 12), wrap="word")
        box.pack(fill="both", expand=True, pady=4)
        lines = ["CONJUNTO DE INSTRUCCIONES (ISA)",
                 "I = {" + ", ".join(OPCODES) + "}", "",
                 "  Opcode  Instrucción  Efecto",
                 "  ------  -----------  ------"]
        for name, code in OPCODES.items():
            lines.append(f"  {code:>5}   {name:<11}  {DESCRIPTIONS[name]}")
        lines += ["", "Cada palabra de memoria = opcode × 100 + operando  (p. ej. 305 = ADD 5).",
                  "Programa y datos comparten la MISMA memoria (arquitectura Von Neumann).",
                  "Las palabras son enteros de 16 bits con signo (−32768 … 32767).", "",
                  "SINTAXIS", "  ETIQUETA:  INSTRUCCIÓN  operando   ; comentario",
                  "  X:         DAT  valor                  ; reserva una celda de datos", "",
                  "ATAJOS", "  F5 ejecutar/pausar   F6 una fase   F7 una instrucción   F8 reiniciar"]
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=8, height=30)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        self.status_left = ctk.CTkLabel(bar, text="", font=(MONO, 11), text_color=C["text"])
        self.status_left.pack(side="left", padx=12, pady=4)
        self.status_right = ctk.CTkLabel(bar, text="", font=(SANS, 11, "bold"), text_color=C["muted"])
        self.status_right.pack(side="right", padx=12)

    # ======================================================= utilidades
    def _append(self, widget, text, tag=None):
        widget.configure(state="normal")
        widget.insert("end", text, tag) if tag else widget.insert("end", text)
        widget.see("end")
        widget.configure(state="disabled")

    def _log(self, text, tag=None):
        self._append(self.log, text + "\n", tag)
        try:
            if int(self.log.index("end-1c").split(".")[0]) > 600:
                self.log.configure(state="normal")
                self.log.delete("1.0", "100.0")
                self.log.configure(state="disabled")
        except (ValueError, tk.TclError, AttributeError):
            pass

    def _set_status(self, text, color=None):
        self.status_right.configure(text=text, text_color=color or C["muted"])

    def _clear_console(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        self.out_shown = 0
        self.wait_shown = False

    # ================================================== cargar / ensamblar
    def load_example(self, name):
        self._set_editor(self._read(os.path.join(PROG_DIR, name)))
        self.assemble_current()

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Ensamblador", "*.asm"), ("Texto", "*.txt"), ("Todos", "*.*")])
        if path:
            self._set_editor(self._read(path))
            self.assemble_current()

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".asm",
                                            filetypes=[("Ensamblador", "*.asm")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", "end-1c"))

    @staticmethod
    def _read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _set_editor(self, text):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)

    def assemble_current(self):
        self._stop_run()
        text = self.editor.get("1.0", "end-1c")
        self.editor.tag_remove("err", "1.0", "end")
        try:
            prog = assemble(text)
        except AsmError as e:
            for n, msg in e.errors:
                self.editor.tag_add("err", f"{n}.0", f"{n}.end")
                self._log(f"✖ Línea {n}: {msg}", "err")
            self._set_status(f"{len(e.errors)} error(es) de ensamblado", C["red"])
            return False
        self.program, self.source = prog, text
        self.cpu.input_queue.clear()
        self.cpu.load(prog.words)
        self.visited, self.alu_last = set(), "—"
        self.last_phase = None
        self._clear_console()
        self.cfg.draw(prog)
        self._fill_analysis(prog)
        self._log(f"✔ Ensamblado: {len(prog.words)} celdas "
                  f"({sum(k == 'code' for k in prog.kinds.values())} instrucciones, "
                  f"{sum(k == 'data' for k in prog.kinds.values())} datos)", "ok")
        self._set_status("Programa listo", C["green"])
        self._render([])
        return True

    def _fill_analysis(self, prog):
        summary, warnings = analyze(prog)
        lines = [f"Nodos: {summary.get('nodos')}   Aristas: {summary.get('aristas')}"]
        if "alcanzables" in summary:
            lines.append(f"Alcanzables desde el inicio: {summary['alcanzables']}")
            lines.append(f"Con camino a HALT: {summary['con camino a HALT']}")
            lines.append("Contiene ciclos: " + ("sí" if summary["tiene ciclos"] else "no"))
        lines += [("⚠ " + w) for w in warnings] or ["✔ Todos los caminos llevan a HALT"]
        self.analysis.configure(state="normal")
        self.analysis.delete("1.0", "end")
        self.analysis.insert("1.0", "\n".join(lines))
        self.analysis.configure(state="disabled")

    def _ready(self):
        if self.program is None or self.editor.get("1.0", "end-1c") != self.source:
            return self.assemble_current()
        return True

    # ============================================================ control
    def reset_program(self):
        self._stop_run()
        if self.program is None:
            return
        self.cpu.input_queue.clear()
        self.cpu.load(self.program.words)
        self.visited, self.alu_last = set(), "—"
        self._clear_console()
        self.last_transition = "—"
        self.last_phase = None
        self._log("↻ Reiniciado (PC = 0, memoria recargada)", "dim")
        self._set_status("Reiniciado", C["muted"])
        self._render([])

    def step_phase(self):
        if self._ready():
            self._advance("phase")

    def step_instruction(self):
        if self._ready():
            self._advance("instr")

    def toggle_run(self):
        if self.running:
            self._stop_run()
            self._set_status("En pausa", C["orange"])
            return
        if not self._ready():
            return
        if self.cpu.halted:
            self.reset_program()
        self.running = True
        self.resume_after_input = False
        self.btn_run.configure(text="⏸ Pausar  F5")
        self._tick()

    def _stop_run(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except (ValueError, tk.TclError):
                pass
            self.after_id = None
        self.btn_run.configure(text="▶ Ejecutar  F5")

    def _tick(self):
        if not self.running:
            return
        cpu = self.cpu
        level = int(round(self.speed.get()))
        if level <= 6:
            self._advance("phase")
        elif level <= 8:
            self._advance("instr")
        else:
            for _ in range(25):
                self._advance("instr", log=False)
                if cpu.halted or cpu.waiting_input:
                    break
        if cpu.halted or cpu.waiting_input:
            self._stop_run()
            return
        self.after_id = self.after(SPEEDS[level], self._tick)

    def _advance(self, mode, log=True):
        cpu = self.cpu
        if cpu.halted:
            self._set_status("El programa terminó. Pulsa Reiniciar.", C["orange"])
            return
        prev = cpu.phase
        events = cpu.step_phase() if mode == "phase" else cpu.step_instruction()
        if prev == "FETCH" or mode == "instr":
            self.visited.add(cpu.cur_addr)
        if any(e.src == "ALU" and e.dst == "AC" for e in events):
            self.alu_last = cpu.mnemonic
        self.last_phase = prev if mode == "phase" else "INSTR"
        if mode == "phase":
            instr = cpu.mnemonic if prev in ("DECODE", "EXECUTE") else "ε"
            self.last_transition = f"δ({prev}, {instr}) = {cpu.phase}"
        else:
            self.last_transition = f"instrucción completa → {cpu.phase}"
        if log:
            if mode == "phase":
                self._log(f"▸ {prev}", "head")
            else:
                self._log(f"▸ Instrucción en [{cpu.cur_addr}]: {disassemble(cpu.ir)}", "head")
            for e in events:
                self._log("    " + e.text)
        while self.out_shown < len(cpu.output):
            self._append(self.console, f"▶ {cpu.output[self.out_shown]}\n", "out")
            self.out_shown += 1
        if cpu.waiting_input:
            if not self.wait_shown:
                self._append(self.console, "⏳ El programa pide un número. Escríbelo aquí.\n", "wait")
                self.wait_shown = True
            self.resume_after_input = self.running
            self._stop_run()
            self._set_status("Esperando entrada: escribe un número y pulsa Enter", C["cyan"])
            self.entry.focus_set()
        elif cpu.error:
            self._log("✖ " + cpu.error, "err")
            self._set_status("Error de ejecución", C["red"])
        elif cpu.halted:
            self._log(f"■ HALT · {cpu.instructions_done} instrucciones ejecutadas", "ok")
            self._set_status("Programa finalizado", C["green"])
        else:
            self._set_status("Ejecutando" if self.running else "Listo", C["accent"])
        self._render(events)

    def submit_input(self, _event=None):
        text = self.entry.get().strip()
        try:
            value = int(text)
        except ValueError:
            self._set_status("La entrada debe ser un entero", C["red"])
            return
        self.cpu.provide_input(value)
        self.wait_shown = False
        self.entry.delete(0, "end")
        self._append(self.console, f"⌨ {value}\n", "in")
        if self.resume_after_input:
            self.resume_after_input = False
            self.toggle_run()
        else:
            self._set_status("Entrada recibida", C["green"])
            self._render(self.cpu.last_events)

    # ============================================================ notas
    @staticmethod
    def _caption(parent, text):
        ctk.CTkLabel(parent, text=text, text_color=C["muted"], font=(SANS, 11), justify="left",
                     wraplength=330, anchor="w").pack(fill="x", padx=12, pady=(0, 6))

    def _set_note(self, title, text):
        self.note_title.configure(text=title)
        self.note_box.configure(state="normal")
        self.note_box.delete("1.0", "end")
        self.note_box.insert("1.0", text)
        self.note_box.configure(state="disabled")

    def show_component(self, name):
        """Clic en un componente del diagrama: muestra su explicación."""
        if name in notes.COMPONENTS:
            self._set_note(*notes.COMPONENTS[name])

    def _console_key(self, event):
        """Redirige lo que se teclea sobre la consola hacia la línea de entrada.
        Las demás teclas (F5-F8, Ctrl+C, flechas…) conservan su comportamiento."""
        if event.state & 0x4:                 # Ctrl+C, Ctrl+A… funcionan normal
            return None
        if event.keysym in ("Return", "KP_Enter"):
            self.entry.focus_set()
            self.submit_input()
            return "break"
        if event.keysym == "BackSpace":
            self.entry.focus_set()
            text = self.entry.get()
            self.entry.delete(0, "end")
            self.entry.insert(0, text[:-1])
            return "break"
        if event.char and event.char.isprintable():
            self.entry.focus_set()
            self.entry.insert("end", event.char)
            return "break"
        return None

    def _build_notes_tab(self, tab):
        box = ctk.CTkTextbox(tab, fg_color=C["panel"], font=(MONO, 12), wrap="word")
        box.pack(fill="both", expand=True, pady=4)
        box.insert("1.0", notes.GUIDE)
        box.configure(state="disabled")

    # ============================================================ dibujo
    def show_cell(self, addr):
        word = self.cpu.mem[addr]
        kind = self.program.kinds.get(addr) if self.program else None
        label = {"code": "instrucción", "data": "dato", None: "libre"}[kind]
        extra = f"   →  {disassemble(word)}" if kind == "code" else ""
        self.cell_info.configure(text=f"M[{addr}] = {word}   ({label}){extra}", text_color=C["text"])

    def _highlight_editor(self):
        self.editor.tag_remove("cur", "1.0", "end")
        cpu = self.cpu
        if not self.program or self.editor.get("1.0", "end-1c") != self.source:
            return
        addr = cpu.cur_addr if (cpu.phase in ("DECODE", "EXECUTE") or cpu.halted) else cpu.pc
        line = self.program.lines.get(addr)
        if line:
            self.editor.tag_add("cur", f"{line}.0", f"{line}.end")
            self.editor.see(f"{line}.0")

    def _render(self, events):
        cpu = self.cpu
        self.arch.update(cpu, events, self.alu_last, len(cpu.input_queue))
        self.mem.update(cpu, self.program)
        self.auto.update(cpu.phase)
        done, total = self.cfg.update(cpu, self.visited)
        self.coverage.configure(text=f"Cobertura: {done}/{total} nodos recorridos")
        self.tuple_label.configure(
            text=f"q = ({cpu.phase}, PC={cpu.pc}, AC={cpu.ac}, IR={cpu.ir})")
        self.delta_label.configure(
            text=self.last_transition + ("    q ∈ F ✔" if cpu.halted and not cpu.error else ""))
        self._highlight_editor()
        self.entry.configure(border_color=C["cyan"] if cpu.waiting_input else C["line"])
        self._set_note(*notes.explain(cpu, self.last_phase))
        self.status_left.configure(
            text=f"Fase: {cpu.phase:<8} PC={cpu.pc:<3} AC={cpu.ac:<6} IR={cpu.ir:<6} "
                 f"Instrucciones: {cpu.instructions_done}")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

"""Ventana principal del emulador Von Neumann (customtkinter)."""
import os
import sys
import threading
import time
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

# --- Color-coded event categories for the micro-operations log ---
_EVENT_CATEGORIES = {
    "mem_read":  {"prefix": "📖", "color": "#4fd8e8", "tag": "ev_memr"},     # cyan
    "mem_write": {"prefix": "📝", "color": "#ffb454", "tag": "ev_memw"},     # orange
    "alu":       {"prefix": "⚡", "color": "#3ddc97", "tag": "ev_alu"},      # green
    "jump":      {"prefix": "↪",  "color": "#b48cff", "tag": "ev_jump"},     # purple
    "control":   {"prefix": "🔧", "color": "#4f9dff", "tag": "ev_ctrl"},     # accent/blue
    "io":        {"prefix": "📟", "color": "#e8edf7", "tag": "ev_io"},       # text
}


def _classify_event(event):
    """Classify a CPU event into a category for color-coding."""
    text = event.text.lower()
    src, dst = event.src, event.dst
    if dst == "MEM" or src == "MEM":
        if "←" in event.text and dst == "MEM":
            return "mem_write"
        return "mem_read"
    if src == "ALU" or dst == "ALU":
        return "alu"
    if "pc ←" in text and dst == "PC" and src != "PC":
        return "jump"
    if src in ("IN", "OUT") or dst in ("IN", "OUT"):
        return "io"
    if "salto" in text or "jump" in text:
        return "jump"
    return "control"


# Plantilla que se carga al elegir "✎ Crear propio asm" en el menú de programas.
# Usa la sintaxis real del ISA educativo (LOAD/ADD/OUTPUT/HALT y etiquetas con ":").
CUSTOM_TEMPLATE = """; ✎ Tu propio programa ensamblador
; Modifica esto libremente y presiona F5:
; se ensambla y ejecuta automáticamente.

INICIO: LOAD  A        ; AC = A
        ADD   B        ; AC = A + B
        OUTPUT         ; muestra AC (la suma) en la consola
        HALT           ; termina

A:      DAT 3
B:      DAT 5
"""

# Respaldo solo-ASCII para la vista del código NASM de la ventana DLL. Se usa
# unicamente si no se puede leer dll/suma.asm (p. ej. si el archivo fue borrado).
FALLBACK_SUMA_ASM = """; =====================================================================
;  suma.asm  -  funcion suma(a, b) para Windows x64, ensamblada con NASM
; ---------------------------------------------------------------------
;  Convencion de llamada Microsoft x64:
;    * 1er argumento entero  -> RCX
;    * 2do argumento entero  -> RDX
;    * valor de retorno      -> RAX
; =====================================================================

bits 64
default rel

global suma

section .text

suma:
    mov rax, rcx
    add rax, rdx
    ret
"""


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
        self._step_number = 0          # global step counter for console
        self._input_flash_id = None    # for flashing input prompt
        self._log_cycle_num = 0        # cycle number for log separators
        self._log_last_phase = None    # track phase changes for log formatting
        self._phase_history = []       # últimas transiciones visibles del ciclo

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

        self.special = "✎ Crear propio asm"
        self.examples = sorted(f for f in os.listdir(PROG_DIR) if f.endswith(".asm")) \
            if os.path.isdir(PROG_DIR) else []
        # La opción para escribir asm propio siempre va primero.
        self.example_menu.configure(values=[self.special] + self.examples)
        if self.examples:
            # El autoload inicial sigue cargando el PRIMER EJEMPLO REAL.
            self.example_menu.set(self.examples[0])
            self.load_example(self.examples[0])
        else:
            self.example_menu.set(self.special)

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
        self.btn_dll = self._btn(bar, "Σ Suma via DLL", self.open_suma_dll, width=150)
        self.btn_dll.pack(side="left", padx=4)
        ctk.CTkLabel(bar, text="Velocidad", text_color=C["muted"],
                     font=(SANS, 11)).pack(side="left", padx=(24, 6))
        self.speed = ctk.CTkSlider(bar, from_=1, to=10, number_of_steps=9, width=170)
        self.speed.set(4)
        self.speed.pack(side="left", padx=4)

    def open_suma_dll(self):
        """Ventana: suma real por DLL (suma.dll) + código NASM x64 de suma.asm."""
        dll_path = os.path.join(ROOT, "dll", "suma.dll")
        src_path = os.path.join(ROOT, "dll", "llamar_suma.py")

        win = ctk.CTkToplevel(self)
        win.title("Suma via DLL (NASM x64) · suma.asm")
        win.geometry("720x640")
        win.minsize(660, 560)
        win.configure(fg_color=C["bg"])
        win.transient(self)

        # ------------------------------------------------ (a) función existente
        ctk.CTkLabel(win, text="SUMA CALCULADA POR UNA DLL REAL (NASM x64)",
                     font=(SANS, 15, "bold"), text_color=C["text"]).pack(pady=(14, 2))
        ctk.CTkLabel(win, text=".asm → nasm -f win64 → .obj → gcc -shared → .dll → "
                               "llamada desde Python con ctypes",
                     font=(SANS, 11), text_color=C["muted"], wraplength=640,
                     justify="center").pack(padx=20)

        form = ctk.CTkFrame(win, fg_color=C["panel"], corner_radius=10)
        form.pack(fill="x", padx=20, pady=(10, 6))
        form.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(form, text="Número A", font=(SANS, 12, "bold"),
                     text_color=C["muted"]).grid(row=0, column=0, sticky="w",
                                                 padx=14, pady=(8, 2))
        ctk.CTkLabel(form, text="Número B", font=(SANS, 12, "bold"),
                     text_color=C["muted"]).grid(row=0, column=1, sticky="w",
                                                 padx=14, pady=(8, 2))
        entry_a = ctk.CTkEntry(form, placeholder_text="p. ej. 4", border_width=2,
                               border_color=C["line"], font=(MONO, 14))
        entry_a.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        entry_b = ctk.CTkEntry(form, placeholder_text="p. ej. 5", border_width=2,
                               border_color=C["line"], font=(MONO, 14))
        entry_b.grid(row=1, column=1, sticky="ew", padx=14, pady=(0, 10))

        actions = ctk.CTkFrame(win, fg_color="transparent")
        actions.pack(pady=(0, 2))
        btn_sumar = ctk.CTkButton(actions, text="Sumar", width=130, height=32,
                                  fg_color=C["accent"], hover_color=C["line"],
                                  text_color=C["text"], corner_radius=8,
                                  font=(SANS, 12, "bold"))
        btn_sumar.pack(side="left", padx=6)
        btn_ver = ctk.CTkButton(actions, text="Ver llamar_suma.py", width=170, height=32,
                                fg_color=C["box"], hover_color=C["line"],
                                text_color=C["text"], corner_radius=8,
                                font=(SANS, 12, "bold"))
        btn_ver.pack(side="left", padx=6)

        error = ctk.CTkLabel(win, text="", font=(SANS, 12, "bold"),
                             text_color=C["red"], wraplength=640, justify="center")
        result = ctk.CTkLabel(win, text="Resultado: —", font=(SANS, 20, "bold"),
                              text_color=C["accent"])
        detail = ctk.CTkLabel(win, text="", font=(SANS, 11), text_color=C["muted"])
        error.pack()
        result.pack(pady=(2, 0))
        detail.pack()

        def sumar():
            error.configure(text="")
            try:
                a = int(entry_a.get().strip())
                b = int(entry_b.get().strip())
            except ValueError:
                result.configure(text="Resultado: —")
                detail.configure(text="")
                error.configure(text="✖ Escribe dos números enteros válidos.")
                return
            if not os.path.isfile(dll_path):
                result.configure(text="Resultado: —")
                detail.configure(text="")
                error.configure(text="✖ No se encontró dll\\suma.dll.\n"
                                     "Compílala con dll\\compilar.bat y vuelve a intentar.")
                return
            try:
                # Import perezoso: si la DLL falta, la GUI igual arranca sin problemas.
                from dll.llamar_suma import suma_dll
                valor = suma_dll(a, b)
            except Exception as exc:  # DLL corrupta, símbolo ausente, etc.
                result.configure(text="Resultado: —")
                detail.configure(text="")
                error.configure(text=f"✖ No se pudo llamar a suma.dll: {exc}")
                return
            result.configure(text=f"Resultado: {valor}")
            detail.configure(text="(calculado por suma.dll)")

        def ver_codigo():
            sub = ctk.CTkToplevel(win)
            sub.title("dll/llamar_suma.py")
            sub.geometry("620x420")
            sub.configure(fg_color=C["bg"])
            sub.transient(win)
            ctk.CTkLabel(sub, text="dll\\llamar_suma.py  ·  todo el código Python necesario",
                         font=(SANS, 12, "bold"), text_color=C["muted"]).pack(
                anchor="w", padx=12, pady=(10, 4))
            box = ctk.CTkTextbox(sub, fg_color=C["panel"], text_color=C["text"],
                                 font=(MONO, 12), wrap="none", border_width=1,
                                 border_color=C["line"])
            box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            try:
                with open(src_path, encoding="utf-8") as f:
                    box.insert("1.0", f.read())
            except OSError as exc:
                box.insert("1.0", f"No se pudo leer el archivo:\n{exc}")
            box.configure(state="disabled")

        btn_sumar.configure(command=sumar)
        btn_ver.configure(command=ver_codigo)

        # ------------------------------------------------ (b) código NASM (solo lectura)
        ctk.CTkFrame(win, fg_color=C["line"], height=1).pack(
            fill="x", padx=20, pady=(8, 6))

        head = ctk.CTkFrame(win, fg_color="transparent")
        head.pack(fill="x", padx=20)
        ctk.CTkLabel(head, text="CÓDIGO NASM X64 (dll/suma.asm)",
                     font=(SANS, 11, "bold"), text_color=C["accent"]).pack(side="left")
        btn_recargar = ctk.CTkButton(head, text="↺ Recargar", width=110, height=28,
                                     fg_color=C["box"], hover_color=C["line"],
                                     text_color=C["text"], corner_radius=8,
                                     font=(SANS, 11, "bold"))
        btn_recargar.pack(side="right")

        codigo = ctk.CTkTextbox(win, fg_color=C["bg"], text_color=C["text"],
                                font=(MONO, 11), wrap="none", border_width=1,
                                border_color=C["line"])
        codigo.pack(fill="both", expand=True, padx=20, pady=(4, 12))

        def leer_suma_asm():
            """Contenido real de dll/suma.asm; respaldo ASCII si no se puede leer."""
            try:
                with open(os.path.join(ROOT, "dll", "suma.asm"), encoding="utf-8") as f:
                    return f.read()
            except OSError:
                return FALLBACK_SUMA_ASM

        def recargar_codigo():
            codigo.configure(state="normal")
            codigo.delete("1.0", "end")
            codigo.insert("1.0", leer_suma_asm())
            codigo.configure(state="disabled")

        recargar_codigo()
        btn_recargar.configure(command=recargar_codigo)

        entry_a.bind("<Return>", lambda e: sumar())
        entry_b.bind("<Return>", lambda e: sumar())
        win.after(120, entry_a.focus_set)

        # Referencias para pruebas de humo y para depuración.
        win.btn_sumar = btn_sumar
        win.entry_a = entry_a
        win.entry_b = entry_b
        win.error_label = error
        win.result_label = result
        win.detail_label = detail
        win.sumar = sumar
        return win

    def open_nasm_run(self):
        """Ventana: programa NASM x64 completo, ensamblado, enlazado y ejecutado.

        Un solo botón decide el modo de ejecución según el código del editor:

        * sin ``scanf`` → ejecución INTERACTIVA en esta ventana: la salida
          llega en vivo por pipes y la fila ENTRADA escribe en su stdin;
        * con ``scanf`` → se compila y se lanza ``run.exe`` en una ventana de
          consola real de Windows, donde printf/scanf funcionan al 100%.
        """
        win = ctk.CTkToplevel(self)
        win.title("Programa NASM x64 · ensamblar y ejecutar nativamente")
        win.geometry("780x790")
        win.minsize(700, 640)
        win.configure(fg_color=C["bg"])
        win.transient(self)

        # Cada vez que se abre la ventana se empieza sin proceso.
        win.nasm_proc = None
        win._nasm_compilando = False

        ctk.CTkLabel(win, text="PROGRAMA NASM X64 (ejecutable nativo)",
                     font=(SANS, 15, "bold"), text_color=C["text"]).pack(pady=(14, 2))
        ctk.CTkLabel(win, text="run.asm → nasm → gcc → run.exe · interacción en vivo "
                               "con la consola",
                     font=(SANS, 11), text_color=C["muted"], wraplength=700,
                     justify="center").pack(padx=20)

        def plantilla_demo():
            """Import perezoso: si asm64.runner falta, la GUI igual funciona."""
            try:
                from asm64.runner import PLANTILLA_DEMO
                return PLANTILLA_DEMO
            except Exception as exc:  # módulo ausente, error de sintaxis, etc.
                return f"; ✖ No se pudo cargar asm64.runner: {exc}\n"

        editor = ctk.CTkTextbox(win, fg_color=C["panel"], text_color=C["text"],
                                font=(MONO, 12), wrap="none", border_width=1,
                                border_color=C["line"])
        editor.pack(fill="both", expand=True, padx=20, pady=(12, 6))
        editor.insert("1.0", plantilla_demo())

        acciones = ctk.CTkFrame(win, fg_color="transparent")
        acciones.pack(fill="x", padx=20)
        btn_ejecutar = ctk.CTkButton(acciones, text="⚙ Ensamblar y ejecutar", width=200,
                                     height=34, fg_color=C["accent"],
                                     hover_color=C["line"], text_color=C["text"],
                                     corner_radius=8, font=(SANS, 12, "bold"))
        btn_ejecutar.pack(side="left")
        btn_restaurar = ctk.CTkButton(acciones, text="↺ Restaurar plantilla", width=180,
                                      height=34, fg_color=C["box"],
                                      hover_color=C["line"], text_color=C["text"],
                                      corner_radius=8, font=(SANS, 12, "bold"))
        btn_restaurar.pack(side="left", padx=8)
        btn_detener = ctk.CTkButton(acciones, text="⏹ Detener", width=110,
                                    height=34, fg_color=C["red"],
                                    hover_color=C["line"], text_color=C["text"],
                                    corner_radius=8, font=(SANS, 12, "bold"))
        btn_detener.pack(side="right")

        ctk.CTkLabel(win, text="Un solo botón decide el modo: si tu programa no usa "
                               "'scanf', la salida sale en esta consola; si usa 'scanf' "
                               "(pedir datos) se abre una ventana de consola de Windows "
                               "para responder los datos ahí mismo. Tu programa debe "
                               "definir 'main' (global) y puede usar 'extern printf' y "
                               "'extern scanf' — gcc enlaza la CRT.",
                     font=(SANS, 11), text_color=C["muted"], wraplength=700,
                     justify="left").pack(anchor="w", padx=20, pady=(8, 4))

        ctk.CTkLabel(win, text="SALIDA DEL PROGRAMA", font=(SANS, 11, "bold"),
                     text_color=C["accent"]).pack(anchor="w", padx=20)
        salida = ctk.CTkTextbox(win, height=180, fg_color=C["bg"], text_color=C["text"],
                                font=(MONO, 11), wrap="none", border_width=1,
                                border_color=C["line"])
        salida.pack(fill="both", expand=False, padx=20, pady=(4, 10))
        salida.configure(state="disabled")

        # ------------------------------------------------ fila de ENTRADA
        ctk.CTkLabel(win, text="ENTRADA (stdin del programa)", font=(SANS, 11, "bold"),
                     text_color=C["accent"]).pack(anchor="w", padx=20)
        entrada = ctk.CTkFrame(win, fg_color="transparent")
        entrada.pack(fill="x", padx=20, pady=(4, 16))
        ctk.CTkLabel(entrada, text="›", text_color=C["cyan"],
                     font=(MONO, 16, "bold"), width=14).pack(side="left")
        entry_in = ctk.CTkEntry(
            entrada,
            placeholder_text="▸ Escribe aquí lo que pide tu programa "
                             "(números, opción del menú…) y presiona Enviar",
            border_width=2, border_color=C["line"], font=(MONO, 12))
        entry_in.pack(side="left", fill="x", expand=True, padx=(2, 8))
        btn_enviar = ctk.CTkButton(entrada, text="Enviar ▸", width=120, height=34,
                                   fg_color=C["accent"], hover_color=C["line"],
                                   text_color=C["text"], corner_radius=8,
                                   font=(SANS, 12, "bold"))
        btn_enviar.pack(side="left")

        def _log_salida(texto):
            """Agrega texto a la consola sin borrar lo anterior (hilo de Tk)."""
            try:
                salida.configure(state="normal")
                salida.insert("end", texto)
                salida.see("end")
                salida.configure(state="disabled")
            except tk.TclError:
                pass  # ventana ya cerrada

        def on_salida(texto):
            """Callback del lector: se reenvía SIEMPRE al hilo de Tk."""
            try:
                win.after(0, lambda t=texto: _log_salida(t))
            except (tk.TclError, RuntimeError):
                pass

        def enviar():
            proc = getattr(win, "nasm_proc", None)
            texto = entry_in.get()
            entry_in.delete(0, "end")
            if proc is None or not getattr(proc, "activo", False):
                _log_salida("\n✖ No hay programa en ejecución. Presiona "
                            "\"⚙ Ensamblar y ejecutar\" primero.\n")
                return
            try:
                enviado = proc.enviar_linea(texto)
            except Exception as exc:
                _log_salida(f"\n✖ No se pudo enviar la entrada: {exc}\n")
                return
            if enviado:
                _log_salida(f"› {texto}\n")

        def detener():
            proc = getattr(win, "nasm_proc", None)
            if proc is None or not getattr(proc, "activo", False):
                _log_salida("\n⏹ No hay programa en ejecución.\n")
                return
            try:
                proc.detener()
            except Exception as exc:
                _log_salida(f"\n✖ No se pudo detener el proceso: {exc}\n")
                return
            _log_salida("\n⏹ Deteniendo el proceso...\n")

        def _avisar(texto):
            """Escribe en la consola desde un hilo de trabajo (vía Tk)."""
            try:
                win.after(0, lambda t=texto: _log_salida(t))
            except (tk.TclError, RuntimeError):
                pass

        def _fin_ejecucion(ok, log, usa_scanf):
            """Cierra el estado 'Ensamblando...' y reporta el resultado."""
            win._nasm_compilando = False
            try:
                btn_ejecutar.configure(text="⚙ Ensamblar y ejecutar", state="normal")
            except tk.TclError:
                pass
            _log_salida("\n" + (log or "✖ Sin detalle") + "\n")
            if not ok:
                return
            if usa_scanf:
                _log_salida("\n▶ La ventana de consola ya abrió: escribe los datos "
                            "que pida tu programa ahi.\n")
            else:
                _log_salida("\n▶ Programa iniciado — responde en ENTRADA cuando "
                            "pida datos.\n")
                try:
                    entry_in.focus_set()
                except tk.TclError:
                    pass

        def ejecutar():
            """Un solo botón: elige solo el modo según el código del editor."""
            if getattr(win, "_nasm_compilando", False):
                _log_salida("\n⏳ Ya hay una compilación en curso; espera un momento.\n")
                return
            src = editor.get("1.0", "end-1c")

            # Detener cualquier ejecución interactiva anterior antes de
            # recompilar (en Windows run.exe quedaría bloqueado).
            anterior = getattr(win, "nasm_proc", None)
            if anterior is not None and getattr(anterior, "activo", False):
                try:
                    # Evita que el programa viejo siga escribiendo en la
                    # consola que vamos a limpiar.
                    anterior.on_salida = lambda texto: None
                    anterior.detener()
                except Exception:
                    pass
                viejo = getattr(anterior, "proc", None)
                fin = time.time() + 1.0
                while (viejo is not None and viejo.poll() is None
                       and time.time() < fin):
                    time.sleep(0.02)
            win.nasm_proc = None

            win._nasm_compilando = True
            # El botón se deshabilita mientras compila; se rehabilita al
            # terminar en cualquiera de los dos caminos.
            try:
                btn_ejecutar.configure(text="⏳ Ensamblando...", state="disabled")
            except tk.TclError:
                pass

            # La consola se limpia al COMENZAR (antes de lanzar el hilo).
            try:
                salida.configure(state="normal")
                salida.delete("1.0", "end")
                salida.insert("1.0", "⏳ Ensamblando y enlazando...\n")
                salida.see("end")
                salida.configure(state="disabled")
            except tk.TclError:
                pass

            def worker():
                # Detección de modo: 'scanf' (extern/call, cualquier caja)
                # exige una consola real porque la CRT bufferiza stdout al
                # ser un pipe.
                usa_scanf = "scanf" in src.lower()
                if usa_scanf:
                    _avisar("\n[modo] ✦ Tu programa usa scanf → se abrira una "
                            "VENTANA DE CONSOLA DE WINDOWS (interactua ahi; "
                            "printf/scanf/pause funcionan al 100%).\n")
                else:
                    _avisar("\n[modo] ✦ Tu programa no usa scanf → saldrá en esta "
                            "consola (usa ENTRADA abajo si hiciera falta responder "
                            "algo).\n")

                try:
                    # Import perezoso: si asm64.runner falta, la GUI sigue viva.
                    from asm64.runner import (PLANTILLA_DEMO, NasmProceso,
                                              lanzar_consola)
                    _ = PLANTILLA_DEMO  # se importa junto al resto (misma carga)
                except Exception as exc:
                    aviso = f"✖ No se pudo importar asm64.runner:\n{exc}"
                    try:
                        win.after(0, lambda a=aviso: _fin_ejecucion(
                            False, a, usa_scanf))
                    except (tk.TclError, RuntimeError):
                        pass
                    return

                if usa_scanf:
                    # Sin pipes: la interacción ocurre en la ventana de cmd.
                    try:
                        ok, log = lanzar_consola(src)
                    except Exception as exc:
                        ok, log = False, f"✖ Error inesperado al compilar: {exc}"
                    win.nasm_proc = None
                    try:
                        win.after(0, lambda: _fin_ejecucion(ok, log, True))
                    except (tk.TclError, RuntimeError):
                        pass
                    return

                # Modo interactivo de siempre: salida en vivo por pipes.
                proceso = NasmProceso(on_salida=on_salida)
                win.nasm_proc = proceso
                ok, log = proceso.iniciar(src)
                try:
                    win.after(0, lambda: _fin_ejecucion(ok, log, False))
                except (tk.TclError, RuntimeError):
                    pass

            threading.Thread(target=worker, daemon=True).start()

        def restaurar():
            editor.delete("1.0", "end")
            editor.insert("1.0", plantilla_demo())

        def cerrar_ventana():
            """Al cerrar: detener el proceso y destruir la ventana."""
            try:
                proc = getattr(win, "nasm_proc", None)
                if proc is not None:
                    proc.detener()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        btn_ejecutar.configure(command=ejecutar)
        btn_restaurar.configure(command=restaurar)
        btn_enviar.configure(command=enviar)
        btn_detener.configure(command=detener)
        entry_in.bind("<Return>", lambda e: enviar())
        win.protocol("WM_DELETE_WINDOW", cerrar_ventana)

        # Referencias para pruebas de humo y para depuración.
        win.editor = editor
        win.btn_ejecutar = btn_ejecutar
        win.btn_restaurar = btn_restaurar
        win.salida = salida
        win.ejecutar = ejecutar
        win.restaurar = restaurar
        win.entry_in = entry_in
        win.btn_enviar = btn_enviar
        win.btn_detener = btn_detener
        win.enviar = enviar
        win.detener = detener
        return win

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

        # --- Console section with enhanced labels ---
        ctk.CTkLabel(left, text="CONSOLA  (haz clic y escribe; Enter envía)", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(12, 2))
        self.console = ctk.CTkTextbox(left, width=290, height=110, fg_color=C["bg"],
                                      font=(MONO, 12), border_width=1, border_color=C["line"])
        self.console.pack(fill="x", padx=10)
        self.console.tag_config("out", foreground=C["green"])
        self.console.tag_config("out_label", foreground=C["green"])
        self.console.tag_config("in", foreground=C["cyan"])
        self.console.tag_config("wait", foreground=C["orange"])
        self.console.tag_config("step_num", foreground=C["muted"])
        self.console.configure(state="disabled")
        # lo que se teclee sobre la consola se redirige a la línea de entrada
        self.console.bind("<Key>", self._console_key)
        self.console.bind("<Button-1>", lambda e: self.after(1, self.entry.focus_set))
        row3 = ctk.CTkFrame(left, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=(6, 12))
        self._input_prompt = ctk.CTkLabel(row3, text="›", text_color=C["cyan"],
                                          font=(MONO, 16, "bold"), width=14)
        self._input_prompt.pack(side="left")
        self.entry = ctk.CTkEntry(row3, placeholder_text="número + Enter", width=190,
                                  border_width=2, border_color=C["line"])
        self.entry.pack(side="left", padx=(2, 0))
        self.entry.bind("<Return>", self.submit_input)
        self._btn(row3, "Enviar", self.submit_input, width=70).pack(side="left", padx=6)

        # --- columna central: arquitectura + explanation + bitácora
        mid = ctk.CTkFrame(tab, fg_color=C["panel"], corner_radius=10)
        mid.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        ctk.CTkLabel(mid, text="ARQUITECTURA  (flechas = flujo de datos · clic en un componente = explicación)",
                     text_color=C["muted"], font=(SANS, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        self.arch = ArchView(mid, self.show_component)
        self.arch.canvas.pack(padx=10, pady=4)

        # --- Instruction counter widget ---
        instr_frame = ctk.CTkFrame(mid, fg_color=C["bg"], corner_radius=6)
        instr_frame.pack(fill="x", padx=10, pady=(2, 4))
        self._instr_counter = ctk.CTkLabel(
            instr_frame, text="Instrucciones ejecutadas: 0",
            text_color=C["text"], font=(MONO, 11, "bold"), anchor="w")
        self._instr_counter.pack(side="left", padx=8, pady=4)
        self._instr_current = ctk.CTkLabel(
            instr_frame, text="",
            text_color=C["orange"], font=(MONO, 11), anchor="w")
        self._instr_current.pack(side="left", padx=(12, 4), pady=4)
        self._instr_coverage = ctk.CTkLabel(
            instr_frame, text="",
            text_color=C["green"], font=(SANS, 10), anchor="e")
        self._instr_coverage.pack(side="right", padx=8, pady=4)

        # --- Execution progress strip ---
        progress_frame = ctk.CTkFrame(mid, fg_color=C["bg"], corner_radius=6)
        progress_frame.pack(fill="x", padx=10, pady=(0, 4))
        self._progress_title = ctk.CTkLabel(
            progress_frame, text="AVANCE DEL CICLO",
            text_color=C["muted"], font=(SANS, 9, "bold"), anchor="w")
        self._progress_title.pack(side="left", padx=(8, 6), pady=4)
        self._progress_phases = ctk.CTkLabel(
            progress_frame, text="FETCH",
            text_color=C["accent"], font=(MONO, 10, "bold"), anchor="w")
        self._progress_phases.pack(side="left", padx=4, pady=4)
        self._progress_detail = ctk.CTkLabel(
            progress_frame, text="Paso 0 · ciclo 0",
            text_color=C["muted"], font=(MONO, 9), anchor="e")
        self._progress_detail.pack(side="right", padx=8, pady=4)

        # --- Enhanced explanation panel ---
        explain_frame = ctk.CTkFrame(mid, fg_color=C["bg"], corner_radius=8,
                                     border_width=2, border_color=C["cyan"])
        explain_frame.pack(fill="x", padx=10, pady=(2, 4))
        self.note_title = ctk.CTkLabel(explain_frame, text="",
                                       text_color="#0e1320", font=(SANS, 13, "bold"),
                                       anchor="w", fg_color=C["cyan"], corner_radius=4)
        self.note_title.pack(fill="x", padx=4, pady=(4, 0))
        self.note_box = ctk.CTkTextbox(explain_frame, height=84, fg_color=C["bg"],
                                       text_color=C["text"],
                                       font=(SANS, 13), wrap="word", border_width=0)
        self.note_box.pack(fill="x", padx=6, pady=(2, 6))
        self.note_box.tag_config("what", foreground=C["cyan"])
        self.note_box.tag_config("next_h", foreground=C["orange"])
        self.note_box.tag_config("val", foreground=C["green"])
        self.note_box.configure(state="disabled")

        # --- Enhanced micro-operations log ---
        ctk.CTkLabel(mid, text="BITÁCORA DE MICRO-OPERACIONES", text_color=C["muted"],
                     font=(SANS, 10, "bold")).pack(anchor="w", padx=12)
        self.log = ctk.CTkTextbox(mid, height=110, fg_color=C["bg"], font=(MONO, 11),
                                  border_width=1, border_color=C["line"])
        self.log.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        # Base tags
        for tag, color in (("head", C["accent"]), ("err", C["red"]), ("ok", C["green"]),
                           ("dim", C["muted"])):
            self.log.tag_config(tag, foreground=color)
        # Event category tags
        for cat_info in _EVENT_CATEGORIES.values():
            self.log.tag_config(cat_info["tag"], foreground=cat_info["color"])
        # Separator tag
        self.log.tag_config("separator", foreground=C["line"])
        self.log.tag_config("cycle_head", foreground=C["accent"])
        self.log.tag_config("phase_head", foreground=C["purple"])
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

    def _log_cycle_separator(self, cycle_num):
        """Add a visual separator for a new instruction cycle."""
        sep = f"{'─' * 40}\n"
        self._append(self.log, sep, "separator")
        self._append(self.log, f"  ● CICLO #{cycle_num}\n", "cycle_head")

    def _log_phase_header(self, phase_name):
        """Add a phase header with indentation."""
        icon = {"FETCH": "📥", "DECODE": "🔍", "EXECUTE": "⚙️"}.get(phase_name, "▸")
        self._append(self.log, f"  {icon} {phase_name}\n", "phase_head")

    def _log_event(self, event):
        """Log a single event with color-coding and icon."""
        cat = _classify_event(event)
        info = _EVENT_CATEGORIES.get(cat, _EVENT_CATEGORIES["control"])
        self._append(self.log, f"      {info['prefix']} {event.text}\n", info["tag"])

    def _set_status(self, text, color=None):
        self.status_right.configure(text=text, text_color=color or C["muted"])

    def _clear_console(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        self.out_shown = 0
        self.wait_shown = False
        self._step_number = 0

    # ================================================== cargar / ensamblar
    def load_example(self, name):
        if name == self.special:
            self.start_custom_asm()
            return
        self._set_editor(self._read(os.path.join(PROG_DIR, name)))
        self.assemble_current()

    def start_custom_asm(self):
        """Carga la plantilla editable y la deja ensamblada, lista para F5."""
        self._stop_run()
        self._set_editor(CUSTOM_TEMPLATE)
        self.editor.tag_remove("err", "1.0", "end")

        # Estado limpio: nada de la ejecución anterior debe sobrevivir.
        self.program, self.source = None, None
        self.visited, self.last_phase = set(), None
        self.last_transition = "—"
        self.cpu.input_queue.clear()
        self._clear_console()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        # Ensambla la plantilla de inmediato (queda lista para ejecutar).
        self.assemble_current()

        try:
            self.editor.focus_set()
        except (AttributeError, tk.TclError):
            pass
        self._log("✎ Modo CREAR PROPIO ASM: plantilla cargada; edita el código y presiona F5.")
        self._set_status(
            "✎ Modo propio: escribe tu asm y presiona F5 — se ensambla y ejecuta solo",
            C["cyan"])

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
        self._log_cycle_num = 0
        self._log_last_phase = None
        self._phase_history = []
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
        self._stop_input_flash()
        if self.program is None:
            return
        self.cpu.input_queue.clear()
        self.cpu.load(self.program.words)
        self.visited, self.alu_last = set(), "—"
        self._clear_console()
        self.last_transition = "—"
        self.last_phase = None
        self._log_cycle_num = 0
        self._log_last_phase = None
        self._phase_history = []
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
        if mode == "phase":
            transition = f"{prev} → {cpu.phase}"
        else:
            transition = "FETCH → DECODE → EXECUTE"
            if cpu.waiting_input:
                transition += " (INPUT)"
            elif cpu.halted and cpu.error:
                transition += " (ERROR)"
        self._phase_history.append(transition)
        self._phase_history = self._phase_history[-4:]
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
            self._step_number += 1
            if mode == "phase":
                # Add cycle separator when starting a new FETCH
                if prev == "FETCH":
                    self._log_cycle_num += 1
                    self._log_cycle_separator(self._log_cycle_num)
                self._log_phase_header(prev)
                for e in events:
                    self._log_event(e)
            else:
                self._log_cycle_num += 1
                self._log_cycle_separator(self._log_cycle_num)
                self._append(self.log,
                             f"  ⚙️ Instrucción [{cpu.cur_addr:02d}]: {disassemble(cpu.ir)}\n",
                             "phase_head")
                for e in events:
                    self._log_event(e)

        # Console output with step numbers
        while self.out_shown < len(cpu.output):
            val = cpu.output[self.out_shown]
            self._append(self.console, f"[paso {self._step_number}] ", "step_num")
            self._append(self.console, "OUTPUT: ", "out_label")
            self._append(self.console, f"{val}\n", "out")
            self.out_shown += 1

        if cpu.waiting_input:
            if not self.wait_shown:
                self._append(self.console,
                             f"[paso {self._step_number}] ⏳ INPUT: escribe un número ↓\n", "wait")
                self.wait_shown = True
                self._start_input_flash()
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

    # --- Input prompt flashing ---
    def _start_input_flash(self):
        """Flash the input prompt border to draw attention."""
        self._stop_input_flash()
        self._input_flash_state = True
        self._do_input_flash()

    def _do_input_flash(self):
        """Toggle input prompt border color."""
        if not self.cpu.waiting_input:
            self._stop_input_flash()
            return
        self._input_flash_state = not self._input_flash_state
        color = C["orange"] if self._input_flash_state else C["cyan"]
        self.entry.configure(border_color=color)
        self._input_prompt.configure(text_color=color)
        self._input_flash_id = self.after(500, self._do_input_flash)

    def _stop_input_flash(self):
        """Stop flashing the input prompt."""
        if self._input_flash_id:
            try:
                self.after_cancel(self._input_flash_id)
            except (ValueError, tk.TclError):
                pass
            self._input_flash_id = None
        self.entry.configure(border_color=C["line"])
        self._input_prompt.configure(text_color=C["cyan"])

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
        self._stop_input_flash()
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
        """Enhanced explanation panel with 'what happened' / 'what's next' sections."""
        # Title with contrasting background
        display_title = f"  {title}  "
        self.note_title.configure(text=display_title)

        self.note_box.configure(state="normal")
        self.note_box.delete("1.0", "end")

        # Split text into main explanation and "Sigue:" part
        parts = text.split("Sigue:")
        main_text = parts[0].strip()
        next_text = parts[1].strip() if len(parts) > 1 else None

        # Highlight values in the text (numbers in specific patterns)
        self.note_box.insert("end", main_text + "\n")

        if next_text:
            self.note_box.insert("end", "\n")
            self.note_box.insert("end", "▸ Siguiente: ", "next_h")
            self.note_box.insert("end", next_text + "\n")

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

        # Instruction counter and current instruction
        self._instr_counter.configure(
            text=f"Instrucciones ejecutadas: {cpu.instructions_done}")
        if cpu.mnemonic and not cpu.halted:
            self._instr_current.configure(
                text=f"▸ [{cpu.cur_addr:02d}] {disassemble(cpu.ir)}")
        elif cpu.halted:
            self._instr_current.configure(text="■ HALT")
        else:
            self._instr_current.configure(text="")
        # Coverage info
        if self.visited:
            self._instr_coverage.configure(
                text=f"Dirs. visitadas: {len(self.visited)}")
        else:
            self._instr_coverage.configure(text="")
        self._progress_phases.configure(
            text="  •  ".join(self._phase_history) if self._phase_history else cpu.phase,
            text_color=C["red"] if cpu.halted else C["accent"])
        self._progress_detail.configure(
            text=f"Paso {self._step_number} · ciclo {self._log_cycle_num}")

        self.status_left.configure(
            text=f"Fase: {cpu.phase:<8} PC={cpu.pc:<3} AC={cpu.ac:<6} IR={cpu.ir:<6} "
                 f"Instrucciones: {cpu.instructions_done}")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

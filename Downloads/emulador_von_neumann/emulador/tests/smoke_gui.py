"""Prueba de humo de la GUI sin pantalla: sustituye tkinter/customtkinter por
objetos falsos y ejecuta la lógica real de la aplicación."""
import os, sys, types
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Dummy:
    calls = 0
    def __init__(self, *a, **k): pass
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        Dummy.calls += 1
        return MagicMock()

tk = types.ModuleType("tkinter")
tk.Canvas = Dummy; tk.LAST = "last"; tk.END = "end"; tk.TclError = Exception
tk.filedialog = types.ModuleType("tkinter.filedialog")
ctk = types.ModuleType("customtkinter")
for n in ("CTkFrame","CTkButton","CTkLabel","CTkTextbox","CTkEntry","CTkSlider",
          "CTkOptionMenu","CTkTabview","CTkScrollbar"):
    setattr(ctk, n, Dummy)
ctk.CTk = Dummy
ctk.set_appearance_mode = lambda m: None
sys.modules.update({"tkinter": tk, "tkinter.filedialog": tk.filedialog, "customtkinter": ctk})

from gui import app as appmod

class FakeText:
    def __init__(self): self.text = ""; self.tags = {}
    def get(self, a, b=None): return self.text
    def delete(self, a, b=None): self.text = ""
    def insert(self, idx, t, tag=None): self.text += t
    def tag_add(self, tag, a, b): self.tags.setdefault(tag, []).append((a, b))
    def tag_remove(self, tag, a, b): self.tags.pop(tag, None)
    def tag_config(self, *a, **k): pass
    def see(self, *a): pass
    def configure(self, **k): pass
class FakeSlider:
    def __init__(self, v): self.v = v
    def get(self): return self.v
    def set(self, v): self.v = v

def make_app(speed=10):
    app = appmod.App()
    app.editor = FakeText(); app.speed = FakeSlider(speed)
    app.after = lambda ms, fn: None
    app.after_cancel = lambda i: None
    return app

def load(app, name):
    app.editor.text = open(os.path.join(appmod.PROG_DIR, name), encoding="utf-8").read()
    assert app.assemble_current(), "no ensambló " + name

# 1) paso a paso: 3 fases por instrucción, con entrada
app = make_app()
load(app, "01_suma.asm")
app.step_phase(); app.step_phase(); app.step_phase()
assert app.cpu.waiting_input, "debería esperar entrada"
app.entry = MagicMock(); app.entry.get.return_value = "7"
app.submit_input()
app.entry.get.return_value = "5"; app.cpu.provide_input(5)
for _ in range(60):
    if app.cpu.halted: break
    app.step_instruction()
    if app.cpu.waiting_input: app.cpu.provide_input(5)
print("suma paso a paso ->", app.cpu.output, "halted:", app.cpu.halted)

# 2) ejecución automática con entradas pre-encoladas, en 3 velocidades
for speed in (2, 7, 10):
    app = make_app(speed)
    load(app, "02_cuenta_regresiva.asm")
    app.cpu.provide_input(4)
    app.toggle_run()
    guard = 0
    while app.running and guard < 5000:      # simula el bucle de after()
        app._tick(); guard += 1
    print(f"cuenta regresiva velocidad {speed} ->", app.cpu.output, "| cobertura:",
          len(app.visited), "nodos")
    assert app.cpu.output == [4, 3, 2, 1]

# 3) pausa por INPUT y reanudación automática
app = make_app(10)
load(app, "04_multiplicacion.asm")
app.toggle_run()
assert app.cpu.waiting_input and app.resume_after_input
app.entry = MagicMock(); app.entry.get.return_value = "6"; app.submit_input()
app.entry.get.return_value = "7"
while app.running: app._tick()
assert app.cpu.waiting_input
app.submit_input()
while app.running: app._tick()
print("multiplicación con pausas de INPUT ->", app.cpu.output)
assert app.cpu.output == [42]

# 4) reiniciar y reejecutar
app.reset_program(); assert app.cpu.pc == 0 and app.cpu.output == []

# 5) errores de ensamblado
app = make_app()
app.editor.text = open(os.path.join(appmod.PROG_DIR, "99_error_demo.asm"), encoding="utf-8").read()
assert app.assemble_current() is False
print("líneas marcadas con error:", len(app.editor.tags.get("err", [])))
# 5b) teclear sobre la consola, atajos intactos y clic en componentes
from types import SimpleNamespace as NS
from gui import views
app = make_app(); load(app, "01_suma.asm")
app.entry = MagicMock(); app.entry.get.return_value = ""
assert app._console_key(NS(state=0, keysym="7", char="7")) == "break"
app.entry.insert.assert_called_with("end", "7")
assert app._console_key(NS(state=0, keysym="F5", char="")) is None, "F5 debe seguir funcionando"
assert app._console_key(NS(state=4, keysym="c", char="\x03")) is None, "Ctrl+C debe seguir funcionando"
app.entry.get.return_value = "9"
assert app._console_key(NS(state=0, keysym="Return", char="\r")) == "break"
assert app.cpu.input_queue and app.cpu.input_queue[-1] == 9, "Enter en la consola envía la entrada"
notes_seen = []
app._set_note = lambda t, x: notes_seen.append((t, x))
x1, y1, x2, y2 = views.BOXES["PC"]
hit = app.arch._click(NS(x=(x1 + x2) / 2 * views.S, y=(y1 + y2) / 2 * views.S))
assert hit == "PC" and notes_seen[-1][0].startswith("PC"), notes_seen
for name in list(views.BOXES) + list(views.PHASE_PILLS):
    x1, y1, x2, y2 = (views.BOXES | views.PHASE_PILLS)[name]
    assert app.arch._click(NS(x=(x1 + x2) / 2 * views.S, y=(y1 + y2) / 2 * views.S)) == name
    assert name in appmod.notes.COMPONENTS, "falta nota para " + name
assert app.arch._click(NS(x=1, y=1)) is None
print("consola, atajos y clic en componentes: OK")

# 6) todos los ejemplos ensamblan y renderizan
for f in sorted(os.listdir(appmod.PROG_DIR)):
    if f.startswith("99"): continue
    a = make_app(); load(a, f); a.step_phase()
print("OK: GUI lógica sin errores; llamadas a widgets simulados:", Dummy.calls)

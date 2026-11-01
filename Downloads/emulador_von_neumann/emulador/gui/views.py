"""Vistas dibujadas con tk.Canvas: arquitectura, memoria, autómata y grafo."""
import tkinter as tk

from core.isa import MEM_SIZE, disassemble
from formal.cfg import build_cfg

C = dict(
    bg="#0e1320", panel="#161d2e", box="#1e2840", line="#3a4a6b",
    text="#e8edf7", muted="#8a96b0", accent="#4f9dff", green="#3ddc97",
    orange="#ffb454", red="#ff6b6b", purple="#b48cff", cyan="#4fd8e8",
    code="#1c3556", data="#1d3b33",
)
MONO = "Courier"
SANS = "Helvetica"


# ======================================================================
#  Diagrama de la arquitectura
# ======================================================================
S = 0.68            # factor de escala; permite ver el diagrama completo en ventanas estrechas

BOXES = {                       # coordenadas base (x1, y1, x2, y2)
    "MAR": (175, 60, 275, 104),  "PC":  (310, 60, 410, 104),
    "MDR": (175, 180, 275, 224), "IR":  (310, 180, 410, 224),
    "CU":  (445, 180, 545, 224),
    "AC":  (175, 320, 275, 364), "ALU": (310, 320, 410, 364),
    "MEM": (15, 110, 125, 290),
    "IN":  (15, 310, 125, 350),  "OUT": (15, 370, 125, 410),
}
TITLES = {"MAR": "MAR", "PC": "PC  (contador)", "MDR": "MDR", "IR": "IR  (instrucción)",
          "CU": "UNIDAD DE CONTROL", "AC": "AC  (acumulador)", "ALU": "ALU",
          "MEM": "MEMORIA", "IN": "ENTRADA", "OUT": "SALIDA"}
LINKS = [("PC", "MAR"), ("IR", "PC"), ("IR", "MAR"), ("IR", "CU"), ("MDR", "IR"),
         ("MEM", "MDR"), ("MAR", "MEM"), ("MDR", "ALU"), ("MDR", "AC"),
         ("AC", "ALU"), ("IN", "AC"), ("AC", "OUT")]
PHASE_PILLS = {"FETCH": (575, 50, 695, 88), "DECODE": (575, 100, 695, 138),
               "EXECUTE": (575, 150, 695, 188), "HALT": (575, 200, 695, 238)}


class ArchView:
    def __init__(self, parent, on_click=None):
        self.canvas = tk.Canvas(parent, width=int(710 * S), height=int(445 * S),
                                bg=C["panel"], highlightthickness=0)
        self.on_click = on_click
        self.rect, self.value, self.pills = {}, {}, {}
        self.hl = []
        self._draw_static()
        self.canvas.bind("<Button-1>", self._click)

    def _click(self, e):
        """Devuelve el nombre del componente bajo el cursor (cajas y fases)."""
        x, y = e.x / S, e.y / S
        for name, (x1, y1, x2, y2) in list(BOXES.items()) + list(PHASE_PILLS.items()):
            if x1 <= x <= x2 and y1 <= y <= y2:
                if self.on_click:
                    self.on_click(name)
                return name
        return None

    @staticmethod
    def _s(*v):
        return [x * S for x in v]

    def _center(self, n):
        x1, y1, x2, y2 = BOXES[n]
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def _clip(self, n, toward):
        x1, y1, x2, y2 = BOXES[n]
        cx, cy = self._center(n)
        dx, dy = toward[0] - cx, toward[1] - cy
        hw, hh = (x2 - x1) / 2 + 3, (y2 - y1) / 2 + 3
        tx = hw / abs(dx) if dx else float("inf")
        ty = hh / abs(dy) if dy else float("inf")
        t = min(tx, ty)
        return (cx + dx * t, cy + dy * t)

    def _edge(self, a, b):
        return self._clip(a, self._center(b)), self._clip(b, self._center(a))

    def _draw_static(self):
        cv = self.canvas
        cv.create_rectangle(*self._s(150, 20, 560, 430), outline=C["line"], width=2, dash=(5, 4))
        cv.create_text(*self._s(165, 32), text="CPU", anchor="w", fill=C["muted"],
                       font=(SANS, 10, "bold"))
        for a, b in LINKS:
            p1, p2 = self._edge(a, b)
            cv.create_line(*self._s(p1[0], p1[1], p2[0], p2[1]), fill=C["line"], width=2, dash=(3, 3))
        for name, (x1, y1, x2, y2) in BOXES.items():
            self.rect[name] = cv.create_rectangle(*self._s(x1, y1, x2, y2), fill=C["box"],
                                                  outline=C["line"], width=2)
            cv.create_text(*self._s(x1 + 7, y1 + 11), text=TITLES[name], anchor="w",
                           fill=C["muted"], font=(SANS, 7, "bold"))
            vy = (y1 + y2) / 2 + (6 if name != "MEM" else 0)
            self.value[name] = cv.create_text(*self._s((x1 + x2) / 2, vy), text="0",
                                              fill=C["text"], font=(MONO, 11, "bold"))
        self.flags = cv.create_text(*self._s(360, 396), text="Z = 1    N = 0",
                                    fill=C["muted"], font=(MONO, 9))
        for name, (x1, y1, x2, y2) in PHASE_PILLS.items():
            r = cv.create_rectangle(*self._s(x1, y1, x2, y2), fill=C["box"], outline=C["line"], width=2)
            label = {"FETCH": "1 · FETCH", "DECODE": "2 · DECODE",
                     "EXECUTE": "3 · EXECUTE", "HALT": "HALT"}[name]
            t = cv.create_text(*self._s((x1 + x2) / 2, (y1 + y2) / 2), text=label,
                               fill=C["muted"], font=(SANS, 9, "bold"))
            self.pills[name] = (r, t)
        cv.create_text(*self._s(575, 38), text="FASE DEL CICLO", anchor="w",
                       fill=C["muted"], font=(SANS, 7, "bold"))
        self.info = cv.create_text(*self._s(575, 262), anchor="nw", width=int(125 * S),
                                   text="", fill=C["text"], font=(SANS, 9))

    # ------------------------------------------------------------------
    def update(self, cpu, events, alu_last, in_queue):
        cv = self.canvas
        for item in self.hl:
            cv.delete(item)
        self.hl = []

        values = {"PC": cpu.pc, "MAR": cpu.mar, "MDR": cpu.mdr, "IR": cpu.ir, "AC": cpu.ac,
                  "CU": cpu.mnemonic or "—", "ALU": alu_last,
                  "MEM": f"M[{cpu.mar}]\n= {cpu.mem[cpu.mar]}",
                  "IN": f"cola: {in_queue}" if in_queue else "—",
                  "OUT": str(cpu.output[-1]) if cpu.output else "—"}
        active = {e.dst for e in events}
        for name, val in values.items():
            on = name in active
            cv.itemconfig(self.value[name], text=str(val), fill=C["green"] if on else C["text"])
            cv.itemconfig(self.rect[name], outline=C["orange"] if on else C["line"],
                          width=3 if on else 2)

        for e in events:
            if e.src == e.dst:
                continue
            p1, p2 = self._edge(e.src, e.dst)
            self.hl.append(cv.create_line(*self._s(p1[0], p1[1], p2[0], p2[1]), arrow=tk.LAST, width=3, fill=C["accent"],
                                          arrowshape=(10, 12, 5)))

        cv.itemconfig(self.flags, text=f"Z = {int(cpu.zero)}    N = {int(cpu.negative)}")
        for name, (r, t) in self.pills.items():
            on = name == cpu.phase
            color = C["red"] if (on and name == "HALT") else C["accent"]
            cv.itemconfig(r, fill=color if on else C["box"], outline=color if on else C["line"])
            cv.itemconfig(t, fill="#ffffff" if on else C["muted"])

        if cpu.error:
            cv.itemconfig(self.info, text="Error:\n" + cpu.error, fill=C["red"])
        else:
            from core.isa import DESCRIPTIONS
            desc = DESCRIPTIONS.get(cpu.mnemonic, "") if cpu.phase in ("EXECUTE", "FETCH") and cpu.mnemonic else ""
            head = f"Instrucción\n{disassemble(cpu.ir)}" if cpu.mnemonic else "Sin instrucción"
            cv.itemconfig(self.info, text=f"{head}\n{desc}", fill=C["text"])


# ======================================================================
#  Cuadrícula de memoria 10 × 10
# ======================================================================
CELL_W, CELL_H, HDR = 42, 32, 22


class MemView:
    def __init__(self, parent, on_click):
        self.on_click = on_click
        w, h = HDR + 10 * CELL_W, HDR + 10 * CELL_H
        self.canvas = tk.Canvas(parent, width=w, height=h, bg=C["panel"], highlightthickness=0)
        cv = self.canvas
        for c in range(10):
            cv.create_text(HDR + c * CELL_W + CELL_W / 2, HDR / 2, text=str(c),
                           fill=C["muted"], font=(MONO, 9))
        for r in range(10):
            cv.create_text(HDR / 2, HDR + r * CELL_H + CELL_H / 2, text=str(r * 10),
                           fill=C["muted"], font=(MONO, 9))
        self.rect, self.val, self.sub = [], [], []
        for a in range(MEM_SIZE):
            r, c = divmod(a, 10)
            x1, y1 = HDR + c * CELL_W + 1, HDR + r * CELL_H + 1
            self.rect.append(cv.create_rectangle(x1, y1, x1 + CELL_W - 2, y1 + CELL_H - 2,
                                                 fill=C["box"], outline=C["line"]))
            self.val.append(cv.create_text(x1 + (CELL_W - 2) / 2, y1 + 10, text="0",
                                           fill=C["muted"], font=(MONO, 10, "bold")))
            self.sub.append(cv.create_text(x1 + (CELL_W - 2) / 2, y1 + 23, text="",
                                           fill=C["muted"], font=(MONO, 7)))
        cv.bind("<Button-1>", self._click)

    def _click(self, e):
        c, r = (e.x - HDR) // CELL_W, (e.y - HDR) // CELL_H
        if 0 <= c < 10 and 0 <= r < 10:
            self.on_click(r * 10 + c)

    def update(self, cpu, program):
        cv = self.canvas
        for a in range(MEM_SIZE):
            kind = program.kinds.get(a) if program else None
            word = cpu.mem[a]
            used = kind is not None or word != 0
            fill = {"code": C["code"], "data": C["data"]}.get(kind, C["box"])
            outline, width = C["line"], 1
            if a == cpu.last_mem_write:
                outline, width = C["orange"], 3
            elif a == cpu.pc and not cpu.halted:
                outline, width = C["cyan"], 3
            elif a == cpu.mar:
                outline, width = C["purple"], 2
            cv.itemconfig(self.rect[a], fill=fill, outline=outline, width=width)
            cv.itemconfig(self.val[a], text=str(word), fill=C["text"] if used else C["muted"])
            sub = disassemble(word) if kind == "code" else ("dato" if kind == "data" else "")
            cv.itemconfig(self.sub[a], text=sub, fill=C["accent"] if kind == "code" else C["green"])


# ======================================================================
#  Autómata finito (Q, Σ, δ, q0, F)
# ======================================================================
NODES = {"FETCH": (90, 150), "DECODE": (260, 150), "EXECUTE": (430, 150), "HALT": (430, 300)}
R = 34


class AutomatonView:
    def __init__(self, parent):
        self.canvas = tk.Canvas(parent, width=520, height=350, bg=C["panel"], highlightthickness=0)
        cv = self.canvas
        self.circle = {}
        font = (SANS, 9)
        # aristas
        cv.create_line(20, 150, 54, 150, arrow=tk.LAST, fill=C["muted"], width=2)
        cv.create_text(22, 132, text="q0", fill=C["muted"], font=font)
        cv.create_line(124, 150, 226, 150, arrow=tk.LAST, fill=C["muted"], width=2)
        cv.create_text(175, 134, text="ε  (IR ← M[PC])", fill=C["muted"], font=font)
        cv.create_line(294, 150, 396, 150, arrow=tk.LAST, fill=C["muted"], width=2)
        cv.create_text(345, 134, text="opcode válido", fill=C["muted"], font=font)
        cv.create_line(415, 120, 395, 60, 125, 60, 105, 118, smooth=True, arrow=tk.LAST,
                       fill=C["muted"], width=2)
        cv.create_text(260, 48, text="i ∈ I \\ {HALT}", fill=C["muted"], font=font)
        cv.create_line(430, 184, 430, 264, arrow=tk.LAST, fill=C["muted"], width=2)
        cv.create_text(440, 224, text="i = HALT", anchor="w", fill=C["muted"], font=font)
        cv.create_line(280, 182, 402, 282, arrow=tk.LAST, fill=C["muted"], width=2)
        cv.create_text(300, 250, text="opcode inválido", anchor="w", fill=C["muted"], font=font)
        # nodos
        for name, (x, y) in NODES.items():
            if name == "HALT":
                cv.create_oval(x - R - 5, y - R - 5, x + R + 5, y + R + 5, outline=C["muted"], width=2)
            self.circle[name] = cv.create_oval(x - R, y - R, x + R, y + R, fill=C["box"],
                                               outline=C["line"], width=2)
            cv.create_text(x, y, text=name, fill=C["text"], font=(SANS, 9, "bold"))

    def update(self, phase):
        for name, item in self.circle.items():
            on = name == phase
            color = C["red"] if (on and name == "HALT") else C["accent"]
            self.canvas.itemconfig(item, fill=color if on else C["box"],
                                   outline=color if on else C["line"])


# ======================================================================
#  Grafo de flujo de control
# ======================================================================
NODE_W, NODE_H, GAP, X0 = 180, 28, 46, 40


class CFGView:
    def __init__(self, parent, height=420):
        self.frame = parent
        self.canvas = tk.Canvas(parent, width=330, height=height, bg=C["panel"], highlightthickness=0)
        self.nodes = {}
        self.code = []

    def draw(self, program):
        cv = self.canvas
        cv.delete("all")
        self.nodes = {}
        self.code, edges = build_cfg(program)
        index = {a: i for i, a in enumerate(self.code)}
        inv = {v: k for k, v in program.labels.items()}
        if not self.code:
            cv.create_text(20, 20, text="Sin instrucciones", anchor="w", fill=C["muted"])
            return
        y = lambda i: 30 + i * GAP
        right, mid = X0 + NODE_W, X0 + NODE_W / 2
        for a, i in index.items():
            op, operand = program.mnemonics[a], program.operands[a]
            arg = ""
            if op not in ("HALT", "INPUT", "OUTPUT", "NOT"):
                arg = " " + inv.get(operand, str(operand))
            self.nodes[a] = cv.create_rectangle(X0, y(i) - NODE_H / 2, right, y(i) + NODE_H / 2,
                                                fill=C["box"], outline=C["line"], width=2)
            cv.create_text(X0 + 10, y(i), text=f"{a:02d}   {op}{arg}", anchor="w",
                           fill=C["text"], font=(MONO, 10, "bold"))
        for a, b, kind in edges:
            if b not in index:
                continue
            i, j = index[a], index[b]
            if kind in ("seq", "false") and j == i + 1:
                cv.create_line(mid, y(i) + NODE_H / 2, mid, y(j) - NODE_H / 2, arrow=tk.LAST,
                               fill=C["muted"], width=2)
                if kind == "false":
                    cv.create_text(mid + 8, y(i) + NODE_H / 2 + 8, text="F", anchor="w",
                                   fill=C["red"], font=(SANS, 8, "bold"))
            else:
                ax = right + 20 + min(70, 8 * abs(i - j))
                color = C["green"] if kind == "true" else C["orange"]
                cv.create_line(right, y(i), ax, y(i), ax, y(j), right, y(j), smooth=True,
                               arrow=tk.LAST, fill=color, width=2)
                if kind == "true":
                    cv.create_text(right + 6, y(i) - 9, text="V", anchor="w",
                                   fill=C["green"], font=(SANS, 8, "bold"))
        cv.configure(scrollregion=(0, 0, 330, 30 + len(self.code) * GAP))

    def update(self, cpu, visited):
        cur = cpu.cur_addr if (cpu.phase in ("DECODE", "EXECUTE") or cpu.halted) else cpu.pc
        for a, item in self.nodes.items():
            if a == cur:
                self.canvas.itemconfig(item, fill=C["accent"], outline=C["orange"], width=3)
            elif a in visited:
                self.canvas.itemconfig(item, fill=C["data"], outline=C["green"], width=2)
            else:
                self.canvas.itemconfig(item, fill=C["box"], outline=C["line"], width=2)
        done = len(visited & set(self.nodes))
        return done, len(self.nodes)

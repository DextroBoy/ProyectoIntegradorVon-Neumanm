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

# --- Enhanced phase pipeline layout ---
_PIPE_Y0 = 50       # top of pipeline area
_PIPE_H  = 36       # pill height
_PIPE_GAP = 6       # gap between pills
_PIPE_X0 = 570      # left edge
_PIPE_W  = 130      # pill width
_ARROW_W = 16       # arrow connector width

PHASE_PILLS = {}
_py = _PIPE_Y0
for _pname in ("FETCH", "DECODE", "EXECUTE", "HALT"):
    PHASE_PILLS[_pname] = (_PIPE_X0, _py, _PIPE_X0 + _PIPE_W, _py + _PIPE_H)
    _py += _PIPE_H + _PIPE_GAP


class ArchView:
    def __init__(self, parent, on_click=None):
        self.canvas = tk.Canvas(parent, width=int(710 * S), height=int(445 * S),
                                bg=C["panel"], highlightthickness=0)
        self.on_click = on_click
        self.rect, self.value, self.pills = {}, {}, {}
        self.hl = []
        self._glow_items = []      # items for glow/flash effects
        self._anim_after_ids = []  # scheduled after IDs for animations
        self._prev_values = {}     # previous register values for flash detection
        self._cycle_count = 0      # cycle counter
        self._completed_phases = set()  # phases completed in the current cycle
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

        # --- Enhanced pipeline phase pills with arrows ---
        phase_order = ["FETCH", "DECODE", "EXECUTE", "HALT"]
        cv.create_text(*self._s(_PIPE_X0, _PIPE_Y0 - 14), text="FASE DEL CICLO", anchor="w",
                       fill=C["muted"], font=(SANS, 7, "bold"))
        # Draw cycle counter label
        self._cycle_label = cv.create_text(
            *self._s(_PIPE_X0 + _PIPE_W, _PIPE_Y0 - 14), text="", anchor="e",
            fill=C["accent"], font=(SANS, 8, "bold"))

        for idx, name in enumerate(phase_order):
            x1, y1, x2, y2 = PHASE_PILLS[name]

            # Draw connecting arrow between pills (except before first)
            if idx > 0 and idx < 3:  # arrows between FETCH→DECODE, DECODE→EXECUTE
                prev_name = phase_order[idx - 1]
                _, _, _, prev_y2 = PHASE_PILLS[prev_name]
                mid_x = (x1 + x2) / 2
                arr_y1 = prev_y2
                arr_y2 = y1
                self.hl.append(cv.create_line(
                    *self._s(mid_x, arr_y1, mid_x, arr_y2),
                    fill=C["line"], width=2, arrow=tk.LAST, arrowshape=(6, 8, 4)))
            if idx == 3:  # arrow to HALT - special dashed
                prev_name = phase_order[idx - 1]
                _, _, _, prev_y2 = PHASE_PILLS[prev_name]
                mid_x = (x1 + x2) / 2
                cv.create_line(
                    *self._s(mid_x, prev_y2, mid_x, y1),
                    fill=C["line"], width=1, arrow=tk.LAST, dash=(3, 3),
                    arrowshape=(6, 8, 4))

            # Rounded-feel pill (rectangle with rounded corners simulated)
            r = cv.create_rectangle(*self._s(x1, y1, x2, y2), fill=C["box"],
                                    outline=C["line"], width=2)
            label = {"FETCH": "1 · FETCH", "DECODE": "2 · DECODE",
                     "EXECUTE": "3 · EXECUTE", "HALT": "■  HALT"}[name]
            t = cv.create_text(*self._s((x1 + x2) / 2, (y1 + y2) / 2), text=label,
                               fill=C["muted"], font=(SANS, 9, "bold"))
            # Checkmark for completed phases (initially hidden)
            chk = cv.create_text(*self._s(x2 - 12, (y1 + y2) / 2), text="",
                                 fill=C["green"], font=(SANS, 10, "bold"))
            # Glow rectangle (behind the pill, initially hidden)
            glow = cv.create_rectangle(*self._s(x1 - 3, y1 - 3, x2 + 3, y2 + 3),
                                       outline="", width=0, state="hidden")
            cv.tag_lower(glow, r)
            self.pills[name] = (r, t, chk, glow)

        # Draw loop-back arrow from EXECUTE back to FETCH
        ex_x1, _, ex_x2, ex_y2 = PHASE_PILLS["EXECUTE"]
        fe_x1, fe_y1, fe_x2, _ = PHASE_PILLS["FETCH"]
        loop_x = _PIPE_X0 + _PIPE_W + 18
        cv.create_line(
            *self._s(ex_x2, (PHASE_PILLS["EXECUTE"][1] + ex_y2) / 2,
                     loop_x, (PHASE_PILLS["EXECUTE"][1] + ex_y2) / 2,
                     loop_x, (fe_y1 + PHASE_PILLS["FETCH"][3]) / 2,
                     fe_x2, (fe_y1 + PHASE_PILLS["FETCH"][3]) / 2),
            fill=C["muted"], width=2, arrow=tk.LAST, arrowshape=(8, 10, 5), smooth=True)
        cv.create_text(*self._s(loop_x + 4, (fe_y1 + ex_y2) / 2),
                       text="ciclo", anchor="w", fill=C["muted"], font=(SANS, 7))

        # Step progress text
        self._step_text = cv.create_text(
            *self._s(_PIPE_X0, PHASE_PILLS["HALT"][3] + 14), anchor="nw",
            text="", fill=C["text"], font=(SANS, 8))

        self.info = cv.create_text(*self._s(_PIPE_X0, PHASE_PILLS["HALT"][3] + 32), anchor="nw",
                                   width=int(125 * S),
                                   text="", fill=C["text"], font=(SANS, 9))

    # ------------------------------------------------------------------
    def _cancel_anims(self):
        """Cancel any pending animation callbacks."""
        for aid in self._anim_after_ids:
            try:
                self.canvas.after_cancel(aid)
            except (ValueError, tk.TclError):
                pass
        self._anim_after_ids.clear()
        for item in self._glow_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._glow_items.clear()

    def _flash_register(self, name, old_val, new_val):
        """Create a brief flash effect on a register that changed value."""
        cv = self.canvas
        x1, y1, x2, y2 = BOXES[name]

        # Show old value struck through (dimmed, slightly offset above)
        if name not in ("MEM", "IN", "OUT"):
            vy = (y1 + y2) / 2 + 6
            old_text = cv.create_text(
                *self._s((x1 + x2) / 2 - 8, vy - 10),
                text=str(old_val), fill=C["red"], font=(MONO, 8),
                stipple="gray50")
            self._glow_items.append(old_text)
            # Remove the old-value indicator after a delay
            aid = cv.after(800, lambda: self._safe_delete(old_text))
            self._anim_after_ids.append(aid)

        # Bright border flash
        glow_rect = cv.create_rectangle(
            *self._s(x1 - 2, y1 - 2, x2 + 2, y2 + 2),
            outline=C["cyan"], width=3)
        self._glow_items.append(glow_rect)
        # Fade the glow border after 500ms
        aid = cv.after(500, lambda: self._safe_delete(glow_rect))
        self._anim_after_ids.append(aid)

    def _safe_delete(self, item):
        """Safely delete a canvas item."""
        try:
            self.canvas.delete(item)
        except tk.TclError:
            pass
        if item in self._glow_items:
            self._glow_items.remove(item)

    def update(self, cpu, events, alu_last, in_queue):
        cv = self.canvas
        # Clean up dynamic highlights but keep glow items (they self-delete)
        for item in self.hl:
            cv.delete(item)
        self.hl = []

        # Track cycle count and completed phases
        if cpu.phase == "FETCH" and self._prev_values.get("_phase") == "EXECUTE":
            self._cycle_count += 1
            self._completed_phases.clear()
        elif cpu.phase == "FETCH" and not self._prev_values:
            self._cycle_count = 1
            self._completed_phases.clear()

        if self._prev_values.get("_phase") and self._prev_values["_phase"] != cpu.phase:
            self._completed_phases.add(self._prev_values["_phase"])

        values = {"PC": cpu.pc, "MAR": cpu.mar, "MDR": cpu.mdr, "IR": cpu.ir, "AC": cpu.ac,
                  "CU": cpu.mnemonic or "—", "ALU": alu_last,
                  "MEM": f"M[{cpu.mar}]\n= {cpu.mem[cpu.mar]}",
                  "IN": f"cola: {in_queue}" if in_queue else "—",
                  "OUT": str(cpu.output[-1]) if cpu.output else "—"}
        active = {e.dst for e in events}

        # Detect changed registers and flash them
        for name, val in values.items():
            str_val = str(val)
            old_str = self._prev_values.get(name)
            on = name in active

            if old_str is not None and old_str != str_val and on:
                self._flash_register(name, old_str, str_val)

            cv.itemconfig(self.value[name], text=str_val,
                          fill=C["green"] if on else C["text"])
            cv.itemconfig(self.rect[name], outline=C["orange"] if on else C["line"],
                          width=3 if on else 2)

        # Store current values for next comparison
        self._prev_values = {name: str(val) for name, val in values.items()}
        self._prev_values["_phase"] = cpu.phase

        # Draw active data flow arrows with labels
        for e in events:
            if e.src == e.dst:
                continue
            p1, p2 = self._edge(e.src, e.dst)
            scaled_p1 = self._s(*p1)
            scaled_p2 = self._s(*p2)
            # Thicker, brighter arrow
            self.hl.append(cv.create_line(*scaled_p1, *scaled_p2,
                                          arrow=tk.LAST, width=4,
                                          fill=C["accent"],
                                          arrowshape=(12, 14, 6)))
            # Data label on the arrow - extract value from event text
            label_text = self._extract_arrow_label(e)
            if label_text:
                mid_x = (scaled_p1[0] + scaled_p2[0]) / 2
                mid_y = (scaled_p1[1] + scaled_p2[1]) / 2
                # Background for label
                bg = cv.create_rectangle(mid_x - 18 * S, mid_y - 8 * S,
                                         mid_x + 18 * S, mid_y + 8 * S,
                                         fill=C["panel"], outline=C["accent"], width=1)
                lbl = cv.create_text(mid_x, mid_y, text=label_text,
                                     fill=C["orange"], font=(MONO, 7, "bold"))
                self.hl.append(bg)
                self.hl.append(lbl)

        cv.itemconfig(self.flags, text=f"Z = {int(cpu.zero)}    N = {int(cpu.negative)}")

        # Update pipeline pills with enhanced visuals
        phase_order = ["FETCH", "DECODE", "EXECUTE"]
        for name, (r, t, chk, glow) in self.pills.items():
            on = name == cpu.phase
            is_halt = name == "HALT"
            completed = name in self._completed_phases and name != "HALT"

            if on:
                color = C["red"] if is_halt else C["accent"]
                cv.itemconfig(r, fill=color, outline=color, width=3)
                cv.itemconfig(t, fill="#ffffff")
                cv.itemconfig(chk, text="")
                # Show glow for current phase
                cv.itemconfig(glow, state="normal", outline=color, width=2)
            elif completed:
                cv.itemconfig(r, fill="#1a3a2a", outline=C["green"], width=2)
                cv.itemconfig(t, fill=C["green"])
                cv.itemconfig(chk, text="✓")
                cv.itemconfig(glow, state="hidden")
            else:
                cv.itemconfig(r, fill=C["box"], outline=C["line"], width=2)
                cv.itemconfig(t, fill=C["muted"])
                cv.itemconfig(chk, text="")
                cv.itemconfig(glow, state="hidden")

        # Update cycle counter
        if self._cycle_count > 0:
            cv.itemconfig(self._cycle_label, text=f"Ciclo #{self._cycle_count}")

        # Update step progress text
        if cpu.halted:
            cv.itemconfig(self._step_text,
                          text=f"■ HALT — {cpu.instructions_done} instr.",
                          fill=C["red"])
        else:
            # Build a visual pipeline indicator: FETCH → DECODE → EXECUTE
            parts = []
            for ph in phase_order:
                if ph == cpu.phase:
                    parts.append(f"▶{ph}")
                elif ph in self._completed_phases:
                    parts.append(f"✓{ph}")
                else:
                    parts.append(f"  {ph}")
            cv.itemconfig(self._step_text,
                          text=" → ".join(parts),
                          fill=C["text"])

        if cpu.error:
            cv.itemconfig(self.info, text="Error:\n" + cpu.error, fill=C["red"])
        else:
            from core.isa import DESCRIPTIONS
            desc = DESCRIPTIONS.get(cpu.mnemonic, "") if cpu.phase in ("EXECUTE", "FETCH") and cpu.mnemonic else ""
            head = f"Instrucción\n{disassemble(cpu.ir)}" if cpu.mnemonic else "Sin instrucción"
            cv.itemconfig(self.info, text=f"{head}\n{desc}", fill=C["text"])

    @staticmethod
    def _extract_arrow_label(event):
        """Extract a short value label from event text for display on arrows."""
        text = event.text
        # Look for patterns like (123) at the end
        if "(" in text and text.rstrip().endswith(")"):
            start = text.rfind("(")
            val = text[start + 1:-1].strip()
            if len(val) <= 8:
                return f"={val}"
        # Look for "= VALUE" patterns
        if "= " in text:
            parts = text.split("= ")
            if len(parts) >= 2:
                val = parts[-1].strip().rstrip(")")
                if len(val) <= 8 and val.lstrip("-").isdigit():
                    return f"={val}"
        return ""


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

        # Tooltip window
        self._tooltip = None
        self._tooltip_after = None
        cv.bind("<Motion>", self._on_motion)
        cv.bind("<Leave>", self._hide_tooltip)

        # Flash tracking
        self._flash_items = []
        self._flash_after_ids = []
        self._prev_mem_read = None
        self._prev_mem_write = None

    def _click(self, e):
        c, r = (e.x - HDR) // CELL_W, (e.y - HDR) // CELL_H
        if 0 <= c < 10 and 0 <= r < 10:
            self.on_click(r * 10 + c)

    def _addr_from_pos(self, x, y):
        """Get memory address from canvas coordinates."""
        c, r = (x - HDR) // CELL_W, (y - HDR) // CELL_H
        if 0 <= c < 10 and 0 <= r < 10:
            return r * 10 + c
        return None

    def _on_motion(self, e):
        """Show tooltip on hover."""
        addr = self._addr_from_pos(e.x, e.y)
        if addr is None:
            self._hide_tooltip()
            return
        # Cancel previous scheduled tooltip
        if self._tooltip_after:
            self.canvas.after_cancel(self._tooltip_after)
        self._tooltip_after = self.canvas.after(200, lambda: self._show_tooltip(e, addr))

    def _show_tooltip(self, e, addr):
        """Display a tooltip with cell info."""
        self._hide_tooltip()
        if not hasattr(self, '_cpu_ref') or self._cpu_ref is None:
            return
        cpu = self._cpu_ref
        word = cpu.mem[addr]
        dis = disassemble(word)
        kind_label = ""
        if hasattr(self, '_prog_ref') and self._prog_ref:
            kind = self._prog_ref.kinds.get(addr)
            kind_label = {"code": "instrucción", "data": "dato"}.get(kind, "libre")
        else:
            kind_label = "libre"

        tip_text = f"Dir: {addr:02d}  |  Valor: {word}\n{kind_label}  →  {dis}"

        self._tooltip = tw = tk.Toplevel(self.canvas)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        # Position near cursor
        x_root = self.canvas.winfo_rootx() + e.x + 12
        y_root = self.canvas.winfo_rooty() + e.y - 10
        tw.wm_geometry(f"+{x_root}+{y_root}")
        lbl = tk.Label(tw, text=tip_text, justify="left",
                       bg="#1e2840", fg="#e8edf7", relief="solid", borderwidth=1,
                       font=(MONO, 9), padx=6, pady=4)
        lbl.pack()

    def _hide_tooltip(self, _e=None):
        """Hide the tooltip."""
        if self._tooltip_after:
            try:
                self.canvas.after_cancel(self._tooltip_after)
            except (ValueError, tk.TclError):
                pass
            self._tooltip_after = None
        if self._tooltip:
            try:
                self._tooltip.destroy()
            except tk.TclError:
                pass
            self._tooltip = None

    def _flash_cell(self, addr, color):
        """Briefly flash a cell with the given color."""
        cv = self.canvas
        r, c = divmod(addr, 10)
        x1, y1 = HDR + c * CELL_W + 1, HDR + r * CELL_H + 1
        flash = cv.create_rectangle(x1 - 1, y1 - 1, x1 + CELL_W, y1 + CELL_H,
                                    outline=color, width=3)
        self._flash_items.append(flash)
        aid = cv.after(600, lambda: self._remove_flash(flash))
        self._flash_after_ids.append(aid)

    def _remove_flash(self, item):
        try:
            self.canvas.delete(item)
        except tk.TclError:
            pass
        if item in self._flash_items:
            self._flash_items.remove(item)

    def update(self, cpu, program):
        cv = self.canvas
        # Store refs for tooltip
        self._cpu_ref = cpu
        self._prog_ref = program

        # Detect memory read (MAR changed) and write for flash effects
        if cpu.last_mem_write is not None and cpu.last_mem_write != self._prev_mem_write:
            self._flash_cell(cpu.last_mem_write, C["orange"])
        if cpu.mar != self._prev_mem_read and cpu.last_mem_write != cpu.mar:
            self._flash_cell(cpu.mar, C["cyan"])
        self._prev_mem_read = cpu.mar
        self._prev_mem_write = cpu.last_mem_write

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

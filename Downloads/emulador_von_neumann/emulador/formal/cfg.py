"""Grafo de flujo de control (CFG) de un programa ensamblado.

Grafo dirigido G = (V, E): V = direcciones que contienen instrucciones,
E = transiciones posibles de ejecución (secuenciales o por salto).
"""
from collections import deque


def build_cfg(program):
    """Devuelve (nodos, aristas). Cada arista es (origen, destino, tipo) con
    tipo en {'seq', 'jump', 'true', 'false'}."""
    code = sorted(a for a, k in program.kinds.items() if k == "code")
    code_set = set(code)
    edges = []
    for a in code:
        op = program.mnemonics[a]
        target = program.operands[a]
        if op == "HALT":
            continue
        if op == "JUMP":
            edges.append((a, target, "jump"))
        elif op in ("JZ", "JN"):
            edges.append((a, target, "true"))
            if a + 1 in code_set:
                edges.append((a, a + 1, "false"))
        elif a + 1 in code_set:
            edges.append((a, a + 1, "seq"))
    return code, edges


def analyze(program):
    """Verifica propiedades del grafo. Devuelve (resumen, lista de avisos)."""
    nodes, edges = build_cfg(program)
    if not nodes:
        return {"nodos": 0, "aristas": 0}, ["El programa no tiene instrucciones."]

    succ = {n: [] for n in nodes}
    pred = {n: [] for n in nodes}
    for a, b, _ in edges:
        if b in succ:
            succ[a].append(b)
            pred[b].append(a)

    def bfs(start, graph):
        seen, queue = set(start), deque(start)
        while queue:
            u = queue.popleft()
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        return seen

    reachable = bfs([nodes[0]], succ)
    halts = [n for n in nodes if program.mnemonics[n] == "HALT"]
    reach_halt = bfs(halts, pred) if halts else set()

    warnings = []
    if not halts:
        warnings.append("No hay ninguna instrucción HALT: el programa nunca termina.")
    for n in nodes:
        label = f"dirección {n} ({program.mnemonics[n]})"
        if n not in reachable:
            warnings.append(f"Código inalcanzable: {label}")
        elif n not in reach_halt:
            warnings.append(f"Desde {label} no se puede llegar a HALT")
    for a in nodes:
        op = program.mnemonics[a]
        if op in ("JUMP", "JZ", "JN") and program.operands[a] not in succ:
            warnings.append(f"El salto en {a} apunta a una celda de datos "
                            f"({program.operands[a]})")
        if op != "HALT" and op != "JUMP" and a + 1 not in succ:
            warnings.append(f"La instrucción en {a} continúa hacia una celda sin código")

    summary = {
        "nodos": len(nodes),
        "aristas": len(edges),
        "alcanzables": len(reachable),
        "con camino a HALT": len(reach_halt & reachable),
        "tiene ciclos": _has_cycle(succ),
    }
    return summary, warnings


def _has_cycle(succ):
    color = {n: 0 for n in succ}

    def dfs(u):
        color[u] = 1
        for v in succ[u]:
            if color[v] == 1 or (color[v] == 0 and dfs(v)):
                return True
        color[u] = 2
        return False

    return any(color[n] == 0 and dfs(n) for n in succ)

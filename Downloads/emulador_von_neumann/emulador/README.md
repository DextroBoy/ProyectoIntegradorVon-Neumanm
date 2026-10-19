# Emulador Von Neumann — Arquitectura de Computadores + Matemáticas Discretas

Emulador didáctico en Python: memoria, registros (PC, MAR, MDR, IR, AC), ALU y
ciclo fetch-decode-execute, con interfaz gráfica y modelo formal integrado.

## Ejecutar
```
pip install -r requirements.txt
python main.py
```
Pruebas (no necesitan interfaz):
```
python -m unittest discover -s tests -v
```
En Linux, si falta Tkinter: `sudo apt install python3-tk`.

## Uso rápido
1. Elige un programa del menú (o escribe/abre uno) → se ensambla solo.
2. **F6** avanza una fase, **F7** una instrucción, **F5** ejecuta/pausa, **F8** reinicia.
3. Cuando el programa pide `INPUT`, haz clic en la consola, escribe un entero y pulsa Enter.
4. Lee el panel de explicación (bajo el diagrama): dice qué acaba de ocurrir en cada paso.
   Haz **clic en cualquier componente** (PC, MAR, ALU, fases…) para ver qué hace.
5. Pestaña **Modelo formal**: autómata, grafo de flujo y tablas de verdad en vivo.
6. Pestaña **Notas para exponer**: guion, explicación de cada parte y preguntas probables.

## Estructura
```
core/        isa.py (ISA, codificación)  cpu.py (registros, ALU, ciclo)
assembler/   ensamblador de dos pasadas con errores por línea
formal/      automata.py (Q,Σ,δ,q0,F + tablas de verdad)  cfg.py (grafo + verificación)
gui/         views.py (dibujos)  app.py (ventana)  notes.py (textos explicativos)
programas/   ejemplos .asm
tests/       test_emulador.py (25 pruebas)  smoke_gui.py (prueba de humo sin pantalla)
```

## Correspondencia con Matemáticas Discretas
| Concepto | Dónde |
|---|---|
| Conjuntos (I, M, I × M) | `core/isa.py`, pestaña «ISA y ayuda» |
| Funciones y relaciones (δ, decodificador) | `core/cpu.py`, `formal/automata.py:delta` |
| Autómata finito (Q, Σ, δ, q0, F) | `formal/automata.py`, diagrama animado |
| Álgebra booleana (AND/OR/NOT, JZ, JN) | tablas de verdad en la pestaña formal |
| Grafos dirigidos (flujo de control) | `formal/cfg.py`, cobertura de nodos |

`tests/test_emulador.py::test_delta_matches_cpu` comprueba que la función δ del
modelo formal coincide con el comportamiento real del procesador.

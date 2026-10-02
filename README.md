# ProyectoIntegradorVon-Neumanm

# Emulador de una Arquitectura Von Neumann

**Proyecto Integrador — Arquitectura de Computadores**
UCEVA — Unidad Central del Valle del Cauca

Emulador en software, escrito en Python, que reproduce el funcionamiento interno de un computador didáctico basado en el modelo Von Neumann: memoria, registros, Unidad Aritmético-Lógica (ALU) y ciclo de instrucción (*fetch → decode → execute*), con una interfaz gráfica que muestra la ejecución paso a paso.

---

## Tabla de contenidos

1. [Integrantes](#integrantes)
2. [Descripción](#descripción)
3. [Objetivos](#objetivos)
4. [Arquitectura emulada](#arquitectura-emulada)
5. [Lenguaje ensamblador (ISA)](#lenguaje-ensamblador-isa)
6. [Estructura del proyecto](#estructura-del-proyecto)
7. [Requisitos e instalación](#requisitos-e-instalación)
8. [Uso](#uso)
9. [Programas de ejemplo](#programas-de-ejemplo)
10. [Pruebas](#pruebas)
11. [Cronograma](#cronograma)
12. [Estado del proyecto](#estado-del-proyecto)
13. [Organización del equipo](#organización-del-equipo)
14. [Flujo de trabajo con Git](#flujo-de-trabajo-con-git)
15. [Referencias](#referencias)

---

## Integrantes

| Nombre | Rol principal |
| --- | --- |
| Andrés Mauricio Navarro | 
| Daniel Estaban mataboy |
| Nicolas Tintinago |

**Docente: ARMANDO ARBOLEDA DUQUE** 
**Asignatura:** Arquitectura de Computadores


---

## Descripción

El modelo Von Neumann describe un computador donde **instrucciones y datos comparten la misma memoria**, y una unidad central de procesamiento ejecuta un ciclo repetitivo de búsqueda, decodificación y ejecución de instrucciones.

Este proyecto construye un emulador de ese modelo en Python. El usuario escribe o carga un programa en un lenguaje ensamblador reducido y puede observar, en tiempo real, cómo:

- el **Contador de Programa (PC)** avanza,
- cada instrucción se carga en el **Registro de Instrucción (IR)**,
- la **ALU** procesa los datos,
- se actualizan el **Acumulador (AC)** y las posiciones de memoria involucradas.

El proyecto es de naturaleza didáctica y no requiere hardware especial: se desarrolla íntegramente con software libre.

---

## Objetivos

### General

Diseñar e implementar un emulador de software que represente el funcionamiento de una arquitectura Von Neumann, incluyendo memoria, registros, ALU y ciclo de instrucción, con una interfaz gráfica que muestre su ejecución en tiempo real.

### Específicos

- Definir un lenguaje ensamblador reducido (ISA) con instrucciones aritméticas, lógicas, de salto y de entrada/salida.
- Modelar en software la memoria RAM y los registros internos (PC, AC, IR).
- Implementar la ALU con las operaciones definidas en el ISA.
- Construir el ciclo de instrucción completo: búsqueda, decodificación y ejecución.
- Desarrollar una interfaz gráfica que permita cargar programas y visualizar el estado de registros y memoria en tiempo real.

---

## Arquitectura emulada

| Componente real | Elemento simulado en software |
| --- | --- |
| Memoria RAM | Lista de 100 posiciones direccionables en Python |
| Registro PC (Program Counter) | Variable entera que apunta a la siguiente instrucción |
| Registro AC (Acumulador) | Variable que almacena el resultado de las operaciones |
| Registro IR (Instrucción) | Variable que guarda la instrucción actualmente decodificada |
| ALU | Función que ejecuta suma y resta según el opcode |
| Consola de entrada/salida | Función de entrada y lista de salida (en la GUI, cuadros de texto) |

### Codificación de instrucciones

Cada posición de memoria almacena un entero con el formato:

```
palabra = opcode * 100 + dirección
```

Por ejemplo, `ADD 6` se almacena como `306`. Los datos son simplemente enteros guardados en posiciones de la misma memoria.

### Ciclo de instrucción

```
        ┌──────────────────────────────────────────┐
        │                                          │
        ▼                                          │
   FETCH:    IR ← MEM[PC];  PC ← PC + 1            │
        │                                          │
        ▼                                          │
   DECODE:   opcode, dirección ← IR                │
        │                                          │
        ▼                                          │
   EXECUTE:  ejecutar la operación (ALU / memoria  │
             / salto / entrada-salida) ────────────┘
             (se detiene al ejecutar HALT)
```

---

## Lenguaje ensamblador (ISA)

| Mnemónico | Opcode | Operando | Descripción |
| --- | :---: | :---: | --- |
| `HALT` | 0 | — | Detiene la ejecución |
| `LOAD` | 1 | dirección | `AC ← MEM[dir]` |
| `STORE` | 2 | dirección | `MEM[dir] ← AC` |
| `ADD` | 3 | dirección | `AC ← AC + MEM[dir]` |
| `SUB` | 4 | dirección | `AC ← AC − MEM[dir]` |
| `JUMP` | 5 | dirección | `PC ← dir` |
| `JZ` | 6 | dirección | Si `AC == 0`, entonces `PC ← dir` |
| `INPUT` | 7 | — | `AC ←` valor de entrada |
| `OUTPUT` | 8 | — | Muestra el valor de `AC` |

### Sintaxis del ensamblador

- Un `;` inicia un comentario hasta el final de la línea.
- `ETIQUETA:` define un nombre para una dirección y se puede usar como operando (`JUMP INICIO`, `STORE A`).
- `DATA n` reserva una posición de memoria con el valor inicial `n`.
- Los datos deben ubicarse **después** de `HALT`, para que la CPU no intente ejecutarlos como instrucciones.
- Las instrucciones y las etiquetas no distinguen mayúsculas de minúsculas.

---

## Estructura del proyecto

Estructura objetivo del repositorio:

```
emulador-von-neumann/
├── README.md
├── requirements.txt
├── src/
│   ├── isa.py              # Definición del set de instrucciones
│   ├── ensamblador.py      # Traduce texto ensamblador a palabras de memoria
│   ├── cpu.py              # Memoria, registros, ALU y ciclo de instrucción
│   └── gui.py              # Interfaz gráfica
├── programas/
│   ├── suma.asm            # INPUT, ADD, OUTPUT
│   ├── condicional.asm     # Uso de JZ
│   └── bucle.asm           # Uso de JUMP
├── tests/
│   └── test_cpu.py         # Batería de pruebas
├── docs/
│   ├── diseno.md           # Diagrama de arquitectura y lista de instrucciones
│   └── manual_usuario.md
└── main.py                 # Punto de entrada
```

> Durante las primeras semanas el núcleo puede vivir en un solo archivo (`emulador_vn.py`) y separarse en módulos cuando comience la interfaz gráfica.

---

## Requisitos e instalación

**Requisitos**

- Python 3.10 o superior
- Tkinter (incluido con la instalación estándar de Python en Windows y macOS; en Linux puede requerir `sudo apt install python3-tk`)
- Opcional: PyQt5/PyQt6 si el equipo decide usarlo en lugar de Tkinter
- Editor recomendado: Visual Studio Code


---

## Uso

### Versión de consola (núcleo)

```bash
python emulador_vn.py
```

El programa de ejemplo pide dos números, los suma e imprime el resultado, mostrando los registros después de cada instrucción:

```
INPUT > 5
PC=01  IR=700  AC=5
PC=02  IR=206  AC=5
INPUT > 7
PC=03  IR=700  AC=7
PC=04  IR=306  AC=12
OUTPUT > 12
PC=05  IR=800  AC=12
PC=06  IR=000  AC=12
```

### Como módulo de Python

```python
from emulador_vn import CPU, ensamblar

cpu = CPU(entrada=lambda: 10)        # función que provee los datos de INPUT
cpu.cargar(ensamblar(codigo))        # ensambla y carga en memoria

cpu.paso()                           # ejecuta UNA instrucción
print(cpu.pc, cpu.ac, cpu.ir)        # consulta los registros
print(cpu.memoria[:10])              # consulta la memoria

cpu.ejecutar()                       # ejecuta hasta HALT
```

### Interfaz gráfica

*(Se documentará al completar las semanas 7-8: botones de cargar, ejecutar, paso a paso y reiniciar; paneles de registros, memoria y consola.)*

---

## Programas de ejemplo

### Suma de dos números

```asm
    INPUT           ; AC <- primer número
    STORE A         ; guardarlo en memoria
    INPUT           ; AC <- segundo número
    ADD A           ; AC <- AC + A (usa la ALU)
    OUTPUT          ; mostrar resultado
    HALT
A:  DATA 0
```

### Resta de dos números

```asm
    INPUT
    STORE A
    INPUT
    STORE B
    LOAD A
    SUB B
    OUTPUT
    HALT
A:  DATA 0
B:  DATA 0
```

### Programas por implementar

- **Condicional:** usar `JZ` para decidir según el valor del acumulador.
- **Bucle:** usar `JUMP` y `JZ` para repetir una operación (por ejemplo, una cuenta regresiva).

---

## Pruebas

Se documentará una batería de pruebas con programas que cubran:

| Caso | Qué valida |
| --- | --- |
| Aritmética | `ADD` y `SUB` con valores positivos, negativos y cero |
| Memoria | `LOAD` y `STORE` en distintas direcciones |
| Saltos | `JUMP` incondicional y `JZ` con AC igual y distinto de cero |
| Entrada/salida | `INPUT` y `OUTPUT` |
| Errores | Instrucción desconocida, operando faltante, dirección fuera de rango, opcode inválido |
| Límites | Programa que ocupa toda la memoria; bucle infinito detenido por límite de pasos |

Ejecución prevista de las pruebas:

```bash
python -m unittest discover tests
```

---

## Cronograma

| Semana | Actividad | Entregable parcial |
| :---: | --- | --- |
| 1 - 2 | Estudio del modelo Von Neumann y del computador didáctico LMC (Little Man Computer); definición del ISA propio | Documento de diseño: diagrama de arquitectura y lista de instrucciones |
| 3 - 4 | Implementación de la memoria RAM y los registros internos (PC, AC, IR) | Módulo de memoria y registros funcionando en consola |
| 5 - 6 | Implementación de la ALU y del ciclo de instrucción | Emulador ejecutando programas simples (ADD, SUB, JUMP) sin interfaz gráfica |
| 7 - 8 | Desarrollo de la interfaz gráfica (Tkinter o PyQt) | Emulador con GUI funcional |
| 9 - 10 | Cargador de programas desde archivos de texto; validación de instrucciones | Función de carga probada con varios ejemplos |
| 11 | Pruebas integrales (bucles, condicionales, entrada/salida) y corrección de errores | Batería de pruebas documentada |
| 12 | Documentación final, manual de usuario y video demostrativo | Informe final + sustentación |

---

## Estado del proyecto

- [x] Definición del ISA (9 instrucciones)
- [x] Ensamblador con etiquetas y directiva `DATA`
- [x] Memoria, registros (PC, AC, IR), ALU y ciclo de instrucción en consola
- [ ] Interfaz gráfica
- [ ] Carga de programas desde archivo
- [ ] Programas de ejemplo condicional y de bucle
- [ ] Batería de pruebas
- [ ] Manual de usuario y video demostrativo
- [ ] Informe final y sustentación

---

## Organización del equipo

Propuesta inicial de reparto, a ajustar entre los tres integrantes:

| Integrante | Responsabilidad principal | Apoyo |
| --- | --- | --- |
| Integrante 1 | Núcleo: CPU, ALU, ciclo de instrucción | Pruebas |
| Integrante 2 | Interfaz gráfica | Integración con el núcleo |
| Integrante 3 | Ensamblador, cargador de programas y programas de ejemplo | Documentación |

Todos participan en las pruebas integrales, el manual de usuario, el video y la sustentación.

---

## Flujo de trabajo con Git

- La rama `main` solo contiene código que funciona.
- Cada integrante trabaja en una rama propia o por funcionalidad (`feature/gui`, `feature/ensamblador`, `feature/alu`).
- Los cambios entran a `main` mediante *pull request* revisado por al menos otro integrante.
- Mensajes de commit claros y en español, por ejemplo: `Agrega instrucción JZ al ciclo de ejecución`.

---

## Referencias

- Von Neumann, J. (1945). *First Draft of a Report on the EDVAC*.
- Stallings, W. *Organización y Arquitectura de Computadores*. Pearson.
- Little Man Computer (LMC): modelo didáctico de computador que inspira el ISA de este proyecto.
- Documentación oficial de Python: <https://docs.python.org/3/>
- Documentación de Tkinter: <https://docs.python.org/3/library/tkinter.html>

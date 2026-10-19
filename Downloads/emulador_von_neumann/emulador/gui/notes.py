"""Notas didácticas: explicaciones en vivo, de componentes y guía de exposición."""

COMPONENTS = {
    "PC": ("PC · Contador de programa",
           "Guarda la dirección de la PRÓXIMA instrucción. Después de cada FETCH aumenta en 1; "
           "los saltos (JUMP, JZ, JN) lo sobrescriben con la dirección destino. "
           "En el código es la variable cpu.pc."),
    "MAR": ("MAR · Registro de dirección de memoria",
            "Le dice a la memoria QUÉ celda leer o escribir. Todo acceso a memoria pasa por aquí: "
            "primero se carga la dirección en el MAR y luego se lee o escribe."),
    "MDR": ("MDR · Registro de datos de memoria",
            "Es la «ventanilla» de la memoria: lo que se lee llega aquí, y lo que se va a escribir "
            "sale de aquí. Separa al procesador (rápido) de la memoria (lenta)."),
    "IR": ("IR · Registro de instrucción",
           "Guarda la palabra que se está ejecutando, por ejemplo 305 = ADD 5. La unidad de control "
           "la divide en opcode (IR // 100) y operando (IR % 100)."),
    "CU": ("CU · Unidad de control",
           "Decodifica el opcode y ordena qué micro-operaciones ocurren y en qué orden: es el "
           "«director de orquesta». Formalmente implementa la función de transición δ del autómata."),
    "AC": ("AC · Acumulador",
           "Registro donde la ALU deja sus resultados y desde donde se guardan o imprimen valores. "
           "De él se derivan las banderas Z (AC = 0) y N (AC < 0), que usan JZ y JN."),
    "ALU": ("ALU · Unidad aritmético-lógica",
            "Hace ADD, SUB, AND, OR y NOT sobre enteros de 16 bits con signo (con desbordamiento). "
            "Es una función pura: (AC, MDR, opcode) → nuevo AC. Muestra la última operación hecha."),
    "MEM": ("MEMORIA · RAM",
            "100 celdas direccionables, M = {0, 1, …, 99}. Guarda programa y datos JUNTOS: ese es el "
            "rasgo central de Von Neumann. Cada instrucción se codifica como opcode·100 + operando."),
    "IN": ("ENTRADA",
           "La instrucción INPUT detiene el procesador hasta que escribes un entero en la consola; "
           "luego lo copia al acumulador."),
    "OUT": ("SALIDA",
            "La instrucción OUTPUT copia el acumulador a la consola. Aquí se ve el último valor emitido."),
    "FETCH": ("Fase 1 · FETCH (búsqueda)",
              "Se trae la instrucción de memoria: MAR ← PC; MDR ← M[MAR]; IR ← MDR; PC ← PC + 1."),
    "DECODE": ("Fase 2 · DECODE (decodificación)",
               "La unidad de control separa el IR en opcode y operando y averigua qué instrucción es. "
               "Si el opcode no existe, el procesador se detiene con error."),
    "EXECUTE": ("Fase 3 · EXECUTE (ejecución)",
                "Se realiza la operación: leer/escribir memoria, usar la ALU, saltar, pedir entrada o "
                "mostrar salida. Al terminar, el ciclo vuelve a FETCH (salvo en HALT)."),
    "HALT": ("HALT · estado de aceptación",
             "Estado final del autómata (q ∈ F). Se llega al ejecutar la instrucción HALT, "
             "o por un error (opcode inválido)."),
}

INSTR = {
    "LOAD": "LOAD lee una celda de memoria y la copia al acumulador (MAR ← dirección, MDR ← M[MAR], AC ← MDR).",
    "STORE": "STORE escribe el acumulador en una celda (MAR ← dirección, MDR ← AC, M[MAR] ← MDR). "
             "La celda escrita se marca en naranja en la memoria.",
    "ADD": "ADD: la ALU suma el acumulador con M[x] y deja el resultado en AC.",
    "SUB": "SUB: la ALU resta M[x] al acumulador y deja el resultado en AC.",
    "AND": "AND: la ALU aplica AND bit a bit entre AC y M[x] (tabla de verdad en «Modelo formal»).",
    "OR": "OR: la ALU aplica OR bit a bit entre AC y M[x] (tabla de verdad en «Modelo formal»).",
    "NOT": "NOT: la ALU invierte todos los bits del acumulador.",
    "JUMP": "JUMP: salto incondicional. Sobrescribe el PC con la dirección destino.",
    "JZ": "JZ: salto condicional. Evalúa la proposición p = «AC es cero». Si p es verdadera, "
          "PC ← destino; si es falsa, el PC sigue a la siguiente instrucción.",
    "JN": "JN: salto condicional. Evalúa la proposición «AC es negativo». Si es verdadera, "
          "PC ← destino; si no, sigue a la siguiente instrucción.",
    "INPUT": "INPUT: toma un número ingresado por el usuario y lo deja en el acumulador.",
    "OUTPUT": "OUTPUT: copia el acumulador a la consola de salida.",
    "HALT": "HALT: detiene el procesador.",
}

NEXT = {"FETCH": "FETCH (buscar la siguiente instrucción)",
        "DECODE": "DECODE (interpretar la instrucción)",
        "EXECUTE": "EXECUTE (ejecutarla)",
        "HALT": "nada: el procesador está detenido"}


def explain(cpu, last):
    """Explica lo que acaba de ocurrir. last ∈ {None, FETCH, DECODE, EXECUTE, INSTR}."""
    if cpu.error:
        return "Error de ejecución", cpu.error
    if last is None:
        return ("Listo para ejecutar",
                "El programa está cargado en memoria (celdas azules = código, verdes = datos) y el PC "
                "vale 0. Pulsa F6 para avanzar UNA fase del ciclo, o F7 para una instrucción completa. "
                "Haz clic en cualquier componente del diagrama para ver qué hace.")
    if cpu.waiting_input:
        return ("Esperando entrada",
                "La instrucción INPUT necesita un número. Escríbelo en la consola (abajo a la izquierda) "
                "y pulsa Enter; la ejecución continúa donde quedó.")
    if cpu.halted:
        return ("HALT · fin del programa",
                f"Se ejecutó HALT: el autómata llegó al estado de aceptación (q ∈ F). "
                f"Se completaron {cpu.instructions_done} instrucciones.")
    nxt = NEXT[cpu.phase]
    if last == "FETCH":
        return ("Acaba de ocurrir: FETCH",
                f"El PC ({cpu.cur_addr}) se copió al MAR; la memoria entregó la palabra {cpu.ir} al MDR; "
                f"ésta pasó al IR; y el PC subió a {cpu.pc} para apuntar a la siguiente instrucción.\n"
                f"Sigue: {nxt}.")
    if last == "DECODE":
        return ("Acaba de ocurrir: DECODE",
                f"La unidad de control separó la palabra {cpu.ir}: opcode {cpu.opcode} (= {cpu.mnemonic}) "
                f"y operando {cpu.operand}   [opcode = IR // 100, operando = IR % 100].\n"
                f"Sigue: {nxt}.")
    detail = cpu.last_events[-1].text if cpu.last_events else ""
    title = f"Instrucción completa: {cpu.mnemonic}" if last == "INSTR" else f"Acaba de ocurrir: EXECUTE {cpu.mnemonic}"
    return title, f"{INSTR.get(cpu.mnemonic, '')}\nÚltimo movimiento: {detail}\nSigue: {nxt}."


FORMAL_NOTES = {
    "tables": "Las instrucciones lógicas aplican estas tablas bit a bit. En JZ y JN, la proposición "
              "(AC = 0, AC < 0) decide si el PC salta o sigue de largo.",
    "automata": "Q son las fases del ciclo. Cada instrucción recorre FETCH → DECODE → EXECUTE y regresa "
                "a FETCH; HALT es el estado de aceptación. El círculo azul es el estado actual.",
    "cfg": "Cada nodo es una instrucción (vértice) y cada flecha una transición posible (arista). "
           "Verde V: salto si la condición es cierta · naranja: JUMP · gris F: no salta. "
           "Los nodos ya recorridos se pintan de verde: eso mide la cobertura de la prueba.",
}


GUIDE = """\
NOTAS PARA LA EXPOSICIÓN
========================

1. IDEA GENERAL (30 segundos)
-----------------------------
Construimos un computador completo en software, basado en el modelo de Von Neumann:
una memoria que guarda programa y datos juntos, un procesador que repite sin parar el
ciclo buscar–decodificar–ejecutar, y entrada/salida. Además lo describimos formalmente
con Matemáticas Discretas: conjuntos, funciones, un autómata finito, álgebra booleana
y grafos. No es solo un programa: es un modelo matemático que además se puede ejecutar.

Frase para abrir:  «¿Qué pasa dentro de un computador cuando suma 2 + 3? Vamos a verlo.»


2. CÓMO ESTÁ ORGANIZADO EL CÓDIGO
---------------------------------
  core/       el procesador: isa.py (instrucciones) y cpu.py (registros, ALU, ciclo)
  assembler/  convierte texto en ensamblador a números en memoria
  formal/     el modelo matemático: automata.py (Q,Σ,δ,q0,F) y cfg.py (grafo)
  gui/        la interfaz gráfica (no contiene lógica del procesador)
Punto a destacar: el procesador funciona SIN interfaz; la GUI solo lo observa.
Por eso pudimos probarlo con pruebas automáticas.


3. LOS COMPONENTES (qué decir de cada uno)
------------------------------------------
Memoria   100 celdas con números enteros. Programa y datos conviven en ella: eso es Von Neumann.
          Una instrucción es un número:  opcode × 100 + operando.  Ej.: 305 = ADD 5.
PC        Dice cuál es la próxima instrucción. Sube de 1 en 1 y los saltos lo cambian.
MAR       Dirección de la celda a la que se quiere acceder.
MDR       Dato que va o viene de la memoria.
IR        Instrucción que se está ejecutando ahora.
CU        Unidad de control: interpreta la instrucción y manda qué hacer.
ALU       Hace las cuentas (+, −, AND, OR, NOT).
AC        Acumulador: guarda el resultado. Sus banderas Z y N alimentan los saltos.
(En la ventana: haz clic en un componente y aparece su explicación.)


4. EL CICLO DE INSTRUCCIÓN (la parte central)
---------------------------------------------
FETCH    MAR ← PC;  MDR ← M[MAR];  IR ← MDR;  PC ← PC + 1
DECODE   opcode = IR // 100;  operando = IR % 100
EXECUTE  depende de la instrucción (leer, escribir, calcular, saltar…)
Demostración: con F6 avanzar fase por fase y señalar las flechas azules y el panel
«Acaba de ocurrir», que explica cada paso en palabras.


5. EL LENGUAJE (ISA)
--------------------
13 instrucciones:  LOAD STORE ADD SUB AND OR NOT JUMP JZ JN INPUT OUTPUT HALT.
Formalmente:  I = {instrucciones}   y   M = {0, 1, …, 99}.
Cada instrucción con operando es un elemento del producto cartesiano I × M.


6. MATEMÁTICAS DISCRETAS (pestaña «Modelo formal»)
--------------------------------------------------
CONJUNTOS        I (instrucciones), M (direcciones), I × M (instrucción con operando).
FUNCIONES        δ: Q × Σ → Q es la función de transición. El decodificador asigna a cada
                 opcode una operación: es una función de {opcodes} en {operaciones de la ALU}.
AUTÓMATA FINITO  M = (Q, Σ, δ, q0, F)
                 Q  = {FETCH, DECODE, EXECUTE, HALT}     Σ = I ∪ {ε}
                 q0 = FETCH (con PC = 0)                  F = {HALT}
                 En pantalla el estado actual se ilumina y se muestra la tupla
                 q = (fase, PC, AC, IR).
ÁLGEBRA BOOLEANA AND, OR y NOT operan bit a bit con sus tablas de verdad. JZ evalúa la
                 proposición p = «AC = 0»: si p es verdadera salta, si es falsa no.
GRAFOS           El programa es un grafo dirigido: nodos = instrucciones, aristas = lo que
                 puede ejecutarse a continuación. Los bucles son ciclos del grafo.
                 Se verifica que todo nodo sea alcanzable y que desde todos se llegue a HALT.
Detalle fuerte: una de nuestras pruebas comprueba que la función δ del modelo matemático
da exactamente los mismos estados que el procesador real. La teoría y el código coinciden.


7. GUION DE LA DEMOSTRACIÓN
---------------------------
 1. Cargar 02_cuenta_regresiva.asm, velocidad 3, entrada 3.
 2. F6 varias veces: mostrar fetch/decode/execute y leer el panel de explicación.
 3. F7: ver el bucle (el PC vuelve atrás) y la memoria cambiando.
 4. Pestaña «Modelo formal»: autómata en movimiento y cobertura del grafo subiendo.
 5. 06_factorial.asm con entrada 5 → 120 (dos bucles anidados).
 6. 99_error_demo.asm: el ensamblador señala los errores línea por línea.


8. PREGUNTAS PROBABLES (y respuestas)
-------------------------------------
¿Por qué se llama arquitectura Von Neumann?
  Porque programa y datos comparten la misma memoria. Lo demostramos: un programa puede
  modificar sus propias instrucciones (hay una prueba que lo verifica).

¿Diferencia con la arquitectura Harvard?
  Harvard usa memorias separadas para instrucciones y datos (y buses distintos), lo que
  permite leer ambas a la vez. Von Neumann usa una sola, más simple, pero con el
  «cuello de botella de Von Neumann»: instrucciones y datos compiten por el mismo bus.

¿Por qué el opcode × 100 + operando?
  Es una codificación simple y legible (como el Little Man Computer): las dos últimas
  cifras son la dirección y las anteriores el tipo de instrucción.

¿Qué pasa si el PC llega a una celda de datos?
  Esa palabra se interpreta como instrucción. Si su opcode no existe, el procesador se
  detiene con «opcode inválido». Por eso los datos se colocan después del HALT.

¿Qué pasa si una suma se pasa del rango?
  Las palabras son de 16 bits con signo (−32768 a 32767) y se produce desbordamiento
  (wrap-around), igual que en un procesador real.

¿Por qué es un autómata FINITO si la memoria es grande?
  Modelamos como estados las fases del ciclo de control (4 estados). Los valores de PC, AC,
  IR y memoria son el «contexto» sobre el que actúan las transiciones.

¿Cómo saben que funciona?
  Más de 20 pruebas automáticas (aritmética, bucles, condicionales, E/S, errores, desbordamiento,
  coincidencia con el autómata) y verificación del grafo de cada programa.
"""

default rel

global main
extern printf
extern scanf
extern system
extern exit

section .data
    ; Mensajes de la consola
    msg_inicio  db "=== CALCULADORA CONTINUA V2 ===", 10, "Ingresa el numero inicial: ", 0
    msg_op      db 10, "Operacion (+, -, *, /) o '=' para terminar: ", 0
    msg_next    db "Siguiente numero: ", 0
    msg_parcial db ">> DISPLAY: %lld", 10, 0
    msg_final   db 10, "=======================", 10, "RESULTADO FINAL: %lld", 10, "=======================", 10, 0
    msg_err     db ">> ERROR: No se puede dividir por cero.", 10, 0
    
    ; Comando para la pausa final
    cmd_pause   db "pause", 0

    ; Formatos de lectura
    fmt_num     db "%lld", 0
    fmt_op      db " %c", 0 

section .bss
    acumulador  resq 1    ; Guarda el resultado parcial (64 bits)
    nuevo_num   resq 1    ; Guarda el número a operar (64 bits)
    operacion   resb 1    ; Guarda el signo (+, -, *, /, =)

section .text
main:
    ; --- CONFIGURACIÓN EXACTA DE LA PILA (Stack Frame) ---
    ; Al entrar a main, RSP termina en 8.
    push rbp             ; Resta 8 a RSP -> RSP ahora es múltiplo de 16 (Alineado)
    mov rbp, rsp
    sub rsp, 32          ; Restamos 32 (múltiplo de 16). Mantiene la alineación y da Shadow Space.

    ; --- 1. PEDIR NÚMERO INICIAL ---
    lea rcx, [msg_inicio]
    call printf
    
    lea rcx, [fmt_num]
    lea rdx, [acumulador]
    call scanf

.bucle_principal:
    ; Mostrar el acumulador actual
    lea rcx, [msg_parcial]
    mov rdx, [acumulador]
    call printf

    ; --- 2. PEDIR SIGNO DE OPERACIÓN ---
    lea rcx, [msg_op]
    call printf
    
    lea rcx, [fmt_op]
    lea rdx, [operacion]
    call scanf

    ; Verificar si presionó "="
    mov al, byte [operacion]
    cmp al, '='
    je .mostrar_final

    ; --- 3. PEDIR EL SIGUIENTE NÚMERO ---
    lea rcx, [msg_next]
    call printf
    
    lea rcx, [fmt_num]
    lea rdx, [nuevo_num]
    call scanf

    ; --- 4. SELECCIONAR LA OPERACIÓN MATEMÁTICA ---
    mov al, byte [operacion]
    cmp al, '+'
    je .sumar
    cmp al, '-'
    je .restar
    cmp al, '*'
    je .multiplicar
    cmp al, '/'
    je .dividir
    jmp .bucle_principal    ; Si ingresa un signo inválido, repite el ciclo

; --- BLOQUES MATEMÁTICOS ---
.sumar:
    mov rax, [acumulador]
    add rax, [nuevo_num]
    mov [acumulador], rax   
    jmp .bucle_principal

.restar:
    mov rax, [acumulador]
    sub rax, [nuevo_num]
    mov [acumulador], rax
    jmp .bucle_principal

.multiplicar:
    mov rax, [acumulador]
    imul rax, [nuevo_num]
    mov [acumulador], rax
    jmp .bucle_principal

.dividir:
    mov rcx, [nuevo_num]
    cmp rcx, 0              ; Evitar división por cero
    je .error_div

    mov rax, [acumulador]
    cqo                     ; Extensión de signo obligatoria para dividir en 64 bits
    idiv qword [nuevo_num]  ; Divide RDX:RAX entre el nuevo numero
    mov [acumulador], rax
    jmp .bucle_principal

.error_div:
    lea rcx, [msg_err]
    call printf
    jmp .bucle_principal    ; Ignora la operación y vuelve a pedir el signo

.mostrar_final:
    ; --- RESULTADO Y SALIDA ---
    lea rcx, [msg_final]
    mov rdx, [acumulador]
    call printf

    ; Pausa la consola para que la ventana se quede abierta
    lea rcx, [cmd_pause]
    call system

    ; Desarmar la pila y cerrar el programa de forma limpia
    add rsp, 32
    pop rbp
    xor rcx, rcx
    call exit
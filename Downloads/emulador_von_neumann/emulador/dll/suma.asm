; =====================================================================
;  suma.asm  -  funcion suma(a, b) para Windows x64, ensamblada con NASM
; ---------------------------------------------------------------------
;  Convencion de llamada Microsoft x64 (la que usa Windows en 64 bits):
;    * 1er argumento entero  -> RCX
;    * 2do argumento entero  -> RDX
;    * valor de retorno      -> RAX
;    * el llamador reserva 32 bytes de "shadow space" en la pila
;    * los registros no volatiles (RBX, RSI, RDI, ...) deben preservarse;
;      aqui no usamos ninguno, asi que no hay nada que guardar.
; =====================================================================

bits 64                     ; generamos codigo maquina de 64 bits
default rel                 ; direccionamiento relativo (buena practica en win64)

global suma                 ; exportamos el simbolo "suma" para que la DLL lo publique

section .text               ; seccion de codigo; no necesitamos .data

; ---------------------------------------------------------------------
;  long long suma(long long a, long long b)
;    RCX = a
;    RDX = b
;    RAX = a + b  (resultado)
; ---------------------------------------------------------------------
suma:
    mov rax, rcx            ; RAX = a   (copiamos el 1er parametro al registro de retorno)
    add rax, rdx            ; RAX = a + b   (ADD realiza la suma de enteros)
    ret                     ; regresamos al llamador; el resultado queda en RAX

; Cuenta regresiva: imprime N, N-1, ..., 1  (bucle con JZ)
        INPUT
        STORE N
LOOP:   LOAD  N
        JZ    FIN
        OUTPUT
        SUB   UNO
        STORE N
        JUMP  LOOP
FIN:    HALT
N:      DAT 0
UNO:    DAT 1

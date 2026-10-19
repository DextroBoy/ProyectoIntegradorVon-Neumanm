; Factorial de N (N <= 7 cabe en 16 bits). Usa un bucle dentro de otro.
        INPUT
        STORE N
        LOAD  UNO
        STORE R
OUTER:  LOAD  N
        JZ    FIN
        LOAD  R
        STORE A          ; A = R
        LOAD  N
        STORE C          ; C = contador = N
        LOAD  CERO
        STORE T          ; T = 0
INNER:  LOAD  C
        JZ    DONE
        SUB   UNO
        STORE C
        LOAD  T
        ADD   A
        STORE T          ; T = T + A  (R sumado N veces)
        JUMP  INNER
DONE:   LOAD  T
        STORE R          ; R = R * N
        LOAD  N
        SUB   UNO
        STORE N
        JUMP  OUTER
FIN:    LOAD  R
        OUTPUT
        HALT
N:      DAT 0
R:      DAT 0
A:      DAT 0
C:      DAT 0
T:      DAT 0
UNO:    DAT 1
CERO:   DAT 0

; A * B por sumas repetidas (B >= 0)
        INPUT
        STORE A
        INPUT
        STORE B
LOOP:   LOAD  B
        JZ    FIN
        SUB   UNO
        STORE B
        LOAD  R
        ADD   A
        STORE R
        JUMP  LOOP
FIN:    LOAD  R
        OUTPUT
        HALT
A:      DAT 0
B:      DAT 0
R:      DAT 0
UNO:    DAT 1

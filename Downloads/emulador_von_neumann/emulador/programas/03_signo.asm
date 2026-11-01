; Condicional: imprime 1 si x>0, 0 si x=0, -1 si x<0
        INPUT
        JN    NEG
        JZ    CERO
        LOAD  UNO
        OUTPUT
        HALT
NEG:    LOAD  MENOS
        OUTPUT
        HALT
CERO:   OUTPUT
        HALT
UNO:    DAT 1
MENOS:  DAT -1

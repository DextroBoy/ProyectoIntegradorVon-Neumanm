# Suma en NASM x64 llamada desde Python

Esta carpeta muestra el camino completo que recorre una función escrita en
ensamblador real hasta poder usarse desde Python.

## Pipeline

```
suma.asm
   │  nasm -f win64 suma.asm -o suma.obj     (ensamblado)
   ▼
suma.obj                                    (objeto COFF x64)
   │  gcc -shared suma.obj -o suma.dll       (enlazado)
   ▼
suma.dll                                    (biblioteca dinámica)
   │  ctypes.CDLL(...) + getattr("suma")     (llamada)
   ▼
Python
```

- `nasm -f win64` traduce el texto ensamblador a un **objeto** binario de
  64 bits (formato COFF, el que entiende Windows).
- `gcc -shared` enlaza ese objeto y produce una **DLL** con la función
  exportada.
- `ctypes` (biblioteca estándar de Python) carga la DLL en memoria y permite
  invocar la función como si fuera Python.

## Convención de llamada (Microsoft x64)

La función `suma(a, b)` recibe:

| Parámetro      | Registro |
|----------------|----------|
| `a` (1º)       | `RCX`    |
| `b` (2º)       | `RDX`    |
| resultado      | `RAX`    |

El cuerpo son solo tres instrucciones: copiar `RCX` a `RAX`, hacer
`add rax, rdx` y `ret`.

## Cómo regenerar la DLL

```bat
compilar.bat
```

O manualmente, dentro de esta carpeta:

```bat
nasm -f win64 suma.asm -o suma.obj
gcc -shared suma.obj -o suma.dll
```

## Cómo se llama desde Python

`llamar_suma.py` resuelve la ruta de la DLL de forma relativa al propio
archivo y la carga **una sola vez**:

```python
import ctypes, os

_DLL = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "suma.dll"))
_DLL.suma.argtypes = [ctypes.c_longlong, ctypes.c_longlong]
_DLL.suma.restype = ctypes.c_longlong
```

Luego basta con `_DLL.suma(4, 5)`, que devuelve `9`. También se puede
ejecutar como script:

```bat
python llamar_suma.py
```

## Cómo se usa desde la GUI

El botón **Σ Suma via DLL** de la ventana principal abre un formulario con
dos números. Al pulsar **Sumar**, la GUI importa `llamar_suma.suma_dll` y
muestra el resultado calculado por `suma.dll`.

La misma ventana incluye una vista de **solo lectura** con el contenido de
`suma.asm`, para consultar el código NASM x64 que genera la DLL. El botón
**↺ Recargar** vuelve a leer el archivo del disco. La compilación no se hace
en vivo: si cambias `suma.asm`, regenera la DLL ejecutando `compilar.bat`.

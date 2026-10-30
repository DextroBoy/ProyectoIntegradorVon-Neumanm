"""Carga suma.dll (NASM x64) con ctypes y expone suma_dll(a, b)."""
import ctypes
import os

_RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suma.dll")
_dll = None  # cache: la DLL se carga una sola vez


def _cargar():
    global _dll
    if _dll is None:
        _dll = ctypes.CDLL(_RUTA)
        _dll.suma.argtypes = [ctypes.c_longlong, ctypes.c_longlong]
        _dll.suma.restype = ctypes.c_longlong
    return _dll


def suma_dll(a: int, b: int) -> int:
    """Devuelve a + b calculado por la funcion suma() de suma.dll."""
    return _cargar().suma(a, b)


if __name__ == "__main__":
    x = int(input("Numero A: "))
    y = int(input("Numero B: "))
    print(f"Resultado: {suma_dll(x, y)} (calculado por suma.dll)")

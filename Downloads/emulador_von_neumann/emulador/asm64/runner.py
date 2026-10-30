"""Ensambla, enlaza y ejecuta nativamente un programa NASM x64 en Windows.

Pipeline:
    run.asm  ->  nasm -f win64 run.asm -o run.obj
             ->  gcc run.obj -o run.exe
             ->  ejecutar run.exe

Hay dos formas de uso:

* ``run_asm(src_text)``: compila y ejecuta de una vez, capturando toda la
  salida al final. NUNCA lanza excepciones: devuelve ``(ok, log)``.
* ``NasmProceso``: ejecucion INTERACTIVA. Compila, arranca run.exe con stdin
  y stdout conectados a pipes y entrega la salida en vivo mediante un
  callback, mientras la GUI puede enviar lineas a la entrada del programa.
"""
import codecs
import os
import subprocess
import threading
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_TIMEOUT = 10          # segundos maximos por paso de compilacion (nasm/gcc)
_TIMEOUT_EJEC = 30     # solo para el run_asm() clasico (no interactivo)
_MAX_SALIDA = 2000     # caracteres maximos de salida mostrados por paso

# Programa de ejemplo: demuestra el stack frame clasico de Windows x64.
# Solo ASCII (NASM no acepta acentos en el codigo fuente).
PLANTILLA_DEMO = """; ========================================================================
default rel
global main
extern printf

section .data
    fmt_intro db "=== DEMOSTRACION DEL STACK FRAME EN WINDOWS 11 X64 ===", 0xA, 0
    fmt_out   db "Var1 (RBP-8): 0x%llX | Var2 (RBP-16): 0x%llX", 0xA, 0
    fmt_res   db "Suma de variables locales: %lld", 0xA, 0

section .text
main:
    push rbp
    mov  rbp, rsp
    sub  rsp, 48

    mov  rax, 0x1122334455667788
    mov  [rbp - 8], rax
    mov  qword [rbp - 16], 2

    lea  rcx, [fmt_intro]
    call printf
    lea  rcx, [fmt_out]
    mov  rdx, [rbp - 8]
    mov  r8,  [rbp - 16]
    call printf

    mov  rax, [rbp - 8]
    add  rax, [rbp - 16]

    lea  rcx, [fmt_res]
    mov  rdx, rax
    call printf

    mov  rax, 0
    add  rsp, 48
    pop  rbp
    ret
"""


def plantilla_actual():
    """Devuelve la plantilla demo que usa la ventana NASM x64."""
    return PLANTILLA_DEMO


def _recortar(texto, limite=_MAX_SALIDA):
    """Normaliza y recorta la salida de un proceso para mostrarla en la GUI."""
    texto = (texto or "").replace("\r\n", "\n").strip()
    if len(texto) > limite:
        texto = texto[:limite] + "\n... (salida recortada)"
    return texto


def _volcar_salida(lineas, prefijo, texto):
    """Agrega el stdout/stderr de un proceso al log, solo si tiene contenido."""
    texto = _recortar(texto)
    if texto:
        for ln in texto.split("\n"):
            lineas.append(f"   {prefijo} {ln}")


# ======================================================================
#  Ejecucion interactiva (GUI): stdin/stdout en vivo mediante pipes
# ======================================================================
class NasmProceso:
    """Programa NASM x64 ejecutandose de forma interactiva.

    ``on_salida(texto)`` se invoca desde un hilo lector con cada trozo de
    salida (stdout y stderr combinados). La GUI debe reenviarlo al hilo de
    Tk con ``after(0, ...)``.
    """

    def __init__(self, on_salida=None):
        self.on_salida = on_salida if callable(on_salida) else (lambda texto: None)
        self.proc = None
        self.activo = False
        self._gen = 0
        self._hilo = None

    # ------------------------------------------------------------- interno
    def _emitir(self, texto):
        if not texto:
            return
        try:
            self.on_salida(texto)
        except Exception:
            pass  # el callback nunca debe tumbar al lector

    def _terminar_y_esperar(self, espera=1.0):
        """Detiene el proceso actual (si vive) y espera brevemente su cierre."""
        proc = self.proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
            fin = time.time() + espera
            while proc.poll() is None and time.time() < fin:
                time.sleep(0.02)

    def _leer(self, proc, gen):
        """Hilo daemon: bombea la salida del proceso hacia on_salida()."""
        decodificador = codecs.getincrementaldecoder("utf-8")("replace")
        try:
            fd = None
            try:
                if proc.stdout is not None:
                    fd = proc.stdout.fileno()
            except (OSError, ValueError, AttributeError):
                fd = None

            while True:
                try:
                    if fd is not None:
                        trozo = os.read(fd, 4096)
                    else:
                        trozo = proc.stdout.read1(4096)
                except (OSError, ValueError, AttributeError):
                    break
                if not trozo:
                    break
                if gen == self._gen:
                    self._emitir(decodificador.decode(trozo))
                # Si el proceso es de una generacion anterior, se descarta.

            resto = decodificador.decode(b"", final=True)
            if resto and gen == self._gen:
                self._emitir(resto)
        except Exception:
            pass  # cualquier fallo del pipe termina el hilo limpiamente
        finally:
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except (OSError, ValueError):
                pass
            if gen == self._gen:
                self.activo = False
                self._emitir("\n[proceso terminado]\n")

    # -------------------------------------------------------------- publico
    def iniciar(self, src_text):
        """Escribe run.asm, compila, enlaza y arranca run.exe interactivo.

        Devuelve ``(ok, log)``; nunca lanza excepciones hacia la GUI.
        """
        lineas = []
        try:
            self._gen += 1
            gen = self._gen

            # Una compilacion nueva exige cerrar la ejecucion anterior: en
            # Windows run.exe no se puede sobrescribir mientras corre.
            self._terminar_y_esperar()
            self.activo = False
            self.proc = None

            asm_path = os.path.join(_DIR, "run.asm")
            obj_path = os.path.join(_DIR, "run.obj")
            exe_path = os.path.join(_DIR, "run.exe")

            # ----------------------------------------------------- escribir
            try:
                os.makedirs(_DIR, exist_ok=True)
                with open(asm_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(src_text if src_text is not None else "")
            except OSError as exc:
                return False, f"✖ No se pudo escribir run.asm:\n{exc}"

            # Restos de una compilacion anterior: no reutilizar nada viejo.
            for ruta in (obj_path, exe_path):
                try:
                    if os.path.isfile(ruta):
                        os.remove(ruta)
                except OSError:
                    pass

            # ------------------------------------------------------ 1) nasm
            lineas.append("[1/2] nasm -f win64 run.asm -o run.obj")
            try:
                paso = subprocess.run(
                    ["nasm", "-f", "win64", "run.asm", "-o", "run.obj"],
                    cwd=_DIR, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=_TIMEOUT)
            except FileNotFoundError:
                lineas.append("   ✖ nasm no encontrado en PATH. Instala NASM y agregalo al PATH.")
                return False, "\n".join(lineas)
            except subprocess.TimeoutExpired:
                lineas.append(f"   ✖ nasm excedio el tiempo limite ({_TIMEOUT}s).")
                return False, "\n".join(lineas)
            except OSError as exc:
                lineas.append(f"   ✖ No se pudo ejecutar nasm: {exc}")
                return False, "\n".join(lineas)
            if paso.returncode != 0:
                lineas.append(f"   ✖ nasm fallo (codigo {paso.returncode})")
                _volcar_salida(lineas, "|", paso.stdout)
                _volcar_salida(lineas, "|", paso.stderr)
                return False, "\n".join(lineas)
            _volcar_salida(lineas, "|", paso.stdout)
            _volcar_salida(lineas, "|", paso.stderr)
            lineas.append("   → OK: run.obj generado")

            # ------------------------------------------------------- 2) gcc
            lineas.append("[2/2] gcc run.obj -o run.exe")
            try:
                paso = subprocess.run(
                    ["gcc", "run.obj", "-o", "run.exe"],
                    cwd=_DIR, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=_TIMEOUT)
            except FileNotFoundError:
                lineas.append("   ✖ gcc no encontrado en PATH. Instala MinGW-w64 y agregalo al PATH.")
                return False, "\n".join(lineas)
            except subprocess.TimeoutExpired:
                lineas.append(f"   ✖ gcc excedio el tiempo limite ({_TIMEOUT}s).")
                return False, "\n".join(lineas)
            except OSError as exc:
                lineas.append(f"   ✖ No se pudo ejecutar gcc: {exc}")
                return False, "\n".join(lineas)
            if paso.returncode != 0:
                lineas.append(f"   ✖ gcc fallo (codigo {paso.returncode})")
                _volcar_salida(lineas, "|", paso.stdout)
                _volcar_salida(lineas, "|", paso.stderr)
                return False, "\n".join(lineas)
            _volcar_salida(lineas, "|", paso.stdout)
            _volcar_salida(lineas, "|", paso.stderr)
            if not os.path.isfile(exe_path):
                lineas.append("   ✖ gcc no genero run.exe.")
                return False, "\n".join(lineas)
            lineas.append("   → OK: run.exe generado")

            # ------------------------------------------- 3) proceso interactivo
            lineas.append("[3/3] proceso iniciado (entrada interactiva)")
            lineas.append("   → escribe en ENTRADA y presiona Enviar")
            try:
                self.proc = subprocess.Popen(
                    [exe_path], cwd=_DIR,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, bufsize=0)
            except OSError as exc:
                self.proc = None
                lineas.append(f"   ✖ No se pudo ejecutar run.exe: {exc}")
                return False, "\n".join(lineas)

            self.activo = True
            self._hilo = threading.Thread(
                target=self._leer, args=(self.proc, gen), daemon=True)
            self._hilo.start()
            return True, "\n".join(lineas)
        except Exception as exc:  # fail-safe: la GUI nunca debe romperse
            self.activo = False
            return False, f"✖ Error inesperado al iniciar el proceso: {exc}"

    def enviar_linea(self, texto):
        """Envia una linea a stdin del programa. Devuelve True si la acepto."""
        proc = self.proc
        if proc is None or proc.poll() is not None or proc.stdin is None:
            self._emitir("\n[aviso] No hay programa en ejecucion; entrada descartada.\n")
            return False
        # latin-1 conserva byte a byte lo tecleado (numeros, opcion del menu,
        # caracteres de una sola linea para %c) sin fallar.
        datos = (texto if texto is not None else "").encode("latin-1", "replace") + b"\n"
        try:
            proc.stdin.write(datos)
            proc.stdin.flush()
            return True
        except (OSError, ValueError) as exc:
            self._emitir(f"\n[aviso] El proceso ya no acepta entrada: {exc}\n")
            return False

    def detener(self):
        """Termina el proceso si sigue vivo. Nunca lanza excepciones."""
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass


# ======================================================================
#  Ejecucion clasica (no interactiva): toda la salida al final
# ======================================================================
def _pipeline(src_text):
    lineas = []
    asm_path = os.path.join(_DIR, "run.asm")
    obj_path = os.path.join(_DIR, "run.obj")
    exe_path = os.path.join(_DIR, "run.exe")

    # ---------------------------------------------------------------- escribir
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(asm_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(src_text if src_text is not None else "")
    except OSError as exc:
        return False, f"✖ No se pudo escribir run.asm:\n{exc}"

    # Restos de una compilacion anterior: mejor no reutilizar nada viejo.
    for ruta in (obj_path, exe_path):
        try:
            if os.path.isfile(ruta):
                os.remove(ruta)
        except OSError:
            pass

    # ---------------------------------------------------------------- 1) nasm
    lineas.append("[1/3] nasm -f win64 run.asm -o run.obj")
    try:
        paso = subprocess.run(
            ["nasm", "-f", "win64", "run.asm", "-o", "run.obj"],
            cwd=_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=_TIMEOUT)
    except FileNotFoundError:
        lineas.append("   ✖ nasm no encontrado en PATH. Instala NASM y agregalo al PATH.")
        return False, "\n".join(lineas)
    except subprocess.TimeoutExpired:
        lineas.append(f"   ✖ nasm excedio el tiempo limite ({_TIMEOUT}s).")
        return False, "\n".join(lineas)
    except OSError as exc:
        lineas.append(f"   ✖ No se pudo ejecutar nasm: {exc}")
        return False, "\n".join(lineas)
    if paso.returncode != 0:
        lineas.append(f"   ✖ nasm fallo (codigo {paso.returncode})")
        _volcar_salida(lineas, "|", paso.stdout)
        _volcar_salida(lineas, "|", paso.stderr)
        return False, "\n".join(lineas)
    _volcar_salida(lineas, "|", paso.stdout)
    _volcar_salida(lineas, "|", paso.stderr)
    lineas.append("   → OK: run.obj generado")

    # ----------------------------------------------------------------- 2) gcc
    lineas.append("[2/3] gcc run.obj -o run.exe")
    try:
        paso = subprocess.run(
            ["gcc", "run.obj", "-o", "run.exe"],
            cwd=_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=_TIMEOUT)
    except FileNotFoundError:
        lineas.append("   ✖ gcc no encontrado en PATH. Instala MinGW-w64 y agregalo al PATH.")
        return False, "\n".join(lineas)
    except subprocess.TimeoutExpired:
        lineas.append(f"   ✖ gcc excedio el tiempo limite ({_TIMEOUT}s).")
        return False, "\n".join(lineas)
    except OSError as exc:
        lineas.append(f"   ✖ No se pudo ejecutar gcc: {exc}")
        return False, "\n".join(lineas)
    if paso.returncode != 0:
        lineas.append(f"   ✖ gcc fallo (codigo {paso.returncode})")
        _volcar_salida(lineas, "|", paso.stdout)
        _volcar_salida(lineas, "|", paso.stderr)
        return False, "\n".join(lineas)
    _volcar_salida(lineas, "|", paso.stdout)
    _volcar_salida(lineas, "|", paso.stderr)
    if not os.path.isfile(exe_path):
        lineas.append("   ✖ gcc no genero run.exe.")
        return False, "\n".join(lineas)
    lineas.append("   → OK: run.exe generado")

    # ----------------------------------------------------------- 3) ejecutar
    lineas.append("[3/3] ejecutando run.exe")
    try:
        paso = subprocess.run(
            [exe_path], cwd=_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=_TIMEOUT_EJEC)
    except FileNotFoundError:
        lineas.append("   ✖ No se encontro run.exe para ejecutar.")
        return False, "\n".join(lineas)
    except subprocess.TimeoutExpired as exc:
        lineas.append(f"   ✖ run.exe excedio el tiempo limite ({_TIMEOUT_EJEC}s) y fue detenido.")
        salida = exc.stdout
        if isinstance(salida, bytes):
            salida = salida.decode("utf-8", "replace")
        _volcar_salida(lineas, "|", salida)
        return False, "\n".join(lineas)
    except OSError as exc:
        lineas.append(f"   ✖ No se pudo ejecutar run.exe: {exc}")
        return False, "\n".join(lineas)

    combinada = "\n".join(t for t in ((paso.stdout or ""), (paso.stderr or "")) if t.strip())
    lineas.append("   → OK: run.exe termino (codigo %d)" % paso.returncode)
    lineas.append("------ SALIDA ------")
    if combinada.strip():
        lineas.append(_recortar(combinada))
    else:
        lineas.append("(sin salida)")
    lineas.append("--------------------")
    return True, "\n".join(lineas)


def run_asm(src_text):
    """Compila y ejecuta `src_text` como programa NASM x64 (no interactivo).

    Devuelve `(ok, log)`. `log` contiene los pasos [1/3]-[3/3] y la salida
    completa (stdout + stderr) del ejecutable. Nunca lanza excepciones.
    """
    try:
        return _pipeline(src_text)
    except Exception as exc:  # fail-safe: la GUI nunca debe romperse
        return False, f"✖ Error inesperado en el pipeline: {exc}"


def lanzar_consola(src_text):
    """Compila y lanza run.exe en una consola de Windows nueva (CREATE_NEW_CONSOLE).

    Alternativa simple a ``NasmProceso`` para programas con ``scanf``/``printf``:
    la CRT de Windows bufferiza stdout cuando es un pipe, de modo que los
    prompts no se verian en la GUI hasta que el proceso termina. Al abrir una
    consola real, la entrada y la salida funcionan igual que en ``cmd``.

    Devuelve ``(ok, log)``. Si la compilacion falla NO se lanza el exe. El
    proceso lanzado queda vivo aunque la GUI se cierre. Nunca lanza
    excepciones.
    """
    lineas = []
    try:
        asm_path = os.path.join(_DIR, "run.asm")
        obj_path = os.path.join(_DIR, "run.obj")
        exe_path = os.path.join(_DIR, "run.exe")

        # ------------------------------------------------------ escribir
        try:
            os.makedirs(_DIR, exist_ok=True)
            with open(asm_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(src_text if src_text is not None else "")
        except OSError as exc:
            return False, f"✖ No se pudo escribir run.asm:\n{exc}"

        # Restos de una compilacion anterior: no reutilizar nada viejo.
        for ruta in (obj_path, exe_path):
            try:
                if os.path.isfile(ruta):
                    os.remove(ruta)
            except OSError:
                pass

        # --------------------------------------------------- 1) compilar
        lineas.append("[1/2] nasm -f win64 run.asm -o run.obj")
        try:
            paso = subprocess.run(
                ["nasm", "-f", "win64", "run.asm", "-o", "run.obj"],
                cwd=_DIR, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=_TIMEOUT)
        except FileNotFoundError:
            lineas.append("   ✖ nasm no encontrado en PATH. Instala NASM y agregalo al PATH.")
            return False, "\n".join(lineas)
        except subprocess.TimeoutExpired:
            lineas.append(f"   ✖ nasm excedio el tiempo limite ({_TIMEOUT}s).")
            return False, "\n".join(lineas)
        except OSError as exc:
            lineas.append(f"   ✖ No se pudo ejecutar nasm: {exc}")
            return False, "\n".join(lineas)
        if paso.returncode != 0:
            lineas.append(f"   ✖ nasm fallo (codigo {paso.returncode})")
            _volcar_salida(lineas, "|", paso.stdout)
            _volcar_salida(lineas, "|", paso.stderr)
            return False, "\n".join(lineas)
        _volcar_salida(lineas, "|", paso.stdout)
        _volcar_salida(lineas, "|", paso.stderr)
        lineas.append("   → OK: run.obj generado")

        lineas.append("[1/2] gcc run.obj -o run.exe")
        try:
            paso = subprocess.run(
                ["gcc", "run.obj", "-o", "run.exe"],
                cwd=_DIR, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=_TIMEOUT)
        except FileNotFoundError:
            lineas.append("   ✖ gcc no encontrado en PATH. Instala MinGW-w64 y agregalo al PATH.")
            return False, "\n".join(lineas)
        except subprocess.TimeoutExpired:
            lineas.append(f"   ✖ gcc excedio el tiempo limite ({_TIMEOUT}s).")
            return False, "\n".join(lineas)
        except OSError as exc:
            lineas.append(f"   ✖ No se pudo ejecutar gcc: {exc}")
            return False, "\n".join(lineas)
        if paso.returncode != 0:
            lineas.append(f"   ✖ gcc fallo (codigo {paso.returncode})")
            _volcar_salida(lineas, "|", paso.stdout)
            _volcar_salida(lineas, "|", paso.stderr)
            return False, "\n".join(lineas)
        _volcar_salida(lineas, "|", paso.stdout)
        _volcar_salida(lineas, "|", paso.stderr)
        if not os.path.isfile(exe_path):
            lineas.append("   ✖ gcc no genero run.exe.")
            return False, "\n".join(lineas)
        lineas.append("   → OK: run.exe generado")

        # ----------------------------------- 2) lanzar consola nueva
        lineas.append("[2/2] lanzando run.exe en consola nueva")
        try:
            subprocess.Popen(
                [os.path.join(_DIR, "run.exe")], cwd=_DIR,
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except OSError as exc:
            lineas.append(f"   ✖ No se pudo lanzar run.exe: {exc}")
            return False, "\n".join(lineas)

        lineas.append("   → OK: se abrio una ventana de consola; interactua ahi "
                      "(printf/scanf/pause funcionan igual que en cmd)")
        return True, "\n".join(lineas)
    except Exception as exc:  # fail-safe: la GUI nunca debe romperse
        return False, f"✖ Error inesperado al lanzar la consola: {exc}"


if __name__ == "__main__":
    # Prueba manual interactiva: compila la plantilla demo, deja correr 1s y
    # detiene el proceso (la plantilla termina sola; detener es solo red de
    # seguridad para no dejar nada colgado).
    def _imprimir(trozo):
        try:
            print(trozo, end="", flush=True)
        except Exception:
            pass

    print("[manual] compilando PLANTILLA_DEMO con NasmProceso...")
    proceso = NasmProceso(on_salida=_imprimir)
    ok, log = proceso.iniciar(PLANTILLA_DEMO)
    print(log)
    if ok:
        time.sleep(1.0)
        proceso.detener()
        fin = time.time() + 3.0
        while proceso.proc is not None and proceso.proc.poll() is None and time.time() < fin:
            time.sleep(0.05)
        print("[manual] proceso finalizado; activo =", proceso.activo)
    else:
        print("[manual] fallo la compilacion")

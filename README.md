# DLP-ParserStudio

DLP-ParserStudio es un ecosistema educativo en Python para explorar análisis léxico y sintáctico como parte del proyecto final de Diseño de Lenguajes.

El objetivo del proyecto es servir como una base limpia y extensible para construir herramientas relacionadas con analizadores, gramáticas, visualización y experimentación desde consola o desde un IDE web local.

> Estado actual: incluye núcleo de gramáticas, lexer educativo, loaders YAPar/MiniANTLR, analizadores LL(1), LR(0), SLR(1), LALR(1), árboles sintácticos e IDE web simple.

## Estructura

```text
DLP-ParserStudio/
  README.md
  requirements.txt
  pyproject.toml
  src/
    dlp_parserstudio/
      __init__.py
      cli.py
      core/
      lexer/
      parser/
      grammars/
      ide/
  examples/
  tests/
  docs/
```

## Instalación

Desde la raíz del proyecto:

```bash
python3 -m pip install -e ".[dev]"
```

También puedes instalar las dependencias de desarrollo con:

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

## Uso del CLI

```bash
dlp --help
dlp version
dlp ide
```

El IDE web queda disponible por defecto en `http://127.0.0.1:8000`.

También puedes elegir host, puerto y recarga automática:

```bash
dlp ide --host 127.0.0.1 --port 8000 --reload
```

## Ejemplo de conflicto shift/reduce

Para demostrar conflictos y ramas paralelas en la IDE:

1. Ejecuta `dlp ide`.
2. Abre `examples/conflict_shift_reduce.yalex` en el editor YALex.
3. Abre `examples/conflict_shift_reduce.yapar` en el editor YAPar.
4. Usa el input de `examples/conflict_shift_reduce_input.txt`: `id + id + id`.
5. Selecciona `LR(0)` y presiona `Ejecutar`.

La gramática `E : E PLUS E | ID ;` es ambigua para expresiones con `+`. En la sección `Conflictos` debe aparecer un conflicto `shift/reduce`, con el estado, el símbolo `PLUS` y las acciones en conflicto. En `Ramas paralelas` deben aparecer dos caminos exploratorios: una rama que elige `shift` y otra que elige `reduce`, junto con sus pilas, entrada restante y resultado.

## Tests

```bash
pytest
```

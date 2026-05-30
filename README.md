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

## Tests

```bash
pytest
```

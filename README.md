# DLP-ParserStudio

DLP-ParserStudio es un ecosistema educativo en Python para explorar análisis léxico y sintáctico como parte del proyecto final de Diseño de Lenguajes.

El objetivo del proyecto es servir como una base limpia y extensible para construir herramientas relacionadas con analizadores, gramáticas, visualización y experimentación desde consola o desde una futura interfaz de estudio.

> Estado actual: estructura inicial ejecutable. Todavía no se implementan YALex ni YAPar.

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
```

## Tests

```bash
pytest
```

# FutLang

FutLang es un lenguaje propio y educativo para probar el ecosistema de DLP-ParserStudio. Su motivacion es tener una sintaxis pequena, legible y suficiente para ejercicios de analisis lexico y sintactico.

## Caracteristicas

- declaracion de variable: `let energia = 10;`
- asignacion: `energia = energia + 1;`
- impresion: `print energia;`
- `if` simple: `if energia { print energia; }`
- `while` simple: `while energia { energia = energia - 1; }`
- expresiones aritmeticas con `+`, `-`, `*`, `/` y parentesis

## Ejemplo

```futlang
let energia = 10;
energia = energia + 5;
print energia;
if energia { print energia; }
while energia { energia = energia - 1; }
```

Esta gramatica no ejecuta programas; solo valida su forma sintactica.

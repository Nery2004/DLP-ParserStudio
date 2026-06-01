# COW Simplificado

Este ejemplo opcional documenta una mini-gramatica inspirada en lenguajes esotericos tipo COW. El objetivo es probar una lista de instrucciones repetibles, no ejecutar el lenguaje real.

## Comandos

- `moo`
- `mOo`
- `moO`
- `MOO`

## Ejemplo valido

```cow
moo mOo moO MOO
```

La gramatica acepta cualquier secuencia no vacia de comandos validos. Por eso `moo mOo`, `MOO` o `moo mOo moO MOO` son sintacticamente validos.

Los invalidos se dividen en dos casos:

- rechazo lexico: caracteres o palabras fuera del vocabulario, por ejemplo `moo cow`;
- rechazo sintactico: entrada vacia, porque la gramatica exige al menos un comando.

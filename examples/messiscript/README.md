# MessiScript

Este ejemplo modela un subconjunto sintactico educativo de MessiScript, inspirado en el repositorio `Erawaa/MessiScriptInterpreter`.

No implementa el interprete completo ni semantica real. Su objetivo es validar tokenizacion y analisis sintactico con comandos del lenguaje original.

## Subconjunto soportado

- `la agarra messi.` inicia el programa.
- `¡gol!.` termina el programa.
- `encara messi.`
- `ankara messi.`
- `la mueve messi por la derecha.`
- `la mueve messi por la izquierda.`
- `juega messi.`
- `la pisa messi.`
- `corre messi.`
- `amaga messi.`
- `va messi nombre valor.`
- `sigue messi.`
- `vuelve messi.`

Los comandos se separan con punto. `sigue messi.` y `vuelve messi.` se reconocen como marcadores sintacticos de bucle, pero no se ejecuta logica de ciclo.

## IDE

Carga:

- YALex: `examples/messiscript/messiscript.yalex`
- YAPar: `examples/messiscript/messiscript.yapar`
- Input valido: `examples/messiscript/valid_inputs.txt`
- Input invalido: `examples/messiscript/invalid_inputs.txt`

Ejemplo valido:

```messiscript
la agarra messi.
encara messi.
la mueve messi por la derecha.
va messi pelota grande.
juega messi.
¡gol!.
```

Ejemplo invalido:

```messiscript
arranca; gol messi;
```

Ese comando pertenece al ejemplo antiguo inventado y ya no forma parte de la demo principal.

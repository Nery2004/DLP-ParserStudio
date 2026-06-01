# Natural Language Examples

Estos ejemplos muestran como DLP-ParserStudio puede usar lexers y gramaticas pequenas para validar frases naturales muy controladas.

Importante: son gramaticas educativas simplificadas. No modelan la sintaxis completa del espanol ni del q'eqchi', y la traduccion incluida es lexica, palabra por palabra.

## Carpetas para el IDE

Los ejemplos estan separados para que sea facil cargarlos:

- `espanol/lexer.yalex`
- `espanol/grammar.yapar`
- `espanol/valid_inputs.txt`
- `espanol/invalid_inputs.txt`
- `espanol/lexicon.tsv`
- `maya_qeqchi/lexer.yalex`
- `maya_qeqchi/grammar.yapar`
- `maya_qeqchi/valid_inputs.txt`
- `maya_qeqchi/invalid_inputs.txt`
- `maya_qeqchi/lexicon.tsv`

En el IDE, carga `lexer.yalex` en el editor YALex, `grammar.yapar` en YAPar, `valid_inputs.txt` en Input y `lexicon.tsv` en Lexicon.

## Espanol simple

Patron:

```text
consulta -> pregunta sujeto accion objeto
```

Ejemplo valido:

```text
donde estudiante compra libro
```

## Q'eqchi' simplificado

Patrones:

```text
frase -> pregunta sujeto accion objeto
frase -> sujeto accion objeto
```

El vocabulario q'eqchi' se mantiene deliberadamente pequeno y se documenta en `maya_qeqchi/lexicon.tsv`. Las entradas usan una forma practica para el lexer, aceptando apostrofo ASCII (`'`) y apostrofo tipografico (`’`) en las palabras que lo requieren.

Fuente lexica de referencia: Q'eqchi' Talking Dictionary, K'ulb'il Yol Twitz Paxil / The Academy of Mayan Languages, Living Tongues Institute for Endangered Languages.

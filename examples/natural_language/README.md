# Natural Language Examples

Estos ejemplos muestran como DLP-ParserStudio puede usar lexers y gramaticas pequenas para validar frases naturales muy controladas.

Importante: son gramaticas educativas simplificadas. No modelan la sintaxis completa del espanol ni del q'eqchi', y la traduccion incluida es lexica, palabra por palabra.

## Archivos recomendados para el IDE

Para que sea mas facil ubicarlos en la demo, tambien existen copias con nombres descriptivos:

- Espanol: `lenguaje_espanol.yalex`, `lenguaje_espanol.yapar`, `lenguaje_espanol_valid_inputs.txt`, `lenguaje_espanol_invalid_inputs.txt`, `lenguaje_espanol_lexicon.tsv`
- Maya Q'eqchi': `lenguaje_maya_qeqchi.yalex`, `lenguaje_maya_qeqchi.yapar`, `lenguaje_maya_qeqchi_valid_inputs.txt`, `lenguaje_maya_qeqchi_invalid_inputs.txt`, `lenguaje_maya_qeqchi_lexicon.tsv`

Los nombres anteriores se mantienen para no romper pruebas ni documentacion previa.

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

El vocabulario q'eqchi' se mantiene deliberadamente pequeno y se documenta en `qeqchi_lexicon.tsv`. Las entradas usan una forma practica para el lexer, aceptando apostrofo ASCII (`'`) y apostrofo tipografico (`’`) en las palabras que lo requieren.

Fuente lexica de referencia: Q'eqchi' Talking Dictionary, K'ulb'il Yol Twitz Paxil / The Academy of Mayan Languages, Living Tongues Institute for Endangered Languages.

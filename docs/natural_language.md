# Gramaticas de lenguaje natural

Los ejemplos en `examples/natural_language/` son demostraciones educativas para el proyecto. Usan vocabularios cerrados y reglas de orden muy pequenas para ensenar analisis lexico y sintactico.

No son traductores completos ni descripciones linguisticas completas. En particular, el ejemplo q'eqchi':

- usa un vocabulario minimo;
- valida solo frases artificiales del tipo `pregunta sujeto accion objeto` o `sujeto accion objeto`;
- realiza una traduccion lexica palabra por palabra;
- no modela morfologia, concordancia, aspecto, posesion, variantes dialectales ni ordenes reales completos del idioma.

El vocabulario q'eqchi' fue seleccionado especificamente para no usar Kaqchikel/Kakchiquel ni K'iche'/Quiche, y se basa en entradas documentadas del Q'eqchi' Talking Dictionary: https://talkingdictionary.swarthmore.edu/qeqchi/

## Archivos para cargar en la IDE

Espanol:

- YALex: `examples/natural_language/espanol/lexer.yalex`
- YAPar: `examples/natural_language/espanol/grammar.yapar`
- Input: `examples/natural_language/espanol/valid_inputs.txt`
- Lexicon: `examples/natural_language/espanol/lexicon.tsv`

Maya Q'eqchi':

- YALex: `examples/natural_language/maya_qeqchi/lexer.yalex`
- YAPar: `examples/natural_language/maya_qeqchi/grammar.yapar`
- Input demo principal: `examples/natural_language/maya_qeqchi/valid_inputs.txt`
- Mas consultas validas: `examples/natural_language/maya_qeqchi/valid_queries.txt`
- Lexicon: `examples/natural_language/maya_qeqchi/lexicon.tsv`

## Consultas Q'eqchi' verificadas

`valid_inputs.txt` contiene la consulta principal para cargar directamente en la IDE:

```text
b'ar laa'in xnawb'al aatinob'aal
```

Traduccion esperada:

```text
donde yo saber idioma
```

`valid_queries.txt` contiene consultas validas adicionales, una por linea:

- `b'ar laa'in xnawb'al aatinob'aal` -> `donde yo saber idioma`
- `a'an yehok aatinob'aal` -> `el decir idioma`
- `laa'in chalk ochoch` -> `yo venir casa`
- `b'ar a'an b'ichank aatinob'aal` -> `donde el cantar idioma`
- `laa'in xnawb'al xul` -> `yo saber animal`

Los invalidos en `invalid_inputs.txt` cubren orden incorrecto, objeto antes de accion y palabras fuera del vocabulario cerrado.

Para trabajo linguistico real debe consultarse material especializado y hablantes/autoridades de la comunidad linguistica.

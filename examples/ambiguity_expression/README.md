# Ejemplo: ambiguedad en expresiones

Este ejemplo demuestra `Resolver automaticamente` en la IDE.

## Cargar en la IDE

1. YALex: `ambiguous_expression.yalex`
2. YAPar: `ambiguous_expression.yapar`
3. Input: `ambiguous_expression_input.txt`
4. Metodo recomendado: `SLR(1)` o `LR(0)`
5. Presiona `Ejecutar`
6. Presiona `Resolver automaticamente`

La gramatica ambigua no define precedencia entre `PLUS` y `TIMES`. El programa debe reemplazarla por una version con niveles `expr`, `term` y `factor`, y luego volver a ejecutar el analisis.

`resolved_expression.yapar` contiene la version corregida para comparar.

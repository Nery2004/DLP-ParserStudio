# JSX React Subset

Este ejemplo valida un subconjunto educativo de JSX. No interpreta React real, no evalua expresiones JavaScript y no construye componentes; solo verifica una forma sintactica pequena.

Soporta:

- componentes como `<App></App>`
- etiquetas HTML simples como `<div></div>`
- props simples `name="value"`
- texto plano
- anidacion basica
- etiquetas autocerradas como `<Input />`

Limitaciones:

- no valida que la etiqueta de apertura y cierre tengan el mismo nombre;
- no soporta expresiones `{...}`;
- no soporta comentarios JSX;
- no soporta atributos booleanos ni spreads.
- el lexer no tiene estados, asi que en posicion de hijo la gramatica acepta `TAG`, `COMPONENT` o `TEXT` como texto plano.

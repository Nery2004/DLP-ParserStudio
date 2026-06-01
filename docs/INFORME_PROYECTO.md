# Informe del proyecto DLP-ParserStudio

## 1. Descripción general

DLP-ParserStudio es un ecosistema educativo en Python para estudiar análisis léxico y sintáctico en el contexto de Diseño de Lenguajes. El repositorio implementa una base completa para definir tokens, cargar gramáticas, calcular conjuntos FIRST/FOLLOW, construir analizadores LL(1), LR(0), SLR(1) y LALR(1), explorar conflictos, generar árboles sintácticos y visualizar resultados desde una interfaz web simple.

El proyecto está organizado como paquete instalable `dlp-parserstudio`, con código fuente bajo `src/dlp_parserstudio/`, ejemplos bajo `examples/`, pruebas bajo `tests/` y documentación bajo `docs/`.

## 2. Arquitectura del sistema

La arquitectura está dividida en módulos pequeños:

```text
src/dlp_parserstudio/
  cli.py                 CLI principal: dlp version, dlp ide
  core/grammar.py        Modelo formal de gramáticas G = (V, T, P, S)
  lexer/yalex.py         Lexer basado en reglas regex ordenadas
  parser/first_follow.py Cálculo de FIRST y FOLLOW
  parser/yapar_loader.py Loader del formato educativo .yapar
  parser/ll1.py          Tabla LL(1) y parser predictivo
  parser/lr0.py          Items, closure, goto y autómata LR(0)
  parser/slr.py          Tabla ACTION/GOTO SLR(1) y parser
  parser/lalr.py         Items LR(1), fusión LALR(1), tabla y parser
  parser/parallel_conflict.py Exploración de conflictos shift/reduce
  parser/syntax_tree.py  Árbol sintáctico y exportadores
  mini_antlr/loader.py   Subconjunto educativo de ANTLR
  ide/                   FastAPI + frontend HTML/CSS/JS
```

El flujo principal del IDE es:

1. El usuario escribe o carga texto `.yalex`, texto `.yapar` y un input.
2. `ide.analysis.loads_yalex()` convierte reglas simples de YALex en `LexerRule`.
3. `YALexLexer.tokenize()` produce tokens con tipo, lexema, línea y columna.
4. `loads_yapar()` convierte el texto YAPar en una instancia de `Grammar`.
5. `FirstFollowCalculator` calcula FIRST/FOLLOW.
6. Se construye el método seleccionado: LL(1), LR(0), SLR(1) o LALR(1).
7. El resultado se serializa a JSON para mostrar tokens, tablas, pasos, conflictos, ramas paralelas, errores y árbol sintáctico.

El backend web está en `src/dlp_parserstudio/ide/app.py`. Expone:

- `GET /`: sirve el frontend estático.
- `POST /api/analyze`: ejecuta el análisis.

El frontend está en:

- `src/dlp_parserstudio/ide/static/index.html`
- `src/dlp_parserstudio/ide/static/styles.css`
- `src/dlp_parserstudio/ide/static/app.js`

## 3. Decisiones de diseño

El proyecto prioriza claridad educativa sobre optimización extrema. Las decisiones principales son:

- Gramáticas explícitas: `Grammar` modela formalmente `G = (V, T, P, S)` usando `NonTerminal`, `Terminal` y `Production`.
- Compatibilidad bilingüe parcial en nombres de métodos: existen métodos como `agregar_produccion`, `producciones_de`, `aumentar` y equivalentes en inglés como `add_production`, `productions_for`, `augment`.
- Epsilon como producción vacía: YAPar acepta `epsilon`, pero al construir producciones se representa como RHS vacío.
- Fin de entrada como terminal `$`: `parser.first_follow.EOF` es `Terminal("$")`.
- Errores localizados: lexer, YAPar, SLR y LALR conservan línea y columna en errores o tokens.
- Parsers con trazas: LL(1), SLR y LALR retornan pasos con stack, input restante y acción.
- Árbol sintáctico integrado: LL(1), SLR y LALR construyen `SyntaxTree` cuando aceptan.
- IDE simple: el frontend usa HTML/CSS/JS sin framework para mantener bajo el costo de instalación.
- Tests por módulos y ejemplos: las pruebas cubren núcleo, loaders, parsers, lexer, IDE y gramáticas de ejemplo.

## 4. Modelo formal de gramática

El archivo `src/dlp_parserstudio/core/grammar.py` define:

- `Symbol`
- `Terminal`
- `NonTerminal`
- `Production`
- `Grammar`

`Grammar` contiene:

- `non_terminals`: conjunto V.
- `terminals`: conjunto T.
- `productions`: lista P.
- `start_symbol`: símbolo inicial S.

Funciones relevantes:

- `agregar_produccion(lhs, rhs)`: agrega una producción.
- `producciones_de(non_terminal)`: obtiene producciones por no terminal.
- `es_terminal(symbol)` y `es_no_terminal(symbol)`: clasificación de símbolos.
- `aumentar()`: crea una gramática aumentada con `S' -> S`.
- `Grammar.desde_estructura()` / `Grammar.from_dict()`: carga una gramática desde una estructura Python.

La gramática aumentada se usa en LR(0), SLR(1) y LALR(1).

## 5. YALex

El lexer está implementado en `src/dlp_parserstudio/lexer/yalex.py`.

Clases principales:

- `Token(type, lexeme, line, column)`
- `LexerRule(type, pattern, skip=False)`
- `YALexLexer`
- `LexicalError`

Reglas implementadas:

- Las reglas se definen con expresiones regulares de Python.
- La prioridad depende del orden de aparición.
- Se aplica maximal munch: gana el match más largo.
- Si dos reglas empatan en longitud, gana la primera porque `_best_match()` solo reemplaza el match actual cuando encuentra uno más largo.
- Las reglas `skip=True` se reconocen, actualizan posición y no se emiten como tokens.
- Cuando ningún patrón reconoce el carácter actual, se lanza `LexicalError` con línea, columna y carácter.

El IDE agrega un loader textual simple en `src/dlp_parserstudio/ide/analysis.py`:

```text
TOKEN_NAME regex
TOKEN_NAME regex skip
TOKEN_NAME regex -> skip
```

Los ejemplos `.yalex` reales usan ese formato simple. Por ejemplo, `examples/basic_math.yalex`, `examples/jsx_react/jsx_subset.yalex`, `examples/creative_language/futlang.yalex` y `examples/messiscript/messiscript.yalex`.

## 6. YAPar

El loader YAPar está en `src/dlp_parserstudio/parser/yapar_loader.py`.

Formato soportado:

```text
%token ID NUMBER PLUS
%ignore WS
%start expr

%%
expr : term exprp ;
exprp : PLUS term exprp | epsilon ;
term : NUMBER | ID ;
```

Validaciones implementadas:

- Debe existir separador `%%`.
- Debe existir `%start`.
- El símbolo inicial debe tener producción.
- Debe haber al menos una producción después de `%%`.
- Las directivas desconocidas generan error.
- Las producciones deben tener `lhs : rhs ;`.
- `epsilon` debe aparecer solo en una alternativa.
- Todo símbolo usado en RHS debe ser un no terminal definido como LHS o un terminal declarado con `%token`.
- Los errores reportan línea y columna aproximada mediante `YaparLoaderError`.

El loader retorna una instancia de `Grammar`.

## 7. mini-ANTLR

El subconjunto educativo de ANTLR está en `src/dlp_parserstudio/mini_antlr/loader.py`.

Ejemplo real: `examples/calc.mini.g4`.

```antlr
grammar Calc;

expr : term (PLUS term)* ;
term : NUMBER ;

PLUS : '+' ;
NUMBER : [0-9]+ ;
WS : [ \t\r\n]+ -> skip ;
```

Soportes implementados:

- Header `grammar Name;`.
- Reglas lexer identificadas por nombre inicial en mayúscula.
- Reglas parser identificadas por nombre inicial en minúscula.
- Literales entre comillas simples en reglas lexer.
- Regex lexer como `[0-9]+`.
- Acción `-> skip`.
- Alternativas con `|`.
- Grupos simples con `*`, por ejemplo `(PLUS term)*`.

La conversión produce:

- `MiniANTLRSpec.name`
- `MiniANTLRSpec.lexer_rules`
- `MiniANTLRSpec.grammar`

Para grupos con `*`, el loader genera no terminales auxiliares como `expr__repeat_1` y una alternativa epsilon.

Limitaciones reales del loader:

- Solo soporta grupos simples con `*`.
- No soporta `+`, `?`, acciones semánticas, modos lexer, predicados ni gramáticas ANTLR completas.

## 8. FIRST y FOLLOW

El cálculo está en `src/dlp_parserstudio/parser/first_follow.py`.

Elementos:

- `EPSILON = Symbol("epsilon")`
- `EOF = Terminal("$")`
- `FirstFollowCalculator`
- `calculate_first_sets()`
- `calculate_follow_sets()`
- `first_of_sequence()`

Soportes:

- Epsilon con nombres `epsilon`, `eps` o `ε`.
- FOLLOW del símbolo inicial incluye `$`.
- FIRST de secuencias considera propagación de epsilon.
- FOLLOW usa FIRST(beta) y propaga FOLLOW(lhs) cuando beta puede producir epsilon.

## 9. LL(1)

El parser LL(1) está en `src/dlp_parserstudio/parser/ll1.py`.

Componentes:

- `LL1ParsingTable`
- `LL1Conflict`
- `LL1ConflictError`
- `LL1Parser`
- `ParseStep`
- `ParseResult`
- `build_ll1_table()`

La tabla se construye con:

- FIRST de cada lado derecho.
- FOLLOW del LHS cuando FIRST contiene epsilon.

El parser predictivo mantiene una pila con `$` y el símbolo inicial. En cada paso:

- Si el tope es terminal, hace `match`.
- Si el tope es no terminal, consulta la tabla.
- Si no hay entrada, rechaza con error.
- Si llega a `$` con `$`, acepta.

El resultado incluye pasos y, si acepta, un árbol sintáctico.

## 10. LR(0)

El autómata LR(0) está en `src/dlp_parserstudio/parser/lr0.py`.

Componentes:

- `LR0Item`
- `LR0State`
- `LR0Automaton`
- `closure(items, grammar)`
- `goto(state, symbol, grammar)`
- `build_lr0_automaton(grammar)`

El autómata se construye sobre la gramática aumentada `S' -> S`.

`LR0Automaton.to_dot()` exporta el autómata en formato DOT. El IDE muestra estados, transiciones y DOT del autómata LR(0).

Nota de implementación: el módulo `parser/lr0.py` construye items, estados, `closure`, `goto` y autómata. El modo LR(0) del IDE arma una tabla LR(0) educativa dentro de `ide.analysis.py`, usando reducciones LR(0) para todos los terminales y `$`.

## 11. SLR(1)

El parser SLR está en `src/dlp_parserstudio/parser/slr.py`.

Componentes:

- `SLRAction`: `shift`, `reduce`, `accept`, `error`.
- `SLRConflict`: conflicto en celda ACTION.
- `SLRParsingTable`: ACTION/GOTO.
- `SLRParser`.
- `SLRParseResult`.
- `build_slr_table()`.

La tabla SLR se construye con:

1. Autómata LR(0) sobre gramática aumentada.
2. Acciones `shift` desde transiciones por terminal.
3. GOTO desde transiciones por no terminal.
4. Reducciones solo para terminales en FOLLOW(lhs).
5. `accept` para la producción aumentada completa con lookahead `$`.

Detecta:

- `shift/reduce`
- `reduce/reduce`

El parser retorna:

- aceptación o rechazo,
- pasos,
- conflictos,
- errores con token, línea y columna,
- árbol sintáctico si acepta.

## 12. LALR(1)

El parser LALR está en `src/dlp_parserstudio/parser/lalr.py`.

Componentes:

- `LR1Item` con lookahead.
- `LR1State`.
- `LR1Automaton`.
- `LALRAutomaton`.
- `LALRAction`.
- `LALRConflict`.
- `LALRParsingTable`.
- `LALRParser`.
- `closure_lr1()`, `goto_lr1()`, `build_lr1_automaton()`, `build_lalr_automaton()`, `build_lalr_table()`.

Proceso:

1. Normaliza epsilon.
2. Aumenta la gramática.
3. Construye el autómata LR(1) canónico con lookaheads.
4. Fusiona estados que tienen el mismo núcleo LR(0).
5. Construye ACTION/GOTO sobre el autómata fusionado.
6. Registra conflictos si una celda recibe acciones incompatibles.

Ejemplo clásico incluido:

- Archivo: `examples/classic_assignment_lalr.yapar`
- Gramática:

```text
S : L EQUAL R | R ;
L : STAR R | ID ;
R : L ;
```

Las pruebas en `tests/test_lalr.py` verifican que la versión estructural de esta gramática produce conflicto `shift/reduce` en SLR y no produce conflictos en LALR. También verifican parsing y árbol para una asignación `id = id`.

## 13. Análisis paralelo de conflictos

El módulo está en `src/dlp_parserstudio/parser/parallel_conflict.py`.

Objetivo: explorar de manera conceptual qué ocurre cuando una tabla contiene un conflicto `shift/reduce`.

Componentes:

- `ParallelConflictExplorer`
- `ParallelConflictResult`
- `ConflictBranch`
- `ConflictBranchStep`
- `explore_shift_reduce_conflict()`
- `explore_shift_reduce_branches()`

Funcionamiento:

1. Ejecuta el parser hasta encontrar el primer conflicto `shift/reduce` alcanzable.
2. Crea dos ramas:
   - una aplicando `shift`,
   - otra aplicando `reduce`.
3. Ejecuta ambas ramas con `ThreadPoolExecutor`.
4. Cada rama registra stack, input restante, acción elegida, pasos y resultado.

Este modo no reemplaza al parser principal. Se usa como herramienta exploratoria para explicar conflictos.

Las pruebas usan una gramática ambigua:

```text
E -> E + E
E -> id
```

## 14. Árbol sintáctico

El árbol está en `src/dlp_parserstudio/parser/syntax_tree.py`.

Clases:

- `TreeNode(symbol, lexeme, line, column, children)`
- `SyntaxTree(root)`

Exportadores:

- `to_dict()`
- `to_dot()`
- `pretty_print()`

Reglas de construcción implementadas:

- En LL(1), el árbol se construye al expandir producciones y al hacer match de terminales.
- En SLR y LALR, cada `shift` crea un nodo terminal con lexema, línea y columna.
- Cada `reduce` agrupa los últimos nodos como hijos y crea un nodo no terminal.
- El orden de hijos se preserva.

El IDE expone el árbol en tres vistas: JSON, DOT y texto.

## 15. Errores con línea y columna

El proyecto conserva ubicación en varios niveles:

- Lexer: `LexicalError(character, line, column)`.
- Token: cada `Token` tiene `line` y `column`.
- YAPar: `YaparLoaderError` incluye línea y columna.
- SLR: `SLRParseError(token, line, column, message)`.
- LALR: `LALRParseError(token, line, column, message)`.
- IDE: serializa errores con `source`, `message`, `line`, `column` y `token`.

LL(1) retorna errores como texto en `ParseResult.error`; el IDE intenta asociarlos con el token correspondiente cuando es posible.

## 16. IDE web

El IDE permite:

- editar o cargar texto `.yalex`,
- editar o cargar texto `.yapar`,
- escribir o cargar input,
- seleccionar método `LL(1)`, `LR(0)`, `SLR(1)` o `LALR(1)`,
- ejecutar análisis,
- ver tokens,
- ver FIRST/FOLLOW,
- ver autómata LR(0),
- ver tablas,
- ver pasos,
- ver conflictos,
- ver ramas paralelas,
- ver árbol sintáctico en JSON/DOT/texto,
- ver errores con línea y columna.

Archivos:

- Backend: `src/dlp_parserstudio/ide/app.py`
- Análisis: `src/dlp_parserstudio/ide/analysis.py`
- Frontend: `src/dlp_parserstudio/ide/static/`

## 17. Gramáticas de ejemplo

### 17.1 Español simple

Ubicación: `examples/natural_language/espanol/`.

Archivos:

- `lexer.yalex`
- `grammar.yapar`
- `valid_inputs.txt`
- `invalid_inputs.txt`
- `lexicon.tsv`

Patrón:

```text
consulta -> PREGUNTA SUJETO ACCION OBJETO
```

Vocabulario real del lexer:

- `PREGUNTA`: `donde|cuando`
- `SUJETO`: `estudiante|profesor`
- `ACCION`: `compra|lee`
- `OBJETO`: `libro|cuaderno`

Ejemplo documentado:

```text
donde estudiante compra libro
```

La traducción usada en pruebas para español es identidad palabra por palabra.

### 17.2 Q'eqchi' simplificado

Ubicación: `examples/natural_language/maya_qeqchi/`.

Archivos:

- `lexer.yalex`
- `grammar.yapar`
- `valid_inputs.txt`
- `invalid_inputs.txt`
- `lexicon.tsv`

Patrones:

```text
frase -> PREGUNTA SUJETO ACCION OBJETO
frase -> SUJETO ACCION OBJETO
```

El lexer acepta apostrofo ASCII (`'`) y apostrofo tipográfico (`’`) en palabras listadas.

Vocabulario real:

- `PREGUNTA`: `b'ar` / `b’ar`
- `SUJETO`: `laa'in`, `a'an` y variantes con `’`
- `ACCION`: `xnawb'al`, `yehok`, `chalk`, `b'ichank` y variantes con `’`
- `OBJETO`: `aatinob'aal`, `ochoch`, `xul` y variantes con `’`

Traducciones verificadas en tests:

- `b'ar laa'in xnawb'al aatinob'aal` -> `donde yo saber idioma`
- `a'an yehok aatinob'aal` -> `el decir idioma`
- `laa'in chalk ochoch` -> `yo venir casa`

La documentación existente en `docs/natural_language.md` aclara que es una gramática educativa simplificada, no un traductor completo ni una descripción lingüística completa. El vocabulario documenta como referencia el Q'eqchi' Talking Dictionary.

### 17.3 JSX/React educativo

Ubicación: `examples/jsx_react/`.

Archivos:

- `jsx_subset.yalex`
- `jsx_subset.yapar`
- `valid_inputs.txt`
- `invalid_inputs.txt`
- `README.md`

Soporta:

- componentes como `<App></App>`,
- etiquetas como `<div></div>`,
- props simples `name="value"`,
- texto plano,
- anidación básica,
- etiquetas autocerradas como `<Input />`.

El README del ejemplo aclara limitaciones reales:

- no valida que la etiqueta de apertura y cierre tengan el mismo nombre,
- no soporta expresiones `{...}`,
- no soporta comentarios JSX,
- no soporta atributos booleanos ni spreads,
- el lexer no tiene estados.

Las pruebas validan que esta gramática no es LL(1), pero sí se analiza con SLR para el subconjunto definido.

### 17.4 MessiScript

Ubicación: `examples/messiscript/`.

Archivos:

- `messiscript.yalex`
- `messiscript.yapar`
- `valid_inputs.txt`
- `invalid_inputs.txt`
- `README.md`

Comandos definidos:

- `arranca;`
- `gol nombre;`
- `pase origen destino;`
- `marca nombre numero;`
- `grita "texto";`
- `fin;`

La gramática tiene símbolo inicial `script`:

```text
script : ARRANCA SEMI commands FIN SEMI ;
```

Es un lenguaje de validación sintáctica; no interpreta lógica real.

### 17.5 FutLang

Ubicación: `examples/creative_language/`.

Archivos:

- `futlang.yalex`
- `futlang.yapar`
- `valid_inputs.txt`
- `invalid_inputs.txt`
- `README.md`

Características reales:

- declaración de variable: `let energia = 10;`
- asignación: `energia = energia + 1;`
- impresión: `print energia;`
- `if` simple con bloque,
- `while` simple con bloque,
- expresiones aritméticas con `+`, `-`, `*`, `/` y paréntesis.

El README aclara que no ejecuta programas, solo valida forma sintáctica.

### 17.6 COW simplificado

Existe además `examples/cow/` con lexer, gramática, inputs válidos, inputs inválidos y README. Aunque no es parte central del informe solicitado, está incluido en los tests de ejemplos de lenguaje.

## 18. Pruebas

La carpeta `tests/` contiene pruebas unitarias e integración para:

- importación del paquete,
- gramáticas,
- FIRST/FOLLOW,
- YALex,
- YAPar,
- LL(1),
- LR(0),
- SLR(1),
- LALR(1),
- análisis paralelo de conflictos,
- árboles sintácticos,
- mini-ANTLR,
- IDE web,
- ejemplos de lenguaje natural,
- JSX/React,
- FutLang, MessiScript y COW.

Este informe no fija un número de pruebas como resultado permanente. Para conocer el estado real del repositorio en el momento de entrega debe ejecutarse `pytest`.

## 19. Comandos de ejecución

Instalación editable con dependencias de desarrollo:

```bash
python3 -m pip install -e ".[dev]"
```

Instalación usando `requirements.txt`:

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

CLI:

```bash
dlp --help
dlp version
```

IDE web:

```bash
dlp ide
```

Con host, puerto y recarga automática:

```bash
dlp ide --host 127.0.0.1 --port 8000 --reload
```

Por defecto, el IDE queda disponible en:

```text
http://127.0.0.1:8000
```

Pruebas:

```bash
pytest
```

O en modo compacto:

```bash
pytest -q
```

## 20. Capturas sugeridas para el PDF

Estas capturas son sugerencias para documentar el proyecto; no representan resultados inventados.

1. Estructura del repositorio mostrando `src/`, `examples/`, `tests/` y `docs/`.
2. Pantalla inicial del IDE con el ejemplo aritmético por defecto.
3. Carga o edición de un archivo `.yalex`.
4. Carga o edición de un archivo `.yapar`.
5. Ejecución de análisis con método LL(1).
6. Ejecución de análisis con método SLR(1) o LALR(1).
7. Panel de tokens con lexema, tipo, línea y columna.
8. Panel FIRST/FOLLOW.
9. Panel del autómata LR(0), especialmente la salida DOT.
10. Panel de tablas ACTION/GOTO.
11. Panel de pasos de parsing.
12. Panel de conflictos usando una gramática ambigua.
13. Panel de ramas paralelas para un conflicto shift/reduce.
14. Árbol sintáctico en JSON.
15. Árbol sintáctico en DOT o texto.
16. Ejemplo de error léxico con línea y columna.
17. Ejemplo de error sintáctico con línea y columna.
18. Validación de un input de FutLang.
19. Validación de un input JSX/React.
20. Validación y traducción léxica simple de Q'eqchi' según las tablas del ejemplo.

## 21. Conclusiones

DLP-ParserStudio implementa un entorno educativo completo para experimentar con análisis léxico y sintáctico. El diseño modular permite estudiar cada parte de forma separada: lexer, modelo de gramática, loaders, FIRST/FOLLOW, parsers, tablas, autómatas, conflictos y árboles.

El proyecto no intenta ser un compilador de producción ni una implementación completa de YALex, YAPar o ANTLR. Su valor está en hacer visibles los pasos del análisis y en ofrecer ejemplos variados que muestran cómo una misma infraestructura puede validar lenguajes formales pequeños, subconjuntos de lenguajes reales y gramáticas naturales simplificadas.

El IDE web integra las piezas existentes y facilita la demostración del proyecto final: permite modificar reglas, ejecutar distintos métodos, observar tablas y revisar errores sin escribir código adicional.

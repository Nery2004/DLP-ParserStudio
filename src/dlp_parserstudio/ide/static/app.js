const defaults = {
  yalex: `NUMBER    [0-9]+
PLUS      \\+
TIMES     \\*
LPAREN    \\(
RPAREN    \\)
WS        [ \\t\\r\\n]+  skip`,
  yapar: `%token NUMBER PLUS TIMES LPAREN RPAREN
%ignore WS
%start expr

%%
expr : term exprp ;
exprp : PLUS term exprp | epsilon ;
term : factor termp ;
termp : TIMES factor termp | epsilon ;
factor : NUMBER | LPAREN expr RPAREN ;`,
  input: "12 + 7 * 3",
};

const state = {
  lastResult: null,
  treeView: "graph",
  automatonView: "graph",
};

const $ = (id) => document.getElementById(id);

function setDefaults() {
  $("yalex-text").value = defaults.yalex;
  $("yapar-text").value = defaults.yapar;
  $("input-text").value = defaults.input;
  $("lexicon-text").value = "";
}

async function readFileInto(fileInputId, textareaId) {
  const input = $(fileInputId);
  input.addEventListener("change", async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    $(textareaId).value = await file.text();
  });
}

async function runAnalysis() {
  setLoading(true);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        yalex_text: $("yalex-text").value,
        yapar_text: $("yapar-text").value,
        input_text: $("input-text").value,
        method: $("method").value,
        lexicon_text: $("lexicon-text").value,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    state.lastResult = await response.json();
    await render(state.lastResult);
  } catch (error) {
    renderError(error);
  } finally {
    setLoading(false);
  }
}

async function render(result) {
  const accepted = $("accepted-label");
  const status = getResultStatus(result);
  accepted.className = status.className;
  accepted.textContent = status.label;

  const detected = result.format_detected ? `Formato: ${result.format_detected.toUpperCase()}` : "Formato: YAPar";
  $("summary-label").textContent = `${result.method} · ${detected} · ${result.tokens.length} tokens · ${result.steps.length} pasos · ${status.message}`;

  renderHTMLOrEmpty("tokens-output", renderTokensTable(result.tokens));
  renderHTMLOrEmpty("first-follow-output", renderFirstFollowTable(result.first, result.follow));
  renderHTMLOrEmpty("tables-output", renderActionGotoTables(result.tables));
  renderHTMLOrEmpty("steps-output", renderStepsTable(result.steps));
  renderHTMLOrEmpty("conflicts-output", renderConflictsTable(result.conflicts));
  renderHTMLOrEmpty("branches-output", renderBranches(result.parallel_branches, result.parallel_executor));
  renderHTMLOrEmpty("translation-output", renderTranslation(result.translation));
  renderHTMLOrEmpty("errors-output", renderErrorsPanel(result.errors));
  await renderAutomatonPanel();
  await renderTree();
}

function renderTokensTable(tokens) {
  if (!tokens || tokens.length === 0) return null;
  let html = `<table class="parse-table"><thead><tr>`;
  html += `<th>#</th><th>Tipo</th><th>Lexema</th><th>Linea</th><th>Columna</th>`;
  html += `</tr></thead><tbody>`;
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    html += `<tr>`;
    html += `<td>${i + 1}</td>`;
    html += `<td>${escapeHtml(token.type)}</td>`;
    html += `<td><code>${escapeHtml(token.lexeme)}</code></td>`;
    html += `<td>${token.line}</td>`;
    html += `<td>${token.column}</td>`;
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderFirstFollowTable(first, follow) {
  if ((!first || Object.keys(first).length === 0) && (!follow || Object.keys(follow).length === 0)) return null;
  const names = [...new Set([...Object.keys(first || {}), ...Object.keys(follow || {})])].sort();
  let html = `<table class="parse-table"><thead><tr>`;
  html += `<th>No terminal</th><th>FIRST</th><th>FOLLOW</th>`;
  html += `</tr></thead><tbody>`;
  for (const name of names) {
    const firstSet = first && first[name] ? first[name].join(", ") : "";
    const followSet = follow && follow[name] ? follow[name].join(", ") : "";
    html += `<tr>`;
    html += `<td><strong>${escapeHtml(name)}</strong></td>`;
    html += `<td>{ ${escapeHtml(firstSet)} }</td>`;
    html += `<td>{ ${escapeHtml(followSet)} }</td>`;
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderActionGotoTables(tables) {
  if (!tables || (!tables.action && !tables.goto && !tables.ll1 && !tables.reductions)) return null;
  let html = "";

  if (tables.meta) {
    html += renderTableMeta(tables.meta);
  }

  if (tables.action && tables.action.length > 0) {
    html += renderMatrixTable(
      "ACTION",
      tables.action,
      "state",
      "lookahead",
      "action",
      (value) => actionCellClass(value),
    );
  }

  if (tables.goto && tables.goto.length > 0) {
    html += renderMatrixTable("GOTO", tables.goto, "state", "non_terminal", "target");
  }

  if (tables.ll1 && tables.ll1.length > 0) {
    html += renderMatrixTable("Tabla LL(1)", tables.ll1, "non_terminal", "lookahead", "production");
  }

  if (tables.reductions && tables.reductions.length > 0) {
    html += `<h3>Reducciones</h3>`;
    html += `<table class="parse-table"><thead><tr>`;
    html += `<th>Estado</th><th>Lookahead</th><th>Produccion</th><th>Origen</th>`;
    html += `</tr></thead><tbody>`;
    for (const row of tables.reductions) {
      html += `<tr>`;
      html += `<td><strong>${row.state}</strong></td>`;
      html += `<td>${escapeHtml(row.lookahead)}</td>`;
      html += `<td class="cell-reduce">${escapeHtml(row.production)}</td>`;
      html += `<td>${escapeHtml(row.source)}</td>`;
      html += `</tr>`;
    }
    html += `</tbody></table>`;
  }

  return html || null;
}

function renderMatrixTable(title, entries, rowKey, columnKey, valueKey, classForValue = () => "") {
  const rowValues = [...new Set(entries.map((entry) => entry[rowKey]))].sort(sortMixed);
  const columnValues = [...new Set(entries.map((entry) => entry[columnKey]))].sort(sortMixed);
  const values = {};
  for (const entry of entries) {
    values[`${entry[rowKey]},${entry[columnKey]}`] = entry[valueKey];
  }

  let html = `<h3>${escapeHtml(title)}</h3>`;
  html += `<table class="parse-table"><thead><tr><th>${rowKey === "state" ? "Estado" : "No terminal"}</th>`;
  for (const column of columnValues) html += `<th>${escapeHtml(String(column))}</th>`;
  html += `</tr></thead><tbody>`;
  for (const row of rowValues) {
    html += `<tr><td><strong>${escapeHtml(String(row))}</strong></td>`;
    for (const column of columnValues) {
      const value = values[`${row},${column}`];
      const display = value === undefined ? "" : String(value);
      html += `<td class="${classForValue(display)}">${escapeHtml(display)}</td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderTableMeta(meta) {
  const states = Array.isArray(meta.states) ? meta.states.length : meta.state_count || 0;
  const terminals = Array.isArray(meta.terminals) ? meta.terminals.join(", ") : "";
  const nonTerminals = Array.isArray(meta.non_terminals) ? meta.non_terminals.join(", ") : "";
  let html = `<div class="table-meta">`;
  html += `<span><strong>${states}</strong> estados</span>`;
  html += `<span>Terminales: ${escapeHtml(terminals || "-")}</span>`;
  html += `<span>No terminales: ${escapeHtml(nonTerminals || "-")}</span>`;
  html += `<span>Conflictos: <strong>${meta.conflict_count || 0}</strong></span>`;
  html += `</div>`;
  return html;
}

function renderStepsTable(steps) {
  if (!steps || steps.length === 0) return null;
  let html = `<table class="parse-table"><thead><tr>`;
  html += `<th>#</th><th>Pila</th><th>Entrada restante</th><th>Accion</th>`;
  html += `</tr></thead><tbody>`;
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const stack = Array.isArray(step.stack) ? step.stack.join(" ") : step.stack;
    const input = Array.isArray(step.remaining_input) ? step.remaining_input.join(" ") : step.remaining_input;
    const action = step.action || "";
    const cls = action.includes("accept") ? "row-accept" : action.includes("error") ? "row-error" : "";
    html += `<tr class="${cls}">`;
    html += `<td>${i + 1}</td>`;
    html += `<td>${escapeHtml(String(stack || ""))}</td>`;
    html += `<td>${escapeHtml(String(input || ""))}</td>`;
    html += `<td>${escapeHtml(action)}</td>`;
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderConflictsTable(conflicts) {
  if (!conflicts || conflicts.length === 0) return null;
  let html = `<table class="parse-table"><thead><tr>`;
  html += `<th>#</th><th>Tipo</th><th>Estado</th><th>Lookahead</th><th>Existente</th><th>Entrante</th><th>Explicacion</th>`;
  html += `</tr></thead><tbody>`;
  for (let i = 0; i < conflicts.length; i++) {
    const conflict = conflicts[i];
    html += `<tr class="row-error">`;
    html += `<td>${i + 1}</td>`;
    html += `<td>${escapeHtml(conflict.kind || "-")}</td>`;
    html += `<td>${conflict.state !== undefined ? conflict.state : "-"}</td>`;
    html += `<td>${escapeHtml(conflict.lookahead || conflict.non_terminal || "-")}</td>`;
    html += `<td>${escapeHtml(conflict.existing || "-")}</td>`;
    html += `<td>${escapeHtml(conflict.incoming || "-")}</td>`;
    html += `<td>${escapeHtml(conflict.explanation || describeConflict(conflict))}</td>`;
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderErrorsPanel(errors) {
  if (!errors || errors.length === 0) {
    return `<div class="errors-empty-success">Sin errores detectados</div>`;
  }

  const normalized = normalizeErrors(errors);
  const lexerNotice = renderLexerErrorNotice(normalized);
  return `${renderErrorSummary(normalized)}${lexerNotice}${renderErrorsTable(normalized)}`;
}

function renderErrorSummary(errors) {
  const counts = new Map();
  for (const error of errors) {
    counts.set(error.normalizedType, (counts.get(error.normalizedType) || 0) + 1);
  }

  const order = [
    "Lexer Error",
    "Syntax Error",
    "Semantic Error",
    "Grammar Error",
    "Parser Error",
    "Internal Error",
  ];

  let html = `<div class="error-summary">`;
  for (const type of order) {
    const count = counts.get(type) || 0;
    const label = count === 1 ? type : `${type}s`;
    html += `<span class="error-chip error-${getErrorSeverity({ normalizedType: type })}">`;
    html += `<strong>${count}</strong> ${escapeHtml(label)}`;
    html += `</span>`;
  }
  html += `</div>`;
  return html;
}

function renderLexerErrorNotice(errors) {
  const lexical = errors.filter((error) => error.normalizedType === "Lexer Error");
  if (lexical.length === 0) return "";

  const tokens = [...new Set(lexical.map((error) => error.token).filter(Boolean))];
  const tokenText = tokens.length ? ` ${tokens.map((token) => `<code>${escapeHtml(token)}</code>`).join(" ")}` : "";
  return `<div class="lexer-error-notice">El lexer no reconocio estos caracteres del input:${tokenText}</div>`;
}

function renderErrorsTable(errors) {
  let html = `<table class="parse-table"><thead><tr>`;
  html += `<th>#</th><th>Tipo</th><th>Fuente</th><th>Mensaje</th><th>Linea</th><th>Columna</th><th>Token</th>`;
  html += `</tr></thead><tbody>`;
  for (let i = 0; i < errors.length; i++) {
    const error = errors[i];
    const severity = getErrorSeverity(error);
    html += `<tr class="row-error row-error-${severity}">`;
    html += `<td>${i + 1}</td>`;
    html += `<td>${getErrorBadge(error)}</td>`;
    html += `<td>${escapeHtml(error.source || "-")}</td>`;
    html += `<td>${escapeHtml(error.message || "")}</td>`;
    html += `<td>${error.line ?? "-"}</td>`;
    html += `<td>${error.column ?? "-"}</td>`;
    html += `<td>${escapeHtml(error.token || "-")}</td>`;
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function normalizeErrors(errors) {
  const hasLexerErrors = errors.some((error) => normalizeErrorType(error) === "Lexer Error");
  return errors.map((error) => {
    const normalizedType = normalizeErrorType(error);
    const message = error.message || error.mensaje || "";
    const token = error.token || "";
    const isCascade = hasLexerErrors
      && normalizedType === "Syntax Error"
      && (/unexpected token/i.test(message) || token === "$");
    return {
      ...error,
      source: error.source || error.fuente || "-",
      message,
      token,
      normalizedType,
      isCascade,
    };
  });
}

function normalizeErrorType(error) {
  const source = String(error.source || error.fuente || "").toLowerCase();
  const explicitType = String(error.type || error.tipo || "").toLowerCase();
  const message = String(error.message || error.mensaje || "").toLowerCase();

  if (source === "lexer" || explicitType.includes("lexer")) return "Lexer Error";
  if (source === "parser") return "Syntax Error";
  if (source === "semantic" || explicitType.includes("semantic")) return "Semantic Error";
  if (
    ["grammar", "yapar", "antlr", "method"].includes(source)
    || explicitType.includes("grammar")
    || /production|productions|undefined token|token.*undefined|not declared|no definido|conflict|first\/follow|first|follow|grammar|yapar|antlr/.test(message)
  ) {
    return "Grammar Error";
  }
  if (/unexpected token|syntax|parse error|no ll\(1\) production|expected .* found/.test(message)) {
    return "Syntax Error";
  }
  if (/lexical error|unexpected character|caracter inesperado/.test(message)) {
    return "Lexer Error";
  }
  if (source === "internal" || source === "system" || source === "frontend") {
    return "Internal Error";
  }
  if (explicitType.includes("parser")) return "Parser Error";
  return "Internal Error";
}

function getErrorBadge(error) {
  const severity = getErrorSeverity(error);
  const type = error.normalizedType || normalizeErrorType(error);
  const cascade = error.isCascade
    ? `<span class="error-derived">derivado por errores lexicos previos</span>`
    : "";
  return `<span class="error-badge error-${severity}">${escapeHtml(type)}</span>${cascade}`;
}

function getErrorSeverity(error) {
  const type = error.normalizedType || normalizeErrorType(error);
  if (type === "Lexer Error") return "lexer";
  if (type === "Syntax Error") return "syntax";
  if (type === "Semantic Error") return "semantic";
  if (type === "Grammar Error") return "grammar";
  if (type === "Parser Error") return "parser";
  return "internal";
}

function renderBranches(branches, executor) {
  if (!branches || branches.length === 0) return null;
  let html = renderParallelExecutor(executor);
  for (const branch of branches) {
    const isAccepted = branch.result === "accepted";
    const statusClass = isAccepted ? "branch-ok" : "branch-fail";
    const statusLabel = isAccepted
      ? "ACEPTA"
      : branch.result === "rejected"
        ? "RECHAZA"
        : "ERROR";
    html += `<div class="branch ${statusClass}">`;
    html += `<div class="branch-header">`;
    html += `<strong>Rama: ${escapeHtml(String(branch.name || "").toUpperCase())}</strong>`;
    html += `<span class="branch-action">Accion elegida: ${escapeHtml(branch.chosen_action || "-")}</span>`;
    html += `<span class="branch-result">${statusLabel}</span>`;
    html += `</div>`;
    html += `<div class="branch-meta">`;
    html += `<span>Pila final: <code>${escapeHtml(formatList(branch.stack))}</code></span>`;
    html += `<span>Entrada restante: <code>${escapeHtml(formatList(branch.remaining_input))}</code></span>`;
    html += `</div>`;
    html += renderStepsTable(branch.steps) || "";
    if (branch.error) {
      html += `<div class="branch-error">Error: ${escapeHtml(branch.error)}</div>`;
    }
    html += `</div>`;
  }
  return html;
}

function renderParallelExecutor(executor) {
  if (!executor || executor.type === "none") return "";
  let html = `<div class="parallel-executor">`;
  html += `<span>Executor: <strong>${escapeHtml(executor.type)}</strong></span>`;
  html += `<span>${escapeHtml(executor.note || "")}</span>`;
  html += `</div>`;
  return html;
}

function renderTranslation(translation) {
  if (!translation) return null;
  let html = `<div class="translation-summary">`;
  html += `<div class="translation-row"><span class="translation-label">Original:</span>`;
  html += `<span class="translation-value">${escapeHtml(translation.original)}</span></div>`;
  html += `<div class="translation-row"><span class="translation-label">Traduccion:</span>`;
  html += `<span class="translation-value translation-result">${escapeHtml(translation.translated)}</span></div>`;
  html += `</div>`;
  html += `<table class="parse-table"><thead><tr>`;
  html += `<th>#</th><th>Tipo</th><th>Original</th><th>Traduccion</th>`;
  html += `</tr></thead><tbody>`;
  for (let i = 0; i < translation.token_map.length; i++) {
    const entry = translation.token_map[i];
    html += `<tr>`;
    html += `<td>${i + 1}</td>`;
    html += `<td>${escapeHtml(entry.type)}</td>`;
    html += `<td>${escapeHtml(entry.original)}</td>`;
    html += `<td class="cell-accept">${escapeHtml(entry.translated)}</td>`;
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

async function renderAutomatonPanel() {
  const title = $("automaton-title");
  const graph = $("automaton-graph");
  const output = $("automaton-output");
  const automata = collectAutomata();
  if (title) title.textContent = getAutomatonTitle();

  if (automata.length === 0) {
    graph.hidden = true;
    output.hidden = false;
    if (state.lastResult && String(state.lastResult.method || "").toLowerCase().includes("ll")) {
      setTextOutput("automaton-output", "LL(1) no usa automata LR.");
    } else {
      setTextOutput("automaton-output", null);
    }
    return;
  }

  if (state.automatonView === "graph") {
    output.hidden = true;
    graph.hidden = false;
    graph.classList.remove("empty-output");
    graph.innerHTML = await renderGraphGroup(automata);
  } else if (state.automatonView === "dot") {
    graph.hidden = true;
    output.hidden = false;
    setTextOutput(
      "automaton-output",
      automata.map((item) => `# ${item.label}\n${item.automaton.dot}`).join("\n\n"),
    );
  } else {
    graph.hidden = true;
    output.hidden = false;
    output.classList.remove("text-output");
    output.innerHTML = renderAutomatonStates(automata);
    output.classList.remove("empty-output");
  }
}

function collectAutomata() {
  const result = state.lastResult;
  if (!result) return [];
  const method = String(result.method || "").toLowerCase();
  if (method.includes("ll")) return [];

  const automata = [];
  if (method.includes("lr(0)") || method === "lr0") {
    if (result.lr0_automaton) automata.push({ label: "Automata LR(0)", automaton: result.lr0_automaton });
    return automata;
  }
  if (method.includes("slr")) {
    if (result.lr0_automaton) automata.push({ label: "Automata LR(0) usado por SLR(1)", automaton: result.lr0_automaton });
    return automata;
  }
  if (method.includes("lalr")) {
    if (result.lr0_automaton) automata.push({ label: "Automata LR(0) base para comparar", automaton: result.lr0_automaton });
    if (result.lr1_automaton) automata.push({ label: "Automata LR(1) canonico", automaton: result.lr1_automaton });
    if (result.lalr_automaton) automata.push({ label: "Automata LALR(1) fusionado", automaton: result.lalr_automaton });
  }
  return automata;
}

function renderAutomatonStates(automata) {
  let html = "";
  for (const item of automata) {
    html += `<h3>${escapeHtml(item.label)}</h3>`;
    html += `<table class="parse-table"><thead><tr><th>Estado</th><th>Rol</th><th>Items</th></tr></thead><tbody>`;
    for (const stateItem of item.automaton.states || []) {
      html += `<tr>`;
      html += `<td><strong>I${stateItem.id}</strong></td>`;
      html += `<td>${automatonStateTags(stateItem)}</td>`;
      html += `<td>${(stateItem.items || []).map((value) => `<code>${escapeHtml(value)}</code>`).join("<br>")}</td>`;
      html += `</tr>`;
    }
    html += `</tbody></table>`;
  }
  return html;
}

async function renderTree() {
  const tree = state.lastResult && state.lastResult.syntax_tree;
  const graph = $("tree-graph");
  const output = $("tree-output");

  if (!tree) {
    graph.hidden = true;
    output.hidden = false;
    setTextOutput("tree-output", getTreeEmptyMessage());
    return;
  }

  if (state.treeView === "graph") {
    output.hidden = true;
    graph.hidden = false;
    graph.classList.remove("empty-output");
    graph.innerHTML = await renderGraphGroup([{ label: "Arbol sintactico", automaton: { dot: tree.dot } }]);
  } else {
    graph.hidden = true;
    output.hidden = false;
    if (state.treeView === "json") setTextOutput("tree-output", JSON.stringify(tree.json, null, 2));
    else if (state.treeView === "dot") setTextOutput("tree-output", tree.dot || null);
    else setTextOutput("tree-output", tree.text || null);
  }
}

async function renderGraphGroup(items) {
  const viz = await getViz();
  let html = "";
  for (const item of items) {
    html += `<section class="graph-section"><h3>${escapeHtml(item.label)}</h3>`;
    const dot = themeDot(item.automaton.dot || "");
    if (!viz || !dot) {
      html += `<pre>${escapeHtml(item.automaton.dot || "DOT no disponible.")}</pre>`;
    } else {
      try {
        const svg = viz.renderSVGElement(dot);
        svg.removeAttribute("width");
        svg.removeAttribute("height");
        html += svg.outerHTML;
      } catch (error) {
        html += `<pre>${escapeHtml(String(error))}\n\n${escapeHtml(item.automaton.dot)}</pre>`;
      }
    }
    html += `</section>`;
  }
  return html;
}

function themeDot(dot) {
  if (!dot || !dot.includes("{")) return dot;
  return dot.replace(
    "{",
    `{
  graph [bgcolor="transparent", fontcolor="#e5edf8"];
  node [fontcolor="#e5edf8", color="#64748b", fillcolor="#0f172a", style="filled,rounded"];
  edge [color="#64748b", fontcolor="#38bdf8"];`,
  );
}

async function getViz() {
  if (!window.Viz || !window.Viz.instance) return null;
  if (!state.vizInstance) {
    state.vizInstance = await window.Viz.instance();
  }
  return state.vizInstance;
}

function renderHTMLOrEmpty(id, html) {
  const element = $(id);
  if (html) {
    element.innerHTML = html;
    element.classList.remove("empty-output");
    element.classList.remove("text-output");
  } else {
    element.textContent = element.dataset.empty || "Sin resultados.";
    element.classList.add("empty-output");
  }
}

function setTextOutput(id, value) {
  const element = $(id);
  if (isEmpty(value)) {
    element.textContent = element.dataset.empty || "Sin resultados.";
    element.classList.add("empty-output");
    return;
  }
  element.textContent = value;
  element.classList.remove("empty-output");
  element.classList.add("text-output");
}

function isEmpty(value) {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function actionCellClass(value) {
  if (value.includes("conflict")) return "cell-conflict";
  if (value.startsWith("shift")) return "cell-shift";
  if (value.startsWith("reduce")) return "cell-reduce";
  if (value === "accept") return "cell-accept";
  return "";
}

function getResultStatus(result) {
  const errors = normalizeErrors(result.errors || []);
  const types = new Set(errors.map((error) => error.normalizedType));

  if (types.has("Lexer Error")) {
    return { label: "Error lexico", className: "fail", message: "El lexer no pudo reconocer parte del input." };
  }
  if (types.has("Grammar Error")) {
    return { label: "Error gramatical", className: "warn", message: "Revise la definicion de la gramatica." };
  }
  if (types.has("Syntax Error")) {
    return { label: "Error sintactico", className: "fail", message: "La entrada no coincide con la gramatica." };
  }
  if (types.has("Semantic Error")) {
    return { label: "Error semantico", className: "warn", message: "Hay inconsistencias semanticas reportadas." };
  }
  if (types.has("Parser Error") || types.has("Internal Error")) {
    return { label: "Error interno", className: "fail", message: "El parser reporto un problema interno." };
  }
  if (result.conflicts && result.conflicts.length > 0) {
    return { label: "Error gramatical", className: "warn", message: "La tabla contiene conflictos de analisis." };
  }
  if (result.accepted) {
    return { label: "Aceptado", className: "ok", message: "Analisis completado correctamente." };
  }
  return { label: "Rechazado", className: "fail", message: "El parser rechazo la entrada." };
}

function getAutomatonTitle() {
  const method = String((state.lastResult && state.lastResult.method) || "").toLowerCase();
  if (method.includes("ll")) return "LL(1) no usa automata LR";
  if (method.includes("lr(0)") || method === "lr0") return "Automata LR(0)";
  if (method.includes("slr")) return "Automata LR(0) usado por SLR(1)";
  if (method.includes("lalr")) return "Automata LALR(1)";
  return "Automata LR";
}

function getTreeEmptyMessage() {
  if (!state.lastResult) return "No hay arbol sintactico porque el analisis no fue aceptado.";
  if (state.lastResult.accepted) return "El analisis fue aceptado, pero no se genero arbol sintactico.";
  return "No hay arbol sintactico porque el analisis no fue aceptado.";
}

function automatonStateTags(stateItem) {
  const tags = [];
  if (stateItem.is_initial) tags.push("Inicial");
  if (stateItem.has_reduction) tags.push("Reduce");
  if (stateItem.is_accepting) tags.push("Accept");
  if (tags.length === 0) return `<span class="state-tag state-tag-neutral">-</span>`;
  return tags
    .map((tag) => `<span class="state-tag state-tag-${tag.toLowerCase()}">${escapeHtml(tag)}</span>`)
    .join(" ");
}

function describeConflict(conflict) {
  const kind = conflict.kind || "conflict";
  const state = conflict.state !== undefined ? conflict.state : "-";
  const lookahead = conflict.lookahead || conflict.non_terminal || "-";
  if (kind === "shift/reduce") {
    return `En el estado ${state}, con ${lookahead}, la tabla puede desplazar o reducir.`;
  }
  if (kind === "reduce/reduce") {
    return `En el estado ${state}, con ${lookahead}, hay mas de una reduccion posible.`;
  }
  if (kind === "ll1") {
    return `La celda LL(1) tiene mas de una produccion posible.`;
  }
  return `Conflicto en el estado ${state} con ${lookahead}.`;
}

function formatList(values) {
  if (!Array.isArray(values)) return String(values || "-");
  return values.length ? values.join(" ") : "-";
}

function sortMixed(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderError(error) {
  $("accepted-label").className = "fail";
  $("accepted-label").textContent = "Error";
  $("summary-label").textContent = "";
  renderHTMLOrEmpty(
    "errors-output",
    renderErrorsPanel([
      {
        source: "frontend",
        message: String(error),
        line: "-",
        column: "-",
        token: "-",
      },
    ]),
  );
}

function setLoading(isLoading) {
  const runButton = $("run-button");
  document.body.classList.toggle("loading", isLoading);
  runButton.classList.toggle("loading", isLoading);
  runButton.disabled = isLoading;
  runButton.textContent = isLoading ? "Analizando..." : "Ejecutar";
}

function initEmptyOutputs() {
  document.querySelectorAll("[data-empty]").forEach((element) => {
    element.textContent = element.dataset.empty || "Sin resultados.";
    element.classList.add("empty-output");
  });
}

function wireTabs() {
  document.querySelectorAll("[data-tree-view]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.treeView = button.dataset.treeView;
      document.querySelectorAll("[data-tree-view]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      await renderTree();
    });
  });

  document.querySelectorAll("[data-automaton-view]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.automatonView = button.dataset.automatonView;
      document.querySelectorAll("[data-automaton-view]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      await renderAutomatonPanel();
    });
  });
}

function wireDownloads() {
  document.querySelectorAll("[data-save]").forEach((button) => {
    button.addEventListener("click", () => {
      const textareaId = button.dataset.save;
      const filename = button.dataset.filename;
      downloadTextFile(filename, $(textareaId).value);
    });
  });
}

function downloadTextFile(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function boot() {
  setDefaults();
  initEmptyOutputs();
  readFileInto("yalex-file", "yalex-text");
  readFileInto("yapar-file", "yapar-text");
  readFileInto("input-file", "input-text");
  readFileInto("lexicon-file", "lexicon-text");
  wireTabs();
  wireDownloads();
  $("run-button").addEventListener("click", runAnalysis);
}

boot();

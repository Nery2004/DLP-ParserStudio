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
  accepted.className = result.errors.length ? "warn" : result.accepted ? "ok" : "fail";
  accepted.textContent = result.errors.length
    ? "Con errores"
    : result.accepted
      ? "Aceptado"
      : "Rechazado";

  const detected = result.format_detected ? `Formato: ${result.format_detected.toUpperCase()}` : "Formato: YAPar";
  $("summary-label").textContent = `${result.method} · ${detected} · ${result.tokens.length} tokens · ${result.steps.length} pasos`;

  renderHTMLOrEmpty("tokens-output", renderTokensTable(result.tokens));
  renderHTMLOrEmpty("first-follow-output", renderFirstFollowTable(result.first, result.follow));
  renderHTMLOrEmpty("tables-output", renderActionGotoTables(result.tables));
  renderHTMLOrEmpty("steps-output", renderStepsTable(result.steps));
  renderHTMLOrEmpty("conflicts-output", renderConflictsTable(result.conflicts));
  renderHTMLOrEmpty("branches-output", renderBranches(result.parallel_branches));
  renderHTMLOrEmpty("translation-output", renderTranslation(result.translation));
  renderHTMLOrEmpty("errors-output", renderErrorsTable(result.errors));
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
  html += `<th>#</th><th>Tipo</th><th>Estado</th><th>Lookahead</th><th>Existente</th><th>Entrante</th>`;
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
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderErrorsTable(errors) {
  if (!errors || errors.length === 0) return null;
  let html = `<table class="parse-table"><thead><tr>`;
  html += `<th>#</th><th>Fuente</th><th>Mensaje</th><th>Linea</th><th>Columna</th><th>Token</th>`;
  html += `</tr></thead><tbody>`;
  for (let i = 0; i < errors.length; i++) {
    const error = errors[i];
    html += `<tr class="row-error">`;
    html += `<td>${i + 1}</td>`;
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

function renderBranches(branches) {
  if (!branches || branches.length === 0) return null;
  let html = "";
  for (const branch of branches) {
    const isAccepted = branch.result === "accepted";
    const statusClass = isAccepted ? "branch-ok" : "branch-fail";
    const statusLabel = isAccepted ? "EXITO" : "FALLO";
    html += `<div class="branch ${statusClass}">`;
    html += `<div class="branch-header">`;
    html += `<strong>Rama: ${escapeHtml(String(branch.name || "").toUpperCase())}</strong>`;
    html += `<span class="branch-action">Accion elegida: ${escapeHtml(branch.chosen_action || "-")}</span>`;
    html += `<span class="branch-result">${statusLabel}</span>`;
    html += `</div>`;
    html += renderStepsTable(branch.steps) || "";
    if (branch.error) {
      html += `<div class="branch-error">Error: ${escapeHtml(branch.error)}</div>`;
    }
    html += `</div>`;
  }
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
  const graph = $("automaton-graph");
  const output = $("automaton-output");
  const automata = collectAutomata();

  if (automata.length === 0) {
    graph.hidden = true;
    output.hidden = false;
    setTextOutput("automaton-output", null);
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
  const automata = [];
  if (result.lr0_automaton) automata.push({ label: "LR(0) base", automaton: result.lr0_automaton });
  if (result.lr1_automaton) automata.push({ label: "LR(1) canonico", automaton: result.lr1_automaton });
  if (result.lalr_automaton) automata.push({ label: "LALR(1) fusionado", automaton: result.lalr_automaton });
  return automata;
}

function renderAutomatonStates(automata) {
  let html = "";
  for (const item of automata) {
    html += `<h3>${escapeHtml(item.label)}</h3>`;
    html += `<table class="parse-table"><thead><tr><th>Estado</th><th>Items</th></tr></thead><tbody>`;
    for (const stateItem of item.automaton.states || []) {
      html += `<tr>`;
      html += `<td><strong>I${stateItem.id}</strong></td>`;
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
    setTextOutput("tree-output", null);
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
  if (value.startsWith("shift")) return "cell-shift";
  if (value.startsWith("reduce")) return "cell-reduce";
  if (value === "accept") return "cell-accept";
  return "";
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
    renderErrorsTable([
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

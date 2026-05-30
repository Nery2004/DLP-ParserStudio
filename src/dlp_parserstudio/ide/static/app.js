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
  treeView: "json",
};

const $ = (id) => document.getElementById(id);

function setDefaults() {
  $("yalex-text").value = defaults.yalex;
  $("yapar-text").value = defaults.yapar;
  $("input-text").value = defaults.input;
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
  const runButton = $("run-button");
  runButton.disabled = true;
  runButton.textContent = "Ejecutando";

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        yalex_text: $("yalex-text").value,
        yapar_text: $("yapar-text").value,
        input_text: $("input-text").value,
        method: $("method").value,
      }),
    });

    state.lastResult = await response.json();
    render(state.lastResult);
  } catch (error) {
    renderError(error);
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Ejecutar";
  }
}

function render(result) {
  const accepted = $("accepted-label");
  accepted.className = result.accepted ? "ok" : "fail";
  accepted.textContent = result.errors.length
    ? "Con errores"
    : result.accepted
      ? "Aceptado"
      : "Rechazado";
  $("summary-label").textContent = `${result.method} · ${result.tokens.length} tokens · ${result.steps.length} pasos`;

  $("tokens-output").textContent = pretty(result.tokens);
  $("first-follow-output").textContent = pretty({
    FIRST: result.first,
    FOLLOW: result.follow,
  });
  $("automaton-output").textContent = renderAutomaton(result.lr0_automaton);
  $("tables-output").textContent = pretty(result.tables);
  $("steps-output").textContent = pretty(result.steps);
  $("conflicts-output").textContent = pretty(result.conflicts);
  $("branches-output").textContent = pretty(result.parallel_branches);
  $("errors-output").textContent = pretty(result.errors);
  renderTree();
}

function renderAutomaton(automaton) {
  if (!automaton) return "";
  return pretty({
    states: automaton.states,
    transitions: automaton.transitions,
    dot: automaton.dot,
  });
}

function renderTree() {
  const tree = state.lastResult && state.lastResult.syntax_tree;
  if (!tree) {
    $("tree-output").textContent = "";
    return;
  }
  if (state.treeView === "json") {
    $("tree-output").textContent = pretty(tree.json);
  } else if (state.treeView === "dot") {
    $("tree-output").textContent = tree.dot || "";
  } else {
    $("tree-output").textContent = tree.text || "";
  }
}

function renderError(error) {
  $("accepted-label").className = "fail";
  $("accepted-label").textContent = "Error";
  $("summary-label").textContent = "";
  $("errors-output").textContent = String(error);
}

function pretty(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function wireTabs() {
  document.querySelectorAll("[data-tree-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.treeView = button.dataset.treeView;
      document.querySelectorAll("[data-tree-view]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      renderTree();
    });
  });
}

function boot() {
  setDefaults();
  readFileInto("yalex-file", "yalex-text");
  readFileInto("yapar-file", "yapar-text");
  readFileInto("input-file", "input-text");
  wireTabs();
  $("run-button").addEventListener("click", runAnalysis);
}

boot();

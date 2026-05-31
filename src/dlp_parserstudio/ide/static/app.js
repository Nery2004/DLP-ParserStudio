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
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    state.lastResult = await response.json();
    render(state.lastResult);
  } catch (error) {
    renderError(error);
  } finally {
    setLoading(false);
  }
}

function render(result) {
  const accepted = $("accepted-label");
  accepted.className = result.errors.length ? "warn" : result.accepted ? "ok" : "fail";
  accepted.textContent = result.errors.length
    ? "Con errores"
    : result.accepted
      ? "Aceptado"
      : "Rechazado";
  $("summary-label").textContent = `${result.method} · ${result.tokens.length} tokens · ${result.steps.length} pasos`;

  setOutput("tokens-output", result.tokens);
  setOutput("first-follow-output", {
    FIRST: result.first,
    FOLLOW: result.follow,
  });
  setOutput("automaton-output", renderAutomata(result));
  setOutput("tables-output", result.tables);
  setOutput("steps-output", result.steps);
  setOutput("conflicts-output", result.conflicts);
  setOutput("branches-output", result.parallel_branches);
  setOutput("errors-output", result.errors);
  renderTree();
}

function renderAutomata(result) {
  const automata = {};

  if (result.lr0_automaton) {
    automata["LR(0) base"] = renderAutomaton(result.lr0_automaton);
  }
  if (result.lr1_automaton) {
    automata["LR(1) canonico"] = renderAutomaton(result.lr1_automaton);
  }
  if (result.lalr_automaton) {
    automata["LALR(1) fusionado"] = renderAutomaton(result.lalr_automaton);
  }

  return automata;
}

function renderAutomaton(automaton) {
  if (!automaton) return null;
  return {
    kind: automaton.kind,
    states: automaton.states,
    transitions: automaton.transitions,
    dot: automaton.dot,
  };
}

function renderTree() {
  const tree = state.lastResult && state.lastResult.syntax_tree;
  if (!tree) {
    setOutput("tree-output", null);
    return;
  }
  if (state.treeView === "json") {
    setOutput("tree-output", tree.json);
  } else if (state.treeView === "dot") {
    setOutput("tree-output", tree.dot || null);
  } else {
    setOutput("tree-output", tree.text || null);
  }
}

function renderError(error) {
  $("accepted-label").className = "fail";
  $("accepted-label").textContent = "Error";
  $("summary-label").textContent = "";
  setOutput("errors-output", String(error));
}

function pretty(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function isEmpty(value) {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function setOutput(id, value) {
  const element = $(id);
  if (isEmpty(value)) {
    element.textContent = element.dataset.empty || "Sin resultados.";
    element.classList.add("empty-output");
    return;
  }

  element.textContent = pretty(value);
  element.classList.remove("empty-output");
}

function setLoading(isLoading) {
  const runButton = $("run-button");
  document.body.classList.toggle("loading", isLoading);
  runButton.classList.toggle("loading", isLoading);
  runButton.disabled = isLoading;
  runButton.textContent = isLoading ? "Analizando..." : "Ejecutar";
}

function initEmptyOutputs() {
  document.querySelectorAll("pre[id]").forEach((element) => {
    element.textContent = element.dataset.empty || "Sin resultados.";
    element.classList.add("empty-output");
  });
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
  initEmptyOutputs();
  readFileInto("yalex-file", "yalex-text");
  readFileInto("yapar-file", "yapar-text");
  readFileInto("input-file", "input-text");
  wireTabs();
  $("run-button").addEventListener("click", runAnalysis);
}

boot();

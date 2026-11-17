const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function createHarness() {
  const definitions = {};
  const renderers = {};
  const context = vm.createContext({
    qx: {
      Class: { define: (name, definition) => { definitions[name] = definition; } },
      locale: { Manager: { tr: value => value } },
      ui: { table: { Table: class {} } },
    },
    osparc: {
      jobs: { RunsTableModel: class {} },
      store: { Jobs: { getInstance: () => ({}) } },
      ui: {
        switch: { ThemeSwitcher: { isLight: () => true } },
        table: { cellrenderer: {
          ButtonRenderer: class {},
          ImageButtonRenderer: class {
            constructor(action, icon, shouldShow = null) {
              this.__shouldShowFn = shouldShow;
            }
          },
        } },
      },
    },
  });
  for (const file of ["jobs/RunsTable.js", "ui/table/cellrenderer/ImageButtonRenderer.js"]) {
    const sourcePath = path.join(__dirname, "../source/class/osparc", file);
    vm.runInContext(fs.readFileSync(sourcePath, "utf8"), context);
  }
  const definition = definitions["osparc.jobs.RunsTable"];
  definition.construct.call({
    base() {},
    set() {},
    bind() {},
    setTableModel() {},
    self: () => definition.statics,
    getTableColumnModel: () => ({
      setColumnVisible() {},
      setColumnWidth() {},
      setDataCellRenderer: (column, renderer) => { renderers[column] = renderer; },
    }),
    __attachHandlers() {},
  });
  const renderer = renderers[definition.statics.COLS.ACTION_CANCEL.column];
  const render = definitions["osparc.ui.table.cellrenderer.ImageButtonRenderer"].members.createDataCellHtml;
  return state => {
    const html = [];
    render.call({
      __shouldShowFn: renderer.__shouldShowFn,
      base: () => html.push("<button>Cancel</button>"),
    }, { rowData: { state } }, html);
    return html.join("");
  };
}

for (const state of [
  "Running",
  "Queued",
  "Hardware is ready, installing solvers",
  "Creating your personal computing hardware",
  "Finished",
  "Failed",
  "Aborted",
  "Unknown",
  undefined,
]) {
  test(`Activity Center shows Cancel for status ${state}`, () => {
    assert.match(createHarness()(state), /<button>Cancel<\/button>/);
  });
}

test("Activity Center shows Cancel for a localized Running label", () => {
  const localizedLabel = { toString: () => "Running" };
  assert.match(createHarness()(localizedLabel), /<button>Cancel<\/button>/);
});

test("Activity Center shows Cancel for a translated status", () => {
  assert.match(createHarness()("En ejecución"), /<button>Cancel<\/button>/);
});

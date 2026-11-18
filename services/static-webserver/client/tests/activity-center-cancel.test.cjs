/* global require, __dirname */
/* eslint no-underscore-dangle: ["error", { "allow": ["__shouldShowFn", "_loadRowData"] }] */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

/** Loads the row model and Cancel renderer without a browser. */
function createCancelButtonRenderer() {
  const definitions = {};
  const renderers = {};
  const context = vm.createContext({
    qx: {
      Class: { define: (name, definition) => { definitions[name] = definition; } },
      locale: { Manager: { tr: value => value } },
      core: { Object: class {} },
      ui: { table: { Table: class {}, model: { Remote: class {} } } },
    },
    osparc: {
      jobs: { RunsTableModel: class {} },
      data: {},
      store: { Jobs: { getInstance: () => ({}), SERVER_MAX_LIMIT: 49 } },
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
  for (const file of ["data/Job.js", "jobs/RunsTable.js", "jobs/RunsTableModel.js", "ui/table/cellrenderer/ImageButtonRenderer.js"]) {
    const sourcePath = path.join(__dirname, "../source/class/osparc", file);
    vm.runInContext(fs.readFileSync(sourcePath, "utf8"), context);
  }
  const definition = definitions["osparc.jobs.RunsTable"];
  context.osparc.jobs.RunsTable = definition.statics;
  context.osparc.data.Job = definitions["osparc.data.Job"].statics;
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
  /** @param {Object} rowData Table row to render. */
  function renderRow(rowData) {
    const html = [];
    render.call({
      __shouldShowFn: renderer.__shouldShowFn,
      base: () => html.push("<button>Cancel</button>"),
    }, { rowData }, html);
    return html.join("");
  }
  /**
   * @param {string|undefined} rawState Execution state from the API.
   * @param {string|Object} label Translated display label.
   * @param {string|null} projectId Project history filter.
   */
  function loadRow(rawState, label, projectId = null) {
    context.osparc.data.Job.STATUS_LABELS[rawState] = label;
    const job = {
      getCollectionRunId: () => "synthetic-run",
      getProjectIds: () => ["synthetic-project"],
      getName: () => "Test run",
      getState: () => rawState,
      getSubmittedAt: () => null,
      getStartedAt: () => null,
      getEndedAt: () => null,
    };
    const fetchJobs = async () => [job];
    context.osparc.store.Jobs.getInstance = () => ({
      fetchJobsHistory: fetchJobs,
      fetchJobsLatest: fetchJobs,
    });
    return new Promise((resolve, reject) => {
      const model = {
        ...definitions["osparc.jobs.RunsTableModel"].members,
        _rowCount: 1,
        setIsFetching() {},
        getProjectId: () => projectId,
        getOrderBy: () => ({}),
        getFilterString: () => "",
        getRunningOnly: () => true,
        _onRowDataLoaded: rows => rows ? resolve(rows[0]) : reject(new Error("Row loading failed")),
      };
      model._loadRowData(0, 0);
    });
  }
  return { loadRow, renderRow };
}

for (const rawState of ["RUNNING", "STARTED"]) {
  for (const label of ["Running", "En ejecución", { toString: () => "Running" }]) {
    test(`Activity Center shows Cancel for ${rawState} with label ${label}`, async () => {
      const { loadRow, renderRow } = createCancelButtonRenderer();
      const row = await loadRow(rawState, label);
      assert.equal(row.rawState, rawState);
      assert.equal(row.state, label);
      assert.match(renderRow(row), /<button>Cancel<\/button>/);
    });
  }
}

for (const rawState of [
  "PUBLISHED", "PENDING", "WAITING_FOR_RESOURCES", "WAITING_FOR_CLUSTER",
  "SUCCESS", "FAILED", "ABORTED", "NOT_STARTED", "UNKNOWN", undefined,
]) {
  test(`Activity Center hides Cancel for ${rawState} even with a Running display label`, async () => {
    const { loadRow, renderRow } = createCancelButtonRenderer();
    const row = await loadRow(rawState, "Running");
    assert.equal(renderRow(row), "");
  });
}

test("Project history preserves raw state separately from its display label", async () => {
  const { loadRow, renderRow } = createCancelButtonRenderer();
  const row = await loadRow("STARTED", "En ejecución", "synthetic-project");
  assert.equal(row.rawState, "STARTED");
  assert.equal(row.state, "En ejecución");
  assert.match(renderRow(row), /<button>Cancel<\/button>/);
});

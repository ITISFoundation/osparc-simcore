/* global require, __dirname */
/* eslint no-underscore-dangle: ["error", { "allow": ["_loadRowData"] }] */

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
  const imageRenderer = definitions["osparc.ui.table.cellrenderer.ImageButtonRenderer"];
  context.osparc.ui.table.cellrenderer.ImageButtonRenderer = class {
    constructor(...args) {
      this.base = () => {};
      this.setIconPath = () => {};
      imageRenderer.construct.apply(this, args);
    }
  };
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
  /** @param {Object} rowData Table row to render. */
  function countCancelRenderCalls(rowData) {
    let calls = 0;
    renderer.base = () => { calls += 1; };
    imageRenderer.members.createDataCellHtml.call(renderer, { rowData }, []);
    return calls;
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
  return { loadRow, countCancelRenderCalls };
}

for (const rawState of ["RUNNING", "STARTED"]) {
  for (const [labelType, label] of [
    ["English text", "Running"],
    ["Spanish text", "En ejecución"],
    ["a localized string object", { toString: () => "Running" }],
  ]) {
    test(`Activity Center shows Cancel when the state is ${rawState} and the label is ${labelType}`, async () => {
      const { loadRow, countCancelRenderCalls } = createCancelButtonRenderer();
      const row = await loadRow(rawState, label);
      assert.equal(row.state, label);
      assert.equal(countCancelRenderCalls(row), 1);
    });
  }
}

for (const rawState of [
  "PUBLISHED", "PENDING", "WAITING_FOR_RESOURCES", "WAITING_FOR_CLUSTER",
  "SUCCESS", "FAILED", "ABORTED", "NOT_STARTED", "UNKNOWN", undefined,
]) {
  test(`Activity Center hides Cancel when the state is ${rawState ?? "missing"} and the label says Running`, async () => {
    const { loadRow, countCancelRenderCalls } = createCancelButtonRenderer();
    const row = await loadRow(rawState, "Running");
    assert.equal(countCancelRenderCalls(row), 0);
  });
}

test("Project history shows Cancel when an executing run has a translated status label", async () => {
  const { loadRow, countCancelRenderCalls } = createCancelButtonRenderer();
  const row = await loadRow("STARTED", "En ejecución", "synthetic-project");
  assert.equal(row.state, "En ejecución");
  assert.equal(countCancelRenderCalls(row), 1);
});

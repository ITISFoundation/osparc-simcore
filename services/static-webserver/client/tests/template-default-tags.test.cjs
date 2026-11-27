const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const flush = () => new Promise(resolve => setImmediate(resolve));

function createHarness({ billable, selectedTags, returnedTags }) {
  const definitions = {};
  const requests = [];
  const mutations = [];
  const events = {};
  let started = false;
  class StudyOptions {
    setPatchStudy() {}
    setStudyData(data) { this.data = data; }
    getSelectedTags() { return selectedTags; }
    addListener(event, callback) { events[event] = callback; }
    getChildControl(id) {
      switch (id) {
        case "open-button": return { setLabel() {} };
        case "title-field": return { getValue: () => "Template" };
        case "wallet-selector": return { getSelection: () => [] };
        case "study-pricing-units": return { getNodePricingUnits: () => [] };
        default: throw new Error(`Unexpected control: ${id}`);
      }
    }
    static popUpInWindow() {
      return { moveItUp() {}, close() {}, addListener() {}, getChildControl: () => ({ addListener() {} }) };
    }
  }
  const context = vm.createContext({
    console,
    qx: { Class: { define: (name, definition) => { definitions[name] = definition; } } },
    osparc: {
      ui: { basic: { LoadingPageHandler: class {} } },
      product: { Utils: { getStudyAlias: () => "Study" } },
      Preferences: { getInstance: () => ({ getDefaultStudyTagIds: () => [] }) },
      FlashMessenger: { logError: error => { throw error; } },
      data: { model: { Study: { createMinStudyObject: () => ({ tags: [], workbench: {} }) } } },
      widget: { ProgressSequence: { createCreatingStudyProgress: () => ({}) } },
      study: { StudyOptions, StudyPricingUnits: { includeInList: () => false }, Utils: {} },
      store: {
        StaticInfo: { isBillableProduct: () => billable },
        Services: { getStudyServicesMetadata: () => Promise.resolve(), getInaccessibleServices: () => [] },
        Study: { getInstance: () => ({
          createStudyFromTemplate: (id, data) => { requests.push({ id, data }); return Promise.resolve(); },
          addTag: (_id, tag) => { mutations.push(["add", tag]); return Promise.resolve(); },
          removeTag: (_id, tag) => { mutations.push(["remove", tag]); return Promise.resolve(); },
        }) },
        PollTasks: { getInstance: () => ({
          createPollingTask: () => Promise.resolve({
            addListener(event, callback) {
              if (event === "resultReceived") {
                queueMicrotask(() => callback({ getData: () => ({ uuid: "new", name: "Template", tags: returnedTags, workbench: {} }) }));
              }
            },
          }),
        }) },
      },
    },
    queueMicrotask,
  });
  for (const file of ["study/Utils.js", "dashboard/ResourceBrowserBase.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../source/class/osparc", file), "utf8"), context);
  }
  context.osparc.study.Utils = definitions["osparc.study.Utils"].statics;
  const browser = {
    ...definitions["osparc.dashboard.ResourceBrowserBase"].members,
    tr: text => text,
    _checkLoggedIn: () => true,
    _showLoadingPage() {}, _hideLoadingPage() {},
    _startStudyById() { started = true; },
  };
  return { browser, events, requests, mutations, started: () => started, utils: context.osparc.study.Utils };
}

for (const selectedTags of [[], [2]]) {
  test(`Template creation preserves server defaults when selected tags ${selectedTags.length ? "are changed" : "are empty"}`, async () => {
    const ui = createHarness({ billable: true, selectedTags, returnedTags: [...selectedTags, 3] });
    ui.browser._createStudyFromTemplate({ uuid: "template", name: "Template", tags: [1], workbench: {} });
    ui.events.startStudy();
    await flush();
    assert.equal(ui.requests.length, 1);
    assert.deepEqual(Array.from(ui.requests[0].data.tags), selectedTags);
    assert.deepEqual(ui.mutations, []);
    assert.equal(ui.started(), true);
  });
}

test("Template creation omits tag overrides when selected tags are not supplied", async () => {
  const ui = createHarness({ billable: false, returnedTags: [1, 3] });
  const template = { uuid: "template", name: "Template", tags: [1], workbench: {} };
  await ui.utils.createStudyFromTemplate(template, null, { workspaceId: "workspace", folderId: "folder" });
  assert.equal(ui.requests.length, 1);
  assert.equal(Object.hasOwn(ui.requests[0].data, "tags"), false);
  assert.equal(ui.requests[0].data.workspaceId, "workspace");
  assert.equal(ui.requests[0].data.folderId, "folder");
});

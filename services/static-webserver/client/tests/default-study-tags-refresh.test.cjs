const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const flush = () => new Promise(resolve => setImmediate(resolve));

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

function tag(id, name) {
  return { getTagId: () => id, getName: () => name, rename: value => { name = value; } };
}

function setup(initialTags = [], initialFetch = null) {
  const definitions = {};
  const controls = [];
  const errors = [];
  let tags = initialTags;
  let selected = [];
  let nextSave = null;
  let fetchCount = 0;
  class Control {
    constructor(label) { this.label = label; this.children = []; this.listeners = {}; controls.push(this); }
    set(properties) { Object.assign(this, properties); return this; }
    add(child) { this.children.push(child); }
    addListener(event, callback) { this.listeners[event] = callback; }
    getSizeHint() { return { height: this.children.length * 24 }; }
    getValue() { return this.value; }
    setValue(value) { this.value = value; this.listeners.changeValue(); }
    setEnabled(value) { assert.equal(this.disposed, undefined); this.enabled = value; }
    destroy() { this.disposed = true; }
    isDisposed() { return !!this.disposed; }
  }
  class Section extends Control { addHelper() {} }
  class Button extends Control {}
  const preferences = {
    getLowDiskSpaceThreshold: () => false,
    getDefaultStudyTagIds: () => selected,
    setDefaultStudyTagIds: value => { selected = Array.from(value); },
  };
  const tagStore = {
    getTags: () => tags,
    fetchTags: () => { fetchCount++; const fetch = initialFetch; initialFetch = null; return fetch ? fetch.promise : Promise.resolve(tags); },
  };
  const context = vm.createContext({
    console: { error: (...args) => errors.push(args) },
    qx: {
      Class: { define: (name, definition) => { definitions[name] = definition; } },
      ui: {
        core: { Widget: Control },
        container: { Composite: Control, Scroll: class extends Control {
          constructor(content) { super(); this.add(content); }
        } },
        form: { Button, CheckBox: Control },
        layout: { VBox: Control },
        basic: { Label: Control },
      },
    },
    osparc: {
      widget: { SectionBox: Section },
      ui: { window: { TabbedView: Control } },
      product: { Utils: { isLocaleEnabled: () => false, isS4LProduct: () => false, isProduct: () => false, showPreferencesTokens: () => false, getStudyAlias: () => "study" } },
      store: { Tags: { getInstance: () => tagStore }, StaticInfo: { isBillableProduct: () => false } },
      Preferences: {
        getInstance: () => preferences,
        patchPreference: () => nextSave ? nextSave.promise : Promise.resolve(),
      },
      FlashMessenger: { logError: error => errors.push(error) },
      desktop: { preferences: { pages: {} } },
      data: { Permissions: { getInstance: () => ({ canDo: () => true }) } },
      utils: { Utils: { setIdToWidget() {} } },
    },
  });
  for (const file of ["desktop/account/MyAccount.js", "desktop/preferences/pages/GeneralPage.js", "desktop/preferences/pages/TagsPage.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../source/class/osparc", file), "utf8"), context);
  }
  const generalDefinition = definitions["osparc.desktop.preferences.pages.GeneralPage"];
  let general;
  context.osparc.desktop.preferences.pages.GeneralPage = class {
    constructor() {
      general = Object.assign(this, generalDefinition.members, {
        children: [], base() {}, _setLayout() {}, tr: text => text,
        _getChildren() { return this.children; },
        _add(child) { this.children.push(child); },
        _addAt(child, index) { this.children.splice(index, 0, child); },
        _remove(child) { this.children.splice(this.children.indexOf(child), 1); },
        isDisposed() { return !!this.disposed; },
      });
      generalDefinition.construct.call(general);
    }
  };
  const tagsDefinition = definitions["osparc.desktop.preferences.pages.TagsPage"];
  context.osparc.desktop.preferences.pages.TagsPage = class {
    constructor(openSettings) {
      tagsDefinition.construct.call({ base() {}, _setLayout() {}, _add() {}, __renderLayout() {}, tr: text => text }, openSettings);
    }
  };
  const tabs = { listeners: { changeSelection() {} }, addListener(event, callback) { this.listeners[event] = callback; } };
  const account = {
    ...definitions["osparc.desktop.account.MyAccount"].members,
    tr: text => text,
    getChildControl: () => tabs,
    addTab(title) { return { title, getChildControl: () => ({}) }; },
    _openPage(page) { tabs.listeners.changeSelection({ getData: () => [page] }); },
  };
  account.__addGeneralSettings();
  account.__addTagsPage();
  const button = controls.find(control => control instanceof Button && control.label === "Choose default study tags in Settings");
  return {
    general, account, errors,
    setTags: value => { tags = value; },
    setSave: value => { nextSave = value; },
    getFetchCount: () => fetchCount,
    openSettings: () => button.listeners.execute(),
    select: page => tabs.listeners.changeSelection({ getData: () => [page] }),
    checkboxes: () => general.children.flatMap(section => section.children[0].children[0].children),
    selected: () => selected,
  };
}

test("Default study tags show newly created tags when Settings opens from an empty list", async () => {
  const ui = setup();
  await flush();
  assert.equal(ui.general.children.length, 0);
  ui.setTags([tag(1, "First")]);
  ui.openSettings();
  await flush();
  assert.deepEqual(ui.checkboxes().map(item => item.label), ["First"]);
  assert.equal(ui.general.children.length, 1);
});

test("Default study tags show current names and selections when Settings is revisited", async () => {
  const first = tag(1, "Original");
  const ui = setup([first]);
  await flush();
  const originalSection = ui.general.children[0];
  ui.checkboxes()[0].setValue(true);
  await flush();
  first.rename("Renamed");
  ui.setTags([first, tag(2, "Second")]);
  ui.select({ title: "Profile" });
  assert.equal(ui.checkboxes().length, 1);
  ui.select(ui.account.__settingsPage);
  await flush();
  assert.equal(originalSection.disposed, true);
  assert.deepEqual(ui.checkboxes().map(item => [item.label, item.value]), [["Renamed", true], ["Second", false]]);
  ui.openSettings();
  await flush();
  assert.equal(ui.general.children.length, 1);
  assert.equal(ui.getFetchCount(), 1);
  ui.setTags([]);
  ui.select(ui.account.__settingsPage);
  await flush();
  assert.equal(ui.general.children.length, 0);
});

for (const outcome of ["success", "failure"]) {
  test(`Default study tags preserve saved selections when a pending save ends in ${outcome}`, async () => {
    const ui = setup([tag(1, "First")]);
    await flush();
    const save = deferred();
    ui.setSave(save);
    const original = ui.general.children[0];
    ui.checkboxes()[0].setValue(true);
    ui.setTags([tag(1, "First"), tag(2, "Second")]);
    ui.openSettings();
    await flush();
    assert.equal(ui.general.children[0], original);
    if (outcome === "success") {
      save.resolve();
    } else {
      save.reject(new Error("save failed"));
    }
    await flush();
    assert.deepEqual(ui.checkboxes().map(item => item.value), [outcome === "success", false]);
    assert.deepEqual(ui.selected(), outcome === "success" ? [1] : []);
    assert.equal(ui.errors.length, outcome === "failure" ? 1 : 0);
  });
}

test("Default study tags ignore pending work when the page is disposed", async () => {
  const load = deferred();
  const ui = setup([], load);
  ui.openSettings();
  ui.general.disposed = true;
  const tags = [tag(1, "First")];
  ui.setTags(tags);
  load.resolve(tags);
  await flush();
  assert.equal(ui.general.children.length, 0);
  assert.equal(ui.errors.length, 0);
});

for (const outcome of ["success", "failure"]) {
  test(`Default study tags avoid disposed controls when a pending save ends in ${outcome}`, async () => {
    const ui = setup([tag(1, "First")]);
    await flush();
    const save = deferred();
    ui.setSave(save);
    const section = ui.general.children[0];
    const checkbox = ui.checkboxes()[0];
    checkbox.setValue(true);
    ui.openSettings();
    ui.general.disposed = true;
    section.destroy();
    if (outcome === "success") {
      save.resolve();
    } else {
      save.reject(new Error("save failed"));
    }
    await flush();
    assert.equal(section.enabled, false);
    assert.equal(checkbox.value, true);
    assert.deepEqual(ui.selected(), outcome === "success" ? [1] : []);
    assert.equal(ui.errors.length, outcome === "failure" ? 1 : 0);
  });
}

test("Default study tags use the latest tag models when the initial load finishes after Settings opens", async () => {
  const load = deferred();
  const ui = setup([], load);
  const otherSetting = { label: "Other setting" };
  ui.general._add(otherSetting);
  ui.openSettings();
  ui.openSettings();
  assert.equal(ui.getFetchCount(), 1);
  ui.setTags([tag(1, "New")]);
  load.resolve([]);
  await flush();
  assert.equal(ui.general.children.length, 2);
  assert.equal(ui.general.children[0].children[0].children[0].children[0].label, "New");
  assert.equal(ui.general.children[1], otherSetting);
});

test("Default study tags retry loading when the initial fetch fails", async () => {
  const load = deferred();
  const ui = setup([], load);
  load.reject(new Error("load failed"));
  await flush();
  ui.setTags([tag(1, "First")]);
  ui.openSettings();
  await flush();
  assert.equal(ui.getFetchCount(), 2);
  assert.deepEqual(ui.checkboxes().map(item => item.label), ["First"]);
});

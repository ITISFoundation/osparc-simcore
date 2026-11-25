const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

test("Create/Edit Tags opens Settings when the default tags button is clicked", () => {
  const definitions = {};
  const controls = [];
  class Control {
    constructor(label) { this.label = label; this.listeners = {}; controls.push(this); }
    set(values) { Object.assign(this, values); return this; }
    addListener(event, callback) { this.listeners[event] = callback; }
  }
  class Button extends Control {}
  const context = vm.createContext({
    qx: {
      Class: { define: (name, definition) => { definitions[name] = definition; } },
      ui: {
        core: { Widget: Control },
        form: { Button },
        layout: { VBox: Control },
        basic: { Label: Control },
      },
    },
    osparc: {
      ui: { window: { TabbedView: Control }, form: { LinkButton: Control } },
      product: { Utils: { getStudyAlias: () => "study" } },
      desktop: { preferences: { pages: {} } },
      data: { Permissions: { getInstance: () => ({ canDo: () => true }) } },
      utils: { Utils: { setIdToWidget() {} } },
    },
  });
  for (const file of ["desktop/account/MyAccount.js", "desktop/preferences/pages/TagsPage.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../source/class/osparc", file), "utf8"), context);
  }
  const tagsDefinition = definitions["osparc.desktop.preferences.pages.TagsPage"];
  context.osparc.desktop.preferences.pages.GeneralPage = class { getChildrenCount() { return 0; } };
  context.osparc.desktop.preferences.pages.TagsPage = class {
    constructor(openSettings) {
      tagsDefinition.construct.call({
        base() {}, _setLayout() {}, _add() {}, __renderLayout() {}, tr: text => text,
      }, openSettings);
    }
  };
  const account = {
    ...definitions["osparc.desktop.account.MyAccount"].members,
    tr: text => text,
    getChildControl: () => ({ addListener() {} }),
    addTab(title) { return { title, getChildControl: () => ({}) }; },
    _openPage(page) { this.selectedPage = page; },
  };
  account.__addGeneralSettings();
  account.__addTagsPage();

  const button = controls.find(control => control instanceof Button && control.label === "Choose default study tags in Settings");
  assert.ok(button, "The tags page provides a default-tag settings button");
  button.listeners.execute();
  assert.equal(account.selectedPage.title, "Settings");
});

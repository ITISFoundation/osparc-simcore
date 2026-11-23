const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function renderTags(count) {
  let definition;
  const sections = [];
  const updates = [];
  let selected = [];
  class Control {
    constructor(label) { this.label = label; this.children = []; this.listeners = {}; }
    set(properties) { Object.assign(this, properties); return this; }
    add(child) { this.children.push(child); }
    addListener(event, callback) { this.listeners[event] = callback; }
    getSizeHint() { return { height: this.children.length * 24 }; }
    getValue() { return this.value; }
    setEnabled() {}
  }
  class Section extends Control { addHelper() {} }
  const preferences = {
    getDefaultStudyTagIds: () => selected,
    setDefaultStudyTagIds: ids => { selected = ids; },
  };
  const context = vm.createContext({
    qx: {
      Class: { define: (_name, value) => { definition = value; } },
      ui: {
        core: { Widget: Control },
        container: { Composite: Control, Scroll: class extends Control {
          constructor(content) { super(); this.add(content); }
        } },
        form: { CheckBox: Control },
        layout: { VBox: Control },
      },
    },
    osparc: {
      widget: { SectionBox: Section },
      Preferences: {
        getInstance: () => preferences,
        patchPreference: (_key, value) => { updates.push(Array.from(value)); return Promise.resolve(); },
      },
    },
  });
  const file = path.join(__dirname, "../source/class/osparc/desktop/preferences/pages/GeneralPage.js");
  vm.runInContext(fs.readFileSync(file, "utf8"), context);
  const page = { ...definition.members, tr: value => value, _add: section => sections.push(section) };
  const tags = Array.from({ length: count }, (_value, id) => ({ getTagId: () => id, getName: () => `Tag ${id}` }));
  page.__addDefaultStudyTagsSettingContent(tags);
  return { sections, updates };
}

test("Default study tags hide the section when no tags exist", () => {
  assert.equal(renderTags(0).sections.length, 0);
});

test("Default study tags fit the list when there are few tags", () => {
  const { sections } = renderTags(2);
  const scroll = sections[0].children[0];
  assert.equal(scroll.height, 48);
  assert.equal(scroll.children[0].children.length, 2);
});

test("Default study tags limit list height when there are many tags", async () => {
  const { sections, updates } = renderTags(30);
  const scroll = sections[0].children[0];
  assert.equal(scroll.height, 240);
  const checkboxes = scroll.children[0].children;
  assert.equal(checkboxes.length, 30);
  checkboxes[29].value = true;
  checkboxes[29].listeners.changeValue();
  assert.deepEqual(updates, [[29]]);
});

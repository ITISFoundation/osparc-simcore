const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function createHarness() {
  const definitions = {};
  const forms = [];
  const requests = [];
  const previews = [];

  class Control {
    constructor() {
      this.listeners = {};
    }
    set(values) {
      Object.assign(this, values);
      return this;
    }
    getValue() { return this.value; }
    addListener(event, callback) { this.listeners[event] = callback; }
    bind() {}
    add() {}
    open() {}
    close() {}
  }

  class Form {
    constructor() {
      this.items = {};
      this.buttons = [];
      forms.push(this);
    }
    add(control, label, validator, name) { this.items[name] = control; }
    addButton(button) { this.buttons.push(button); }
    getItems() { return this.items; }
    validate() { return true; }
  }

  const context = vm.createContext({
    qx: {
      Class: { define: (name, definition) => { definitions[name] = definition; } },
      locale: { Manager: { tr: value => value } },
      ui: {
        core: { Widget: Control },
        container: { Composite: Control },
        form: {
          Button: Control, CheckBox: Control, Form, Spinner: Control, TextField: Control,
          renderer: { Single: Control },
        },
        layout: { VBox: Control },
      },
    },
    osparc: {
      data: {
        Permissions: { getInstance: () => ({ canDo: () => true }) },
        Resources: {
          fetch: (resource, action, params) => {
            requests.push({ action, data: params.data });
            return Promise.resolve({ messageContent: { subject: "Approved", bodyHtml: "Approved" } });
          },
        },
      },
      FlashMessenger: { logAs() {}, logError(error) { throw error; } },
      po: {
        BaseView: Control,
        PreviewApprovalRejection: class extends Control {
          constructor() {
            super();
            previews.push(this);
          }
        },
      },
      product: { Utils: { getDefaultWelcomeCredits: () => 100 } },
      store: { StaticInfo: { isBillableProduct: () => true } },
      ui: { window: { Window: { popUpInWindow: () => new Control() } } },
    },
  });
  for (const name of ["UsersPending", "PreviewApprovalRejection"]) {
    const sourcePath = path.join(__dirname, "../source/class/osparc/po", `${name}.js`);
    vm.runInContext(fs.readFileSync(sourcePath, "utf8"), context);
  }

  const pendingDefinition = definitions["osparc.po.UsersPending"];
  const pending = { ...pendingDefinition.members, self: () => pendingDefinition.statics };
  const approvalDefinition = definitions["osparc.po.PreviewApprovalRejection"];
  function approvalWidget(values) {
    const widget = { ...approvalDefinition.members, tr: value => value, fireEvent() {} };
    for (const [name, property] of Object.entries(approvalDefinition.properties)) {
      const value = Object.hasOwn(values, name) ? values[name] : property.init;
      widget[`get${name[0].toUpperCase()}${name.slice(1)}`] = () => value;
    }
    widget.getChildControl = () => ({
      getBccEmails: () => [],
      getChildControl: id => id === "subject-field" ? { getValue: () => "Approved" } : {
        composeWholeHtml: () => "Approved", getBodyText: () => "Approved",
      },
    });
    return widget;
  }
  return { approvalWidget, forms, pending, previews, requests };
}

for (const amount of [0, 25, 100]) {
  test(`existing-user approval forwards USD ${amount} through preview and both approval actions`, async () => {
    const harness = createHarness();
    harness.pending.__openApproveDialog({ email: "existing@example.test", registered: true });
    assert.equal(harness.forms.length, 1, "Existing users must get the welcome-credit form");
    const form = harness.forms[0];
    assert.equal(form.items.credits.getValue(), 100, "Use the product's USD default");
    assert.equal(form.items.withExpiration, undefined, "Existing accounts must not get trial controls");
    form.items.credits.set({ value: amount });
    form.buttons[0].listeners.execute();
    await Promise.resolve();

    assert.equal(harness.requests[0].action, "previewApproval");
    assert.equal(harness.requests[0].data.invitation.extraCreditsInUsd, amount || undefined);
    const preview = harness.previews[0];
    assert.equal(preview.invitationUrl, null);
    assert.equal(preview.extraCreditsInUsd, amount || null);

    for (const method of ["__approveWithEmail", "__approveWithoutEmail"]) {
      const widget = harness.approvalWidget(preview);
      widget[method]();
      const request = harness.requests.at(-1);
      assert.equal(request.action, "approveUser");
      assert.equal(request.data.extraCreditsInUsd, amount || null);
      assert.equal(request.data.invitationUrl, null);
      await Promise.resolve();
    }
  });
}

test("new-user approval preserves invitation credits and trial duration", async () => {
  const harness = createHarness();
  harness.pending.__openApproveDialog({ email: "new@example.test", registered: false });
  const form = harness.forms[0];
  form.items.withExpiration.set({ value: true });
  form.items.trialDays.set({ value: 7 });
  form.buttons[0].listeners.execute();
  await Promise.resolve();
  const invitation = harness.requests[0].data.invitation;
  assert.equal(invitation.extraCreditsInUsd, 100);
  assert.equal(invitation.trialAccountDays, 7);
});

test("new-user invitation stays the source of welcome credits", async () => {
  const harness = createHarness();
  harness.pending.__openApprovalPreview(
    "new@example.test",
    "https://example.test/invitation",
    { subject: "Approved", bodyHtml: "Approved" },
    100,
  );
  const preview = harness.previews[0];
  assert.ok(preview.extraCreditsInUsd == null);
  for (const method of ["__approveWithEmail", "__approveWithoutEmail"]) {
    const widget = harness.approvalWidget(preview);
    widget[method]();
    assert.equal(harness.requests.at(-1).data.invitationUrl, "https://example.test/invitation");
    assert.ok(harness.requests.at(-1).data.extraCreditsInUsd == null);
    await Promise.resolve();
  }
});

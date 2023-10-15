/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.ClusterEditor", {
  extend: qx.ui.core.Widget,

  construct: function(newCluster = true) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox(8));

    this.__newCluster = newCluster;

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    const title = this.getChildControl("title");
    title.setRequired(true);
    manager.add(title);
    const endpoint = this.getChildControl("endpoint");
    endpoint.setRequired(true);
    manager.add(endpoint);
    const username = this.getChildControl("simpleAuthenticationUsername");
    username.setRequired(true);
    manager.add(username);
    const pass = this.getChildControl("simpleAuthenticationPassword");
    pass.setRequired(true);
    manager.add(pass);
    this._createChildControlImpl("description");
    this._createChildControlImpl("test-layout");
    newCluster ? this._createChildControlImpl("create") : this._createChildControlImpl("save");
  },

  properties: {
    cid: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCid"
    },

    label: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeLabel"
    },

    endpoint: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeEndpoint"
    },

    simpleAuthenticationUsername: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeSimpleAuthenticationUsername"
    },

    simpleAuthenticationPassword: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeSimpleAuthenticationPassword"
    },

    description: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeDescription"
    }
  },

  events: {
    "createCluster": "qx.event.type.Event",
    "updateCluster": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __validator: null,
    __newCluster: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Title")
          });
          this.bind("label", control, "value");
          control.bind("value", this, "label");
          this._add(control);
          break;
        case "endpointLayout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "endpoint": {
          const endpointLayout = this.getChildControl("endpointLayout");
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Endpoint")
          });
          this.bind("endpoint", control, "value");
          control.bind("value", this, "endpoint");
          control.setRequired(true);
          endpointLayout.add(control, {
            flex: 1
          });
          break;
        }
        case "simpleAuthenticationUsername": {
          const endpointLayout = this.getChildControl("endpointLayout");
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Username")
          });
          control.getContentElement().setAttribute("autocomplete", "off");
          this.bind("simpleAuthenticationUsername", control, "value");
          control.bind("value", this, "simpleAuthenticationUsername");
          control.setRequired(true);
          endpointLayout.add(control);
          break;
        }
        case "simpleAuthenticationPassword": {
          const endpointLayout = this.getChildControl("endpointLayout");
          control = new osparc.ui.form.PasswordField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Password")
          });
          control.getContentElement().setAttribute("autocomplete", "off");
          this.bind("simpleAuthenticationPassword", control, "value");
          control.bind("value", this, "simpleAuthenticationPassword");
          control.setRequired(true);
          endpointLayout.add(control);
          break;
        }
        case "description":
          control = new qx.ui.form.TextArea().set({
            font: "text-14",
            placeholder: this.tr("Description"),
            autoSize: true,
            minHeight: 70,
            maxHeight: 140
          });
          this.bind("description", control, "value");
          control.bind("value", this, "description");
          this._add(control);
          break;
        case "test-layout": {
          control = this.__getTestLayout();
          this._add(control);
          break;
        }
        case "buttonsLayout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
            alignX: "right"
          }));
          const cancelButton = new qx.ui.form.Button(this.tr("Cancel"));
          cancelButton.addListener("execute", () => this.fireEvent("cancel"), this);
          control.add(cancelButton);
          this._add(control);
          break;
        }
        case "create": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Create")).set({
            appearance: "strong-button"
          });
          control.addListener("execute", () => {
            if (this.__validator.validate()) {
              control.setFetching(true);
              this.fireEvent("createCluster");
            }
          }, this);
          buttons.add(control);
          break;
        }
        case "save": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "strong-button"
          });
          control.addListener("execute", () => {
            if (this.__validator.validate()) {
              control.setFetching(true);
              this.fireEvent("updateCluster");
            }
          }, this);
          buttons.add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __getTestLayout: function() {
      const testLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));
      const testButton = new osparc.ui.form.FetchButton(this.tr("Test"));
      testLayout.add(testButton);

      const testResult = new qx.ui.basic.Image("@FontAwesome5Solid/lightbulb/16");
      testLayout.add(testResult);

      testButton.addListener("execute", () => {
        if (this.__validator.validate()) {
          testButton.setFetching(true);
          const endpoint = this.__newCluster ? "pingWCredentials" : "ping";
          const params = {};
          if (this.__newCluster) {
            params["data"] = {
              "endpoint": this.getEndpoint(),
              "authentication": {
                "type": "simple",
                "username": this.getSimpleAuthenticationUsername(),
                "password": this.getSimpleAuthenticationPassword()
              }
            };
          } else {
            params["url"] = {
              cid: this.getCid()
            };
          }
          osparc.data.Resources.fetch("clusters", endpoint, params)
            .then(() => testResult.setTextColor("ready-green"))
            .catch(err => {
              testResult.setTextColor("failed-red");
              const msg = err.message || this.tr("Test failed");
              osparc.FlashMessenger.getInstance().logAs(msg, "Error");
            })
            .finally(() => testButton.setFetching(false));
        }
      }, this);

      return testLayout;
    }
  }
});

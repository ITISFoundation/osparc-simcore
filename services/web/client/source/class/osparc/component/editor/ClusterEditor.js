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

qx.Class.define("osparc.component.editor.ClusterEditor", {
  extend: qx.ui.core.Widget,

  construct: function(newCluster = true) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox(8));

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    const title = this.getChildControl("title");
    title.setRequired(true);
    manager.add(title);
    this._createChildControlImpl("endpoint");
    this._createChildControlImpl("simpleAuthenticationUsername");
    this._createChildControlImpl("simpleAuthenticationPassword");
    this._createChildControlImpl("description");
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
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.form.TextField().set({
            font: "title-14",
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
            placeholder: this.tr("Username"),
            height: 35
          });
          this.bind("simpleAuthenticationUsername", control, "value");
          control.bind("value", this, "simpleAuthenticationUsername");
          control.setRequired(true);
          endpointLayout.add(control);
          break;
        }
        case "simpleAuthenticationPassword": {
          const endpointLayout = this.getChildControl("endpointLayout");
          control = new qx.ui.form.PasswordField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Password"),
            height: 35
          });
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
          control = new osparc.ui.form.FetchButton(this.tr("Create"));
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
          control = new osparc.ui.form.FetchButton(this.tr("Save"));
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
    }
  }
});

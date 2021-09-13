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
    this.getChildControl("description");
    newCluster ? this.getChildControl("create") : this.getChildControl("save");
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
        case "title": {
          control = new qx.ui.form.TextField().set({
            font: "title-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Title"),
            height: 35
          });
          this.bind("label", control, "value");
          control.bind("value", this, "label");
          this._add(control);
          break;
        }
        case "description": {
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
          buttons.addAt(control, 0);
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
          buttons.addAt(control, 0);
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
      }

      return control || this.base(arguments, id);
    }
  }
});

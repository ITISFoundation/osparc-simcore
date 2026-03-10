/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.widget.NodeSlideTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  properties: {
    nodeId: {
      check: "String",
      event: "changeNodeId",
      nullable: false
    },

    position: {
      check: "Number",
      event: "changePosition",
      init: -1,
      nullable: true
    },

    instructions: {
      check: "String",
      event: "changeInstructions",
      nullable: true
    }
  },

  events: {
    "showNode": "qx.event.type.Event",
    "hideNode": "qx.event.type.Event",
    "moveUp": "qx.event.type.Event",
    "moveDown": "qx.event.type.Event",
    "saveInstructions": "qx.event.type.Data"
  },

  members: {
    // overridden
    _addWidgets: function() {
      this.addIcon();
      this.addLabel();
      const label = this.getChildControl("label");
      if (label) {
        label.setMaxWidth(200);
        // override the one set in osparc-theme
        label.setPaddingTop(0);
      }

      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.getChildControl("position-label");
      this.getChildControl("move-up-button");
      this.getChildControl("move-down-button");
      this.getChildControl("hide-button");
      this.getChildControl("show-button");
      this.getChildControl("instructions-button");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "position-label":
          control = new qx.ui.basic.Label().set({
            marginRight: 5,
            alignY: "middle",
          });
          this.bind("position", control, "value", {
            converter: val => (val+1).toString()
          });
          this.bind("position", control, "visibility", {
            converter: val => val > -1 ? "visible" : "excluded"
          });
          this.addWidget(control);
          break;
        case "move-up-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/10").set({
            toolTipText: this.tr("Move up"),
            appearance: "form-button-transparent",
          });
          control.addListener("execute", () => this.fireEvent("moveUp"), this);
          this.bind("position", control, "visibility", {
            converter: val => val > -1 ? "visible" : "excluded"
          });
          this.bind("position", control, "enabled", {
            converter: val => val > 0
          });
          this.addWidget(control);
          break;
        case "move-down-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-down/10").set({
            toolTipText: this.tr("Move down"),
            appearance: "form-button-transparent",
          });
          control.addListener("execute", () => this.fireEvent("moveDown"), this);
          this.bind("position", control, "visibility", {
            converter: val => val > -1 ? "visible" : "excluded"
          });
          this.addWidget(control);
          break;
        case "hide-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye/10").set({
            toolTipText: this.tr("Hide node"),
            marginRight: 5,
            appearance: "form-button-transparent",
            minWidth: 25,
          });
          control.addListener("execute", () => this.fireEvent("hideNode"), this);
          this.bind("position", control, "visibility", {
            converter: val => val > -1 ? "visible" : "excluded"
          });
          this.addWidget(control);
          break;
        case "show-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-slash/10").set({
            toolTipText: this.tr("Show node"),
            marginRight: 5,
            appearance: "form-button-transparent",
            minWidth: 25,
          });
          control.addListener("execute", () => this.fireEvent("showNode"), this);
          this.bind("position", control, "visibility", {
            converter: val => val > -1 ? "excluded" : "visible"
          });
          this.addWidget(control);
          break;
        case "instructions-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/edit/10").set({
            toolTipText: this.tr("Edit Instructions"),
            marginRight: 5,
            appearance: "form-button-transparent",
          });
          control.addListener("execute", () => this.__editInstructions(), this);
          this.bind("position", control, "visibility", {
            converter: val => val > -1 ? "visible" : "hidden"
          });
          this.bind("instructions", control, "opacity", {
            converter: val => val ? 1 : 0.6
          })
          this.addWidget(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __editInstructions: function() {
      const title = this.tr("Edit Instructions");
      const textEditor = new osparc.editor.MarkdownEditor(this.getInstructions());
      textEditor.getChildControl("accept-button").setLabel(this.tr("Save"));
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 500, 300);
      textEditor.addListener("textChanged", e => {
        const newText = e.getData();
        this.fireDataEvent("saveInstructions", newText);
        win.close();
      }, this);
      textEditor.addListener("cancel", () => win.close(), this);
    }
  }
});

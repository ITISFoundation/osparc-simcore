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

      const posLbl = new qx.ui.basic.Label().set({
        marginRight: 5,
        alignY: "middle",
      });
      this.bind("position", posLbl, "value", {
        converter: val => (val+1).toString()
      });
      this.bind("position", posLbl, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(posLbl);

      const moveUpBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/10").set({
        toolTipText: this.tr("Move up"),
        appearance: "form-button-transparent",
      });
      moveUpBtn.addListener("execute", () => this.fireEvent("moveUp"), this);
      this.bind("position", moveUpBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.bind("position", moveUpBtn, "enabled", {
        converter: val => val > 0
      });
      this.addWidget(moveUpBtn);

      const moveDownBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-down/10").set({
        toolTipText: this.tr("Move down"),
        appearance: "form-button-transparent",
      });
      moveDownBtn.addListener("execute", () => this.fireEvent("moveDown"), this);
      this.bind("position", moveDownBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(moveDownBtn);

      const hideBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye/10").set({
        toolTipText: this.tr("Hide node"),
        marginRight: 5,
        appearance: "form-button-transparent",
        minWidth: 25,
      });
      hideBtn.addListener("execute", () => this.fireEvent("hideNode"), this);
      this.bind("position", hideBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(hideBtn);

      const showBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-slash/10").set({
        toolTipText: this.tr("Show node"),
        marginRight: 5,
        appearance: "form-button-transparent",
        minWidth: 25,
      });
      showBtn.addListener("execute", () => this.fireEvent("showNode"), this);
      this.bind("position", showBtn, "visibility", {
        converter: val => val > -1 ? "excluded" : "visible"
      });
      this.addWidget(showBtn);

      const editInstructionsBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/edit/10").set({
        toolTipText: this.tr("Edit Instructions"),
        marginRight: 5,
        appearance: "form-button-transparent",
      });
      editInstructionsBtn.addListener("execute", () => this.__editInstructions(), this);
      this.bind("position", editInstructionsBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "hidden"
      });
      this.addWidget(editInstructionsBtn);
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

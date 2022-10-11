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

qx.Class.define("osparc.component.widget.NodeSlideTreeItem", {
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
    }
  },

  events: {
    "showNode": "qx.event.type.Event",
    "hideNode": "qx.event.type.Event",
    "moveUp": "qx.event.type.Event",
    "moveDown": "qx.event.type.Event"
  },

  members: {
    // overridden
    _addWidgets: function() {
      this.addIcon();
      this.addLabel();
      const label = this.getChildControl("label");
      if (label) {
        label.setMaxWidth(150);
      }

      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const posLbl = new qx.ui.basic.Label().set({
        marginRight: 5
      });
      this.bind("position", posLbl, "value", {
        converter: val => (val+1).toString()
      });
      this.bind("position", posLbl, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(posLbl);

      const moveUpBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/10").set({
        appearance: "no-shadow-button"
      });
      moveUpBtn.addListener("execute", () => this.fireEvent("moveUp"), this);
      this.bind("position", moveUpBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(moveUpBtn);

      const moveDownBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-down/10").set({
        appearance: "no-shadow-button"
      });
      moveDownBtn.addListener("execute", () => this.fireEvent("moveDown"), this);
      this.bind("position", moveDownBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(moveDownBtn);

      const hideBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye/10").set({
        marginRight: 5,
        appearance: "no-shadow-button"
      });
      hideBtn.addListener("execute", () => this.fireEvent("hideNode"), this);
      this.bind("position", hideBtn, "visibility", {
        converter: val => val > -1 ? "visible" : "excluded"
      });
      this.addWidget(hideBtn);

      const showBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-slash/10").set({
        marginRight: 5,
        appearance: "no-shadow-button"
      });
      showBtn.addListener("execute", () => this.fireEvent("showNode"), this);
      this.bind("position", showBtn, "visibility", {
        converter: val => val > -1 ? "excluded" : "visible"
      });
      this.addWidget(showBtn);
    }
  }
});

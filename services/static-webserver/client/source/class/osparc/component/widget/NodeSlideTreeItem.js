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
    nodeId : {
      check : "String",
      event: "changeNodeId",
      nullable : true
    },

    position: {
      check: "Number",
      event: "changePosition",
      apply: "_applyPosition",
      init: -1,
      nullable: true
    },

    skipNode: {
      check: "Boolean",
      event: "changeSkipNode",
      apply: "_applySkipNode",
      init: false,
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
      this.addSpacer();
      this.addOpenButton();
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
        converter: val => {
          if (val === null) {
            return "";
          }
          return (val+1).toString();
        }
      });
      this.bind("skipNode", posLbl, "visibility", {
        converter: val => val ? "excluded" : "visible"
      });
      this.addWidget(posLbl);

      const hideBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye/10").set({
        marginRight: 5,
        appearance: "no-shadow-button"
      });
      hideBtn.addListener("execute", () => {
        this.fireEvent("showNode");
      }, this);
      this.bind("skipNode", hideBtn, "visibility", {
        converter: val => {
          if (val === null) {
            return "excluded";
          }
          if (val === true) {
            return "excluded";
          }
          return "visible";
        }
      });
      this.addWidget(hideBtn);

      const showBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-slash/10").set({
        marginRight: 5,
        appearance: "no-shadow-button"
      });
      showBtn.addListener("execute", () => {
        this.fireEvent("hideNode");
      }, this);
      this.bind("skipNode", showBtn, "visibility", {
        converter: val => {
          if (val === null) {
            return "excluded";
          }
          if (val === false) {
            return "excluded";
          }
          return "visible";
        }
      });
      this.addWidget(showBtn);

      const moveUpBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/10").set({
        appearance: "no-shadow-button"
      });
      moveUpBtn.addListener("execute", () => {
        this.fireEvent("moveUp");
      }, this);
      this.bind("position", moveUpBtn, "visibility", {
        converter: val => {
          if (val === null) {
            return "excluded";
          }
          return "visible";
        }
      });
      this.addWidget(moveUpBtn);

      const moveDownBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-down/10").set({
        appearance: "no-shadow-button"
      });
      moveDownBtn.addListener("execute", () => {
        this.fireEvent("moveDown");
      }, this);
      this.bind("position", moveDownBtn, "visibility", {
        converter: val => {
          if (val === null) {
            return "excluded";
          }
          return "visible";
        }
      });
      this.addWidget(moveDownBtn);

      if (osparc.data.Permissions.getInstance().canDo("study.nodestree.uuid.read")) {
        const nodeIdWidget = new qx.ui.basic.Label().set({
          alignX: "right",
          minWidth: 260,
          maxWidth: 260
        });
        this.bind("nodeId", nodeIdWidget, "value");
        this.addWidget(nodeIdWidget);
      }
    },

    _applyPosition: function(val) {
      if (val === null) {
        return;
      }
    },

    _applySkipNode: function(val) {
      if (val === null) {
        return;
      }
    }
  }
});

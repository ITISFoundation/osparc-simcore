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
  extend: osparc.component.widget.NodeTreeItem,

  properties: {
    position: {
      check: "Number",
      event: "changePosition",
      apply: "_applyPosition",
      nullable: true
    },

    skipNode: {
      check: "Boolean",
      event: "changeSkipNode",
      apply: "_applySkipNode",
      nullable: true
    }
  },

  events: {
    "moveUp": "qx.event.type.Event",
    "moveDown": "qx.event.type.Event"
  },

  members: {
    // overriden
    _addWidgets: function() {
      this.addSpacer();
      this.addOpenButton();
      this.addIcon();
      this.addLabel();

      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const posLbl = new qx.ui.basic.Label();
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

      const hideBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-slash/10");
      hideBtn.addListener("execute", () => this.setSkipNode(true), this);
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

      const showBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye/10");
      showBtn.addListener("execute", () => this.setSkipNode(false), this);
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

      const moveUpBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/10");
      moveUpBtn.addListener("execute", () => this.fireEvent("moveUp"), this);
      this.addWidget(moveUpBtn);

      const moveDownBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-down/10");
      moveDownBtn.addListener("execute", () => this.fireEvent("moveDown"), this);
      this.addWidget(moveDownBtn);

      if (false && osparc.data.Permissions.getInstance().canDo("study.nodestree.uuid.read")) {
        const nodeIdWidget = new qx.ui.basic.Label();
        this.bind("nodeId", nodeIdWidget, "value");
        nodeIdWidget.setMaxWidth(250);
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

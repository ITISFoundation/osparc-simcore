/* ************************************************************************

   qxapp - the simcore frontent

   https://simcore.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Class.define("qxapp.component.widget.NodeTreeItem", {
  extend : qx.ui.tree.VirtualTreeItem,

  properties : {
    nodeId : {
      check : "String",
      event: "changeNodeId",
      nullable : true
    }
  },

  members : {
    _addWidgets : function() {
      // Here's our indentation and tree-lines
      this.addSpacer();
      this.addOpenButton();

      // The standard tree icon follows
      this.addIcon();

      // The label
      this.addLabel();

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // Add a NodeId
      var nodeIdWidget = new qx.ui.basic.Label();
      this.bind("nodeId", nodeIdWidget, "value");
      nodeIdWidget.setMaxWidth(250);
      this.addWidget(nodeIdWidget);
    }
  }
});

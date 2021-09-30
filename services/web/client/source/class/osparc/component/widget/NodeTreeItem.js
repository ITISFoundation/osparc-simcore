/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

/**
 * VirtualTreeItem used mainly by NodesTree
 *
 *   It consists of an entry icon, label and Node id
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new osparc.component.widget.NodeTreeItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindDefaultProperties(item, id);
 *       c.bindProperty("label", "label", null, item, id);
 *       c.bindProperty("nodeId", "nodeId", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeTreeItem", {
  extend : qx.ui.tree.VirtualTreeItem,

  properties : {
    nodeId : {
      check : "String",
      event: "changeNodeId",
      apply: "_applyNodeId",
      nullable : true
    }
  },

  members : {
    _addWidgets: function() {
      // Here's our indentation and tree-lines
      this.addSpacer();
      this.addOpenButton();

      // The standard tree icon follows
      this.addIcon();

      // The label
      this.addLabel();
      const label = this.getChildControl("label");
      if (label) {
        label.setMaxWidth(150);
      }

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // Add a NodeId
      const nodeIdWidget = new qx.ui.basic.Label();
      this.bind("nodeId", nodeIdWidget, "value");
      nodeIdWidget.set({
        maxWidth: 250
      });
      this.addWidget(nodeIdWidget);
      const permissions = osparc.data.Permissions.getInstance();
      nodeIdWidget.setVisibility(permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded");
      permissions.addListener("changeRole", () => {
        nodeIdWidget.setVisibility(permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded");
      });
    },

    _applyNodeId: function(nodeId) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      if (nodeId === study.getUuid()) {
        osparc.utils.Utils.setIdToWidget(this, "nodeTreeItem_root");
      } else {
        osparc.utils.Utils.setIdToWidget(this, "nodeTreeItem_" + nodeId);
      }
    }
  }
});

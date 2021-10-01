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
  extend: qx.ui.tree.VirtualTreeItem,

  properties: {
    nodeId : {
      check : "String",
      event: "changeNodeId",
      apply: "_applyNodeId",
      nullable : true
    }
  },

  events: {
    "openNode": "qx.event.type.Data",
    "renameNode": "qx.event.type.Data",
    "deleteNode": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "buttons": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(0).set({
            alignY: "middle"
          }));
          this.addWidget(control);
          break;
        }
        case "open-btn": {
          const part = this.getChildControl("buttons");
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("openNode"),
            icon: "@FontAwesome5Solid/edit/9"
          });
          control.addListener("execute", () => this.fireDataEvent("openNode", this.getNodeId()));
          part.add(control);
          break;
        }
        case "rename-btn": {
          const part = this.getChildControl("buttons");
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("renameNode"),
            icon: "@FontAwesome5Solid/i-cursor/9"
          });
          control.addListener("execute", () => this.fireDataEvent("renameNode", this.getNodeId()));
          part.add(control);
          break;
        }
        case "delete-btn": {
          const part = this.getChildControl("buttons");
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("deleteNode"),
            icon: "@FontAwesome5Solid/trash/9"
          });
          control.addListener("execute", () => this.fireDataEvent("deleteNode", this.getNodeId()));
          part.add(control);
          break;
        }
        case "node-id": {
          control = new qx.ui.basic.Label().set({
            maxWidth: 250
          });
          this.bind("nodeId", control, "value", {
            converter: value => value && value.substring(0, 8)
          });
          const permissions = osparc.data.Permissions.getInstance();
          control.setVisibility(permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded");
          permissions.addListener("changeRole", () => {
            control.setVisibility(permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded");
          });
          this.addWidget(control);
        }
      }

      return control || this.base(arguments, id);
    },

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

      this.getChildControl("open-btn");
      this.getChildControl("rename-btn");
      this.getChildControl("delete-btn");
      this.getChildControl("node-id");
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

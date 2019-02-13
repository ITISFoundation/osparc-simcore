/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *   Widget used for displaying an output port data of an input node. It contains a VirtualTree
 * populated with NodeOutputTreeItems.
 *
 * It is meant to fit "node-output-tree-api" input/output port type
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputTree(node, port, portKey);
 *   widget = nodeOutputList.getOutputWidget();
 *   this.getRoot().add(widget);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.inputs.NodeOutputTree", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param port {Object} Port owning the widget
    * @param portKey {String} Port Key
  */
  construct: function(node, port, portKey) {
    this.base();

    this.setNode(node);

    let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children");

    let that = this;
    tree.setDelegate({
      createItem: () => new qxapp.component.widget.inputs.NodeOutputTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
      },
      configureItem: item => {
        item.set({
          isDir: !portKey.includes("modeler") && !portKey.includes("sensorSettingAPI") && !portKey.includes("neuronsSetting"),
          nodeKey: node.getKey(),
          portKey: portKey
        });
        that.__createDragMechanism(item); // eslint-disable-line no-underscore-dangle
      }
    });

    const itemList = qxapp.data.Store.getInstance().getItemList(node.getKey(), portKey);
    const showAsDirs = !portKey.includes("modeler") && !portKey.includes("sensorSettingAPI") && !portKey.includes("neuronsSetting");
    const children = qxapp.data.Converters.fromAPITreeToVirtualTreeModel(itemList, showAsDirs);
    let data = {
      label: port.label,
      children: children
    };
    let model = qx.data.marshal.Json.createModel(data, true);
    tree.setModel(model);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __tree: null,

    __createDragMechanism: function(item) {
      item.setDraggable(true);
      item.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");
        // Register supported types
        e.addType("osparc-mapping");
      });
    },

    getOutputWidget: function() {
      return this.__tree;
    }
  }
});

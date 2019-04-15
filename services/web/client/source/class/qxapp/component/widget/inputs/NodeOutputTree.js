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
 * populated with NodeOutputTreeItems. It implements Drag mechanism.
 *
 * It is meant to fit "node-output-tree-api" input/output port type
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutputTree = new qxapp.component.widget.inputs.NodeOutputTree(node, port, portKey);
 *   widget = nodeOutputTree.getOutputWidget();
 *   this.getRoot().add(widget);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.inputs.NodeOutputTree", {
  extend: qx.ui.tree.VirtualTree,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param port {Object} Port owning the widget
    * @param portKey {String} Port Key
  */
  construct: function(node, ports) {
    const model = this.__generateModel(node, ports);

    this.base(arguments, model, "label", "children", "open");

    this.set({
      node,
      ports,
      decorator: "service-tree",
      hideRoot: true,
      contentPadding: 0
    });

    const self = this;
    this.setDelegate({
      createItem: () => new qxapp.component.widget.inputs.NodeOutputTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("value", "value", null, item, id);
        c.bindProperty("nodeKey", "nodeKey", null, item, id);
        c.bindProperty("portKey", "portKey", null, item, id);
        c.bindProperty("isDir", "isDir", null, item, id);
      },
      configureItem: item => {
        item.setDraggable(true);
        self.__attachEventHandlers(item); // eslint-disable-line no-underscore-dangle
      }
    });
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },
    ports: {
      nullable: false
    }
  },

  members: {
    __attachEventHandlers: function(item) {
      item.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");
        // Register supported types
        e.addType("osparc-port-link");
        item.nodeId = this.getNode().getNodeId();
        item.portId = item.getPortKey();
      }, this);

      const msgCb = decoratorName => msg => {
        this.getSelection().remove(item.getModel());
        const compareFn = msg.getData();
        if (decoratorName && compareFn(this.getNode().getNodeId(), item.getPortKey())) {
          item.setDecorator(decoratorName);
        } else {
          item.resetDecorator();
        }
      };
      item.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("inputFocus", msgCb("outputPortHighlighted"), this);
        qx.event.message.Bus.getInstance().subscribe("inputFocusout", msgCb(), this);
      });
      item.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("inputFocus", msgCb("outputPortHighlighted"), this);
        qx.event.message.Bus.getInstance().unsubscribe("inputFocusout", msgCb(), this);
      });
    },

    __generateModel: function(node, ports) {
      let data = {
        label: "root",
        children: []
      };

      for (let portKey in ports) {
        let portData = {
          label: ports[portKey].label,
          portKey: portKey,
          nodeKey: node.getKey(),
          isDir: !(portKey.includes("modeler") || portKey.includes("sensorSettingAPI") || portKey.includes("neuronsSetting"))
        };
        if (portKey.includes("modeler") || portKey.includes("sensorSettingAPI") || portKey.includes("neuronsSetting")) {
          const itemList = qxapp.data.Store.getInstance().getItemList(node.getKey(), portKey);
          const children = qxapp.data.Converters.fromAPITreeToVirtualTreeModel(itemList);
          portData.children = children;
          portData.open = true;
        } else {
          portData.value = ports[portKey].value || this.tr("no value");
        }
        data.children.push(portData);
      }

      return qx.data.marshal.Json.createModel(data, true);
    },

    getOutputWidget: function() {
      return this;
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

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
 *   let nodeOutputTree = new osparc.component.widget.inputs.NodeOutputTree(node, port);
 *   widget = nodeOutputTree.getOutputWidget();
 *   this.getRoot().add(widget);
 * </pre>
 */

qx.Class.define("osparc.component.widget.inputs.NodeOutputTree", {
  extend: qx.ui.tree.VirtualTree,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    * @param port {Object} Port owning the widget
  */
  construct: function(node, ports) {
    const model = this.__generateModel(node, ports);

    this.base(arguments, model, "label", "children", "open");

    this.set({
      node,
      ports,
      decorator: "service-tree",
      hideRoot: true,
      contentPadding: 0,
      padding: 0,
      minHeight: 0
    });

    const self = this;
    this.setDelegate({
      createItem: () => new osparc.component.widget.inputs.NodeOutputTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("value", "value", null, item, id);
        c.bindProperty("nodeKey", "nodeKey", null, item, id);
        c.bindProperty("portKey", "portKey", null, item, id);
        c.bindProperty("isDir", "isDir", null, item, id);
        c.bindProperty("icon", "icon", null, item, id);
        c.bindProperty("type", "type", null, item, id);
        c.bindProperty("open", "open", null, item, id);
      },
      configureItem: item => {
        item.setDraggable(true);
        self.__attachEventHandlers(item); // eslint-disable-line no-underscore-dangle
      }
    });

    node.addListener("outputChanged", e => {
      const portKey = e.getData();
      const outValue = node.getOutput(portKey);
      this.getModel().getChildren()
        .forEach(treeItem => {
          if (treeItem.getPortKey() === portKey) {
            treeItem.setValue(qx.data.marshal.Json.createModel(outValue.value));
          }
        });
    }, this);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
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
        e.addType("osparc-mapping");
        item.nodeId = this.getNode().getNodeId();
        item.portId = item.getPortKey();
        item.setNodeKey(this.getNode().getKey());
      }, this);

      const msgCb = decoratorName => msg => {
        this.getSelection().remove(item.getModel());
        const compareFn = msg.getData();
        if (item.getPortKey() && decoratorName && compareFn(this.getNode().getNodeId(), item.getPortKey())) {
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
      const nodeKey = node.getKey();

      const data = {
        label: "root",
        open: true,
        children: []
      };

      for (let portKey in ports) {
        const port = ports[portKey];
        console.log(port.label, port.value);

        const portData = {
          label: port.label,
          nodeKey,
          portKey: portKey,
          isDir: !(portKey.includes("modeler") || portKey.includes("sensorSettingAPI") || portKey.includes("neuronsSetting")),
          type: port.type,
          open: false
        };
        if (port.type === "node-output-tree-api-v0.0.1") {
          const itemList = osparc.dev.fake.Data.getItemList(nodeKey, portKey);
          const showLeavesAsDirs = !(portKey.includes("modeler") || portKey.includes("sensorSettingAPI") || portKey.includes("neuronsSetting"));
          const children = osparc.data.Converters.fromAPITreeToVirtualTreeModel(itemList, showLeavesAsDirs, portKey);
          portData.children = children;
          portData.open = true;
        } else if (Array.isArray(port.value)) {
          const children = [];
          port.value.forEach((val, idx) => {
            const childPortData = {
              label: port.label,
              portKey: portKey + "_idx_" + idx,
              icon: osparc.data.Converters.fromTypeToIcon(port.type),
              value: val == null ? this.tr("no value") : val
            };
            children.push(childPortData);
          });
          portData.isDir = true;
          portData.children = children;
          portData.open = true;
        } else {
          portData.icon = osparc.data.Converters.fromTypeToIcon(port.type);
          portData.value = port.value == null ? this.tr("no value") : port.value;
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

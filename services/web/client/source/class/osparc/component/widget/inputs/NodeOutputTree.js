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
        c.bindProperty("type", "type", null, item, id);
        c.bindProperty("label", "description", null, item, id);
        c.bindProperty("description", "description2", null, item, id);
        c.bindProperty("value", "value", null, item, id);
        c.bindProperty("nodeKey", "nodeKey", null, item, id);
        c.bindProperty("portKey", "portKey", null, item, id);
        c.bindProperty("icon", "icon", null, item, id);
        c.bindProperty("unitShort", "unitShort", null, item, id);
        c.bindProperty("unitLong", "unitLong", null, item, id);
      },
      configureItem: item => {
        item.setDraggable(true);
        self.__attachEventHandlers(item); // eslint-disable-line no-underscore-dangle
      }
    });

    node.addListener("changeOutputs", e => {
      const updatedOutputs = e.getData();
      for (const portKey in updatedOutputs) {
        const outValue = updatedOutputs[portKey];
        this.getModel().getChildren()
          .forEach(treeItem => {
            if (treeItem.getPortKey() === portKey && "value" in outValue) {
              treeItem.setValue(qx.data.marshal.Json.createModel(outValue.value));
            }
          });
      }
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

        e.addData("osparc-port-link", {
          "node1": this.getNode(),
          "port1Key": item.getPortKey(),
          "destinations": {}
        });
      }, this);

      const msgCb = decoratorName => msg => {
        this.getSelection().remove(item.getModel());
        const compareFn = msg.getData();
        if (item.getPortKey() && decoratorName) {
          compareFn(this.getNode().getNodeId(), item.getPortKey())
            .then(compatible => {
              if (compatible) {
                item.setDecorator(decoratorName);
              } else {
                item.resetDecorator();
              }
            })
            .catch(() => item.resetDecorator());
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
        open: true,
        children: []
      };

      for (let portKey in ports) {
        const port = ports[portKey];
        const portData = {
          label: port.label,
          description: port.description,
          portKey: portKey,
          nodeKey: node.getKey(),
          open: false,
          type: port.type,
          unitShort: port.unitShort || null,
          unitLong: port.unitLong || null
        };
        if (port.type === "ref_contentSchema") {
          portData.type = port.contentSchema.type;
          if ("x_unit" in port.contentSchema) {
            const {
              unitPrefix,
              unit
            } = osparc.utils.Units.decomposeXUnit(port.contentSchema["x_unit"]);
            const labels = osparc.utils.Units.getLabels(unit, unitPrefix);
            if (labels !== null) {
              portData.unitShort = labels.unitShort;
              portData.unitLong = labels.unitLong;
            }
          }
        }
        portData.icon = osparc.data.Converters.fromTypeToIcon(port.type);
        portData.value = port.value == null ? "-" : port.value;
        data.children.push(portData);
      }

      return qx.data.marshal.Json.createModel(data, true);
    },

    getOutputWidget: function() {
      return this;
    }
  }
});

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
 *   Widget used for displaying an output port data of an input node. It contains a List populated
 * with NodeOutputListItemIcons. It implements Drag&Drop mechanism.
 *
 * It is meant to fit "node-output-list-api" input/output port type
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputListIcon(node, port, portKey);
 *   widget = nodeOutputList.getOutputWidget();
 *   this.getRoot().add(widget);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.inputs.NodeOutputListIcon", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param port {Object} Port owning the widget
    * @param portKey {String} Port Key
  */
  construct: function(node, port, portKey) {
    this.base();

    this.setNode(node);

    let list = this.__list = new qx.ui.list.List().set({
      labelPath: "label",
      iconPath: "icon"
    });

    let that = this;
    list.setDelegate({
      createItem: () => new qxapp.component.widget.inputs.NodeOutputListItemIcon(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
        c.bindProperty("thumbnail", "icon", null, item, id);
        c.bindProperty("label", "label", {
          converter: function(data) {
            // return "<b>" + data + "</b>";
            return data;
          }
        }, item, id);
      },
      configureItem: item => {
        let icon = item.getChildControl("icon");
        icon.set({
          scale: true,
          width: 246,
          height: 144
        });
        that.__createDragMechanism(item); // eslint-disable-line no-underscore-dangle
      }
    });

    const itemList = qxapp.data.Store.getInstance().getItemList(node.getKey(), portKey);
    const listModel = qxapp.data.Converters.fromAPIListToVirtualListModel(itemList);
    let model = qx.data.marshal.Json.createModel(listModel, true);
    list.setModel(model);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __list: null,

    __createDragMechanism: function(item) {
      item.setDraggable(true);
      item.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");

        // HACK
        if (this.getNode().getKey() === "simcore/services/demodec/dynamic/itis/s4l/neuroman") {
          // Register supported types
          e.addType("osparc-port-link");
          item.nodeId = this.getNode().getNodeId();
          item.portId = item.getLabel();
        } else {
          // Register supported types
          e.addType("osparc-mapping");
        }
      }, this);
    },

    getOutputWidget: function() {
      return this.__list;
    }
  }
});

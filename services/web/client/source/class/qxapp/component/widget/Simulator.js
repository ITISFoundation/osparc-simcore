/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const simulator = new qxapp.component.widget.Simulator(node);
 *   this.getRoot().add(simulator);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.Simulator", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.Canvas());
    const splitpane = this.__splitpane = new qx.ui.splitpane.Pane("horizontal");
    splitpane.getChildControl("splitter").getChildControl("knob")
      .hide();
    splitpane.setOffset(0);

    this._add(splitpane, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    const mappers = this.__mappers = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    const tree = this.__settingsTree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
      openMode: "none"
    });
    const itemList = qxapp.data.Store.getInstance().getItemList(node.getKey());
    let children = [];
    for (let i=0; i<itemList.length; i++) {
      children.push({
        label: itemList[i].label,
        uuid: itemList[i].key,
        children: []
      });
    }
    let data = {
      label: "Simulator",
      children: children
    };
    let model = qx.data.marshal.Json.createModel(data, true);
    tree.setModel(model);
    mappers.add(tree);
    mappers.setWidth(250);
    mappers.setMinWidth(150);
    splitpane.add(mappers, 0);

    this.checkModeler();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __splitpane: null,
    __mappers: null,
    __modeler: null,
    __settingsTree: null,

    checkModeler: function() {
      const inputNodes = this.getNode().getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        if (inputNodes[i].isInKey("remote-renderer")) {
          const modeler = this.__modeler = new qxapp.component.widget.RemoteRenderer(inputNodes[i], null);
          this.__splitpane.add(modeler, 1);
          break;
        }
      }
    }
  }
});

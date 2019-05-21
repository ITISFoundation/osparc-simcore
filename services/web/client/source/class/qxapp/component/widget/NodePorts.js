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
 * Widget that represents the output of an input node.
 * It creates a VBox with widgets representing each of the output ports of the node.
 * It can also create widget for representing default inputs (isInputModel = false).
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodePorts = new qxapp.component.widget.NodePorts(node, isInputModel);
 *   this.getRoot().add(nodePorts);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodePorts", {
  extend: qxapp.desktop.PanelView,
  /**
   * @param node {qxapp.data.model.Node} Node owning the widget
   * @param isInputModel {Boolean} false for representing defaultInputs
   */
  construct: function(node, isInputModel = true) {
    this.setIsInputModel(isInputModel);
    this.setNode(node);

    this._setLayout(new qx.ui.layout.Grow());

    const nodeUIPorts = this.__nodeUIPorts = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
      appearance: "node-ports"
    });

    this.base(arguments, node.getLabel(), nodeUIPorts);

    node.bind("label", this, "title");
  },

  properties: {
    isInputModel: {
      check: "Boolean",
      init: true,
      nullable: false
    },

    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __nodeUIPorts: null,

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    getMetaData: function() {
      return this.getNode().getMetaData();
    },

    populatePortsData: function() {
      this.__nodeUIPorts.removeAll();
      const metaData = this.getNode().getMetaData();
      if (this.getIsInputModel()) {
        this.__createUIPorts(false, metaData.outputs);
      } else if (metaData.inputsDefault) {
        this.__createUIPorts(false, metaData.inputsDefault);
      }
    },

    __createUIPorts: function(isInput, ports) {
      // Always create ports if node is a container
      if (!this.getNode().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      if (ports.defaultNeuromanModels) {
        // Maintaining NodeOutputListIcon for Neuroman
        const nodeOutputList = new qxapp.component.widget.inputs.NodeOutputListIcon(this.getNode(), ports.defaultNeuromanModels, "defaultNeuromanModels");
        this.__nodeUIPorts.add(nodeOutputList.getOutputWidget());
      } else {
        const portTree = new qxapp.component.widget.inputs.NodeOutputTree(this.getNode(), ports);
        this.__nodeUIPorts.add(portTree);
      }
    }
  }
});

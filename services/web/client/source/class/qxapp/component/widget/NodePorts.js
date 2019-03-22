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
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param isInputModel {Boolean} false for representing defaultInputs
  */
  construct: function(node, isInputModel = true) {
    this.base();

    let nodeInputLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeInputLayout);

    let label = new qx.ui.basic.Label().set({
      font: "title-16",
      alignX: "center",
      marginTop: 10
    });
    node.bind("label", label, "value");
    this._add(label);

    let nodeUIPorts = this.__nodeUIPorts = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
      padding: 5
    });
    this._add(nodeUIPorts);

    this.setIsInputModel(isInputModel);
    this.setNode(node);
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
      for (const portKey in ports) {
        const port = ports[portKey];
        if (port.type.includes("api")) {
          let widget = null;
          switch (port.type) {
            case "node-output-list-api-v0.0.1": {
              let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputListIcon(this.getNode(), port, portKey);
              widget = nodeOutputList.getOutputWidget();
              break;
            }
            case "node-output-tree-api-v0.0.1": {
              let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputTree(this.getNode(), port, portKey);
              widget = nodeOutputList.getOutputWidget();
              break;
            }
          }
          if (widget !== null) {
            this.__nodeUIPorts.add(widget);
          }
        } else {
          let nodeOutputLabel = new qxapp.component.widget.inputs.NodeOutputLabel(this.getNode(), port, portKey);
          let widget = nodeOutputLabel.getOutputWidget();
          this.__nodeUIPorts.add(widget);
          let label = {
            isInput: isInput,
            ui: widget
          };
          label.ui.isInput = isInput;
        }
      }
    }
  }
});

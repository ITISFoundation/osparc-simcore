/* ************************************************************************
   Copyright: 2018 ITIS Foundation
   License:   MIT
   Authors:   Odei Maiz <maiz@itis.swiss>
   Utf8Check: äöü
************************************************************************ */

/**
 *  Creates the widget that represents the output of an input node.
 * It creates a VBox with widgets representing each of the output ports of the node.
 * It can also create widget for representing default inputs (isInputModel = false).
 *
 */

qx.Class.define("qxapp.component.widget.NodePorts", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, isInputModel = true) {
    this.base();

    let nodeInputLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeInputLayout);

    this.set({
      decorator: "main"
    });

    const title16Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-16"]);
    let label = new qx.ui.basic.Label().set({
      font: title16Font,
      alignX: "center",
      alignY: "middle"
    });
    nodeModel.bind("label", label, "value");
    this._add(label);

    let nodeUIPorts = this.__nodeUIPorts = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this._add(nodeUIPorts, {
      flex: 1
    });

    this.setIsInputModel(isInputModel);
    this.setNodeModel(nodeModel);
  },

  properties: {
    isInputModel: {
      check: "Boolean",
      init: true,
      nullable: false
    },

    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  members: {
    __nodeUIPorts: null,

    getNodeId: function() {
      return this.getNodeModel().getNodeId();
    },

    getMetaData: function() {
      return this.getNodeModel().getMetaData();
    },

    populatePortsData: function() {
      this.__nodeUIPorts.removeAll();
      const metaData = this.getNodeModel().getMetaData();
      if (this.getIsInputModel()) {
        this.__createUIPorts(false, metaData.outputs);
      } else if (Object.prototype.hasOwnProperty.call(metaData, "inputsDefault")) {
        this.__createUIPorts(false, metaData.inputsDefault);
      }
    },

    __createUIPorts: function(isInput, ports) {
      // Always create ports if node is a container
      if (!this.getNodeModel().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      for (const portKey in ports) {
        const port = ports[portKey];
        if (port.type.includes("api")) {
          let widget = null;
          switch (port.type) {
            case "node-output-list-api-v0.0.1": {
              let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputListIcon(this.getNodeModel(), port, portKey);
              widget = nodeOutputList.getOutputWidget();
              break;
            }
            case "node-output-tree-api-v0.0.1": {
              let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputTree(this.getNodeModel(), port, portKey);
              widget = nodeOutputList.getOutputWidget();
              break;
            }
          }
          if (widget !== null) {
            this.__nodeUIPorts.add(widget, {
              flex: 1
            });
          }
        } else {
          let nodeOutputLabel = new qxapp.component.widget.inputs.NodeOutputLabel(this.getNodeModel(), port, portKey);
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

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
    let label = new qx.ui.basic.Label(nodeModel.getLabel()).set({
      font: title16Font,
      alignX: "center",
      alignY: "middle"
    });
    this._add(label);

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
    __inputPort: null,
    __outputPort: null,

    getNodeId: function() {
      return this.getNodeModel().getNodeId();
    },

    getMetaData: function() {
      return this.getNodeModel().getMetaData();
    },

    populateNodeLayout: function() {
      const metaData = this.getNodeModel().getMetaData();
      this.__inputPort = {};
      this.__outputPort = {};
      if (this.getIsInputModel()) {
        this.__createUIPorts(false, metaData.outputs);
      } else if (Object.prototype.hasOwnProperty.call(metaData, "inputsDefault")) {
        this.__createUIPorts(false, metaData.inputsDefault);
      }
    },

    getInputPort: function() {
      return this.__inputPort["Input"];
    },

    getOutputPort: function() {
      return this.__outputPort["Output"];
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
              let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputList(this.getNodeModel(), port, portKey);
              widget = nodeOutputList.getOutputWidget();
              break;
            }
            case "node-output-list-icon-api-v0.0.1": {
              let nodeOutputList = new qxapp.component.widget.inputs.NodeOutputListIcon(this.getNodeModel(), port, portKey);
              widget = nodeOutputList.getOutputWidget();
              break;
            }
          }
          if (widget !== null) {
            this._add(widget, {
              flex: 1
            });
          }
        } else {
          let nodeOutputLabel = new qxapp.component.widget.inputs.NodeOutputLabel(this.getNodeModel(), port, portKey);
          let widget = nodeOutputLabel.getOutputWidget();
          this._add(widget);
          let label = {
            isInput: isInput,
            ui: widget
          };

          label.ui.isInput = isInput;
          if (isInput) {
            this.__inputPort["Input"] = label;
          } else {
            this.__outputPort["Output"] = label;
          }
        }
      }
    }
  }
});

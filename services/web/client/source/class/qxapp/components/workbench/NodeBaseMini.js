const miniFactor = 4;
const nodeWidthMini = parseInt(240/miniFactor);

qx.Class.define("qxapp.components.workbench.NodeBaseMini", {
  extend: qxapp.components.workbench.NodeBase,

  construct: function(nodeImageId, uuid) {
    this.base(arguments, nodeImageId, uuid);

    this.set({
      minWidth: nodeWidthMini,
      maxWidth: nodeWidthMini,
      padding: 0
    });

    this.__createNodeLayout();
  },

  members: {
    __label: null,

    __createNodeLayout: function() {
      let nodeLayout = new qx.ui.layout.VBox();
      this.setLayout(nodeLayout);

      let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this.add(inputsOutputsLayout, {
        flex: 1
      });

      let inputsBox = new qx.ui.layout.VBox();
      this.__inputPortsUI = new qx.ui.container.Composite(inputsBox);
      inputsOutputsLayout.add(this.__inputPortsUI, {
        flex: 1
      });

      const nodeImageId = this.getNodeImageId();
      let miniLabel = "";
      let store = qxapp.data.Store.getInstance();
      let metaData = store.getNodeMetaData(nodeImageId);
      if (metaData) {
        miniLabel = metaData.name.substring(0, 4);
      }
      this.__label = new qx.ui.basic.Label(miniLabel);
      inputsOutputsLayout.add(this.__label);

      let outputsBox = new qx.ui.layout.VBox();
      this.__outputPortsUI = new qx.ui.container.Composite(outputsBox);
      inputsOutputsLayout.add(this.__outputPortsUI, {
        flex: 1
      });

      this.add(inputsOutputsLayout);

      this.__inputPorts = {};
      this.__outputPorts = {};
      this.__createInputPort();
      this.__createOutputPort();
    },

    __createInputPort: function() {
      const portId = "inPort";
      let label = {
        portId: portId,
        isInput: true
      };
      this.getInputPorts()[portId] = label;
      // this.__inputPortsUI.add(label.ui);
    },

    __createOutputPort: function() {
      const portId = "outPort";
      let label = {
        portId: portId,
        isInput: false
      };
      this.getOutputPorts()[portId] = label;
      // this.__outputPortsUI.add(label.ui);
    },

    getLinkPoint: function(port) {
      const nodeBounds = this.getCurrentBounds();
      let x = nodeBounds.left;
      if (port.isInput === false) {
        x += nodeBounds.width;
      }
      let y = nodeBounds.top + nodeBounds.height/2;
      return [x, y];
    }
  }
});

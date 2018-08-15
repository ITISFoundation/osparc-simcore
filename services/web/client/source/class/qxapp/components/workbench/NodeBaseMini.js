const miniFactor = 4;
const nodeWidthMini = parseInt(240/miniFactor);

qx.Class.define("qxapp.components.workbench.NodeBaseMini", {
  extend: qxapp.components.workbench.NodeBase,

  construct: function(uuid) {
    this.base(arguments, uuid);

    this.set({
      minWidth: nodeWidthMini,
      maxWidth: nodeWidthMini,
      padding: 0
    });
  },

  members: {
    __label: null,

    createNodeLayout: function() {
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

      this.__label = new qx.ui.basic.Label("S");
      inputsOutputsLayout.add(this.__label);

      let outputsBox = new qx.ui.layout.VBox();
      this.__outputPortsUI = new qx.ui.container.Composite(outputsBox);
      inputsOutputsLayout.add(this.__outputPortsUI, {
        flex: 1
      });

      this.add(inputsOutputsLayout);
    }
  }
});

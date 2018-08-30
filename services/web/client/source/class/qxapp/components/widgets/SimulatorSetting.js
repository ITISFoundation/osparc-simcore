qx.Class.define("qxapp.components.widgets.SimulatorSetting", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let simulatorSettingLayout = new qx.ui.layout.HBox(10);
    this._setLayout(simulatorSettingLayout);

    let treesBox = this.__treesBox = new qx.ui.layout.VBox(10);
    this._add(treesBox);

    let contentBox = this.__contentBox = new qx.ui.layout.VBox(10);
    this._add(contentBox);
  },

  properties: {
    node: {
      check: "qxapp.components.workbench.NodeBase",
      apply: "__applyNode"
    }
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    __treesBox: null,
    __contentBox: null,

    __applyNode: function(node, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__settingsBox.add(node.getPropsWidget());

      this.__dynamicViewer.removeAll();
      let viewerButton = node.getViewerButton();
      if (viewerButton) {
        if (!viewerButton.hasListener("execute")) {
          viewerButton.addListener("execute", function(e) {
            const data = {
              metadata: node.getMetaData(),
              nodeId: node.getNodeId()
            };
            console.log("ShowViewer", data);
            this.fireDataEvent("ShowViewer", data);
          }, this);
        }
        this.__dynamicViewer.add(viewerButton);
      }
    }
  }
});

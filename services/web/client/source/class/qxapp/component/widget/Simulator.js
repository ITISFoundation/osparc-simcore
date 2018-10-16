qx.Class.define("qxapp.component.widget.Simulator", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    if (!(Object.prototype.hasOwnProperty.call(node.getMetaData(), "innerNodes"))) {
      return;
    }

    let simulatorLayout = new qx.ui.layout.Grow();
    this._setLayout(simulatorLayout);

    this.__buildLayout(node);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    __buildLayout: function(node) {
      const innerNodes = node.getInnerNodes();

      let tree = new qx.ui.tree.Tree().set({
        width: 300,
        height: Math.min(400, 30 + innerNodes.length * 25),
        selectionMode: "single"
      });

      let root = new qx.ui.tree.TreeFolder(node.getMetaData().name);
      root.setOpen(true);
      tree.setRoot(root);

      for (let i=0; i<innerNodes.length; i++) {
        let conceptSetting = this.__getConceptSetting(innerNodes[i]);
        root.add(conceptSetting);
      }

      this._add(tree);
    },

    __getConceptSetting: function(innerNode) {
      let conceptSetting = new qx.ui.tree.TreeFolder(innerNode.getMetaData().name);
      conceptSetting.addListener("dblclick", function(e) {
        this.fireDataEvent("NodeDoubleClicked", innerNode.getNodeId());
        e.stopPropagation();
      }, this);
      return conceptSetting;
    }
  }
});

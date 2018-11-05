qx.Class.define("qxapp.component.widget.inputs.NodeOutputListItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    isDir: {
      check: "Boolean",
      nullable: false,
      init: true
    },

    nodeKey: {
      check: "String",
      nullable: false
    },

    portKey: {
      check: "String",
      nullable: false
    }
  }
});

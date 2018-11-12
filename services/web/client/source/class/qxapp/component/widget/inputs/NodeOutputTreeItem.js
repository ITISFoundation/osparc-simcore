qx.Class.define("qxapp.component.widget.inputs.NodeOutputTreeItem", {
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

    isRoot: {
      check: "Boolean",
      nullable: false,
      init: false
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

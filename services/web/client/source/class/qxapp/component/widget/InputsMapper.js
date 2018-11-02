qx.Class.define("qxapp.component.widget.InputsMapper", {
  extend: qx.ui.core.Widget,

  construct: function(label) {
    this.base();

    let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
      openMode: "none"
    });

    tree.setDelegate({
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
      },
      configureItem: item => {
        item.setDroppable(true);
        item.addListener("dragover", e => {
          let compatible = false;
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const to = e.getCurrentTarget();
            compatible = true;
            console.log(from, to);
          }
          if (!compatible) {
            e.preventDefault();
          }
        });
        item.addListener("drop", e => {
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const to = e.getCurrentTarget();
            console.log("Map", from.path, "to", to.path);
          }
        });
      }
    });

    let data = {
      label: label,
      children: []
    };
    let model = qx.data.marshal.Json.createModel(data, true);
    tree.setModel(model);
  },

  members: {
    __tree: null,

    getWidget: function() {
      return this.__tree;
    }
  }
});

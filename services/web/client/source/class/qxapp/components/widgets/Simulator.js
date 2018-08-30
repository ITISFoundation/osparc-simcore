qx.Class.define("qxapp.components.widgets.Simulator", {
  extend: qx.ui.core.Widget,

  construct: function(metaData) {
    this.base(arguments);

    if (!(Object.prototype.hasOwnProperty.call(metaData, "innerServices"))) {
      return;
    }

    let simulatorLayout = new qx.ui.layout.Grow();
    this._setLayout(simulatorLayout);

    this.__buildLayout(metaData);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    __metaData: null,

    __buildLayout: function(metaData) {
      this.__metaData = metaData;

      const innerServices = metaData.innerServices;

      let tree = new qx.ui.tree.Tree().set({
        width: 300,
        height: Math.min(400, 25 + innerServices.length * 25),
        selectionMode: "single"
      });

      let root = new qx.ui.tree.TreeFolder(metaData.name);
      root.setOpen(true);
      tree.setRoot(root);

      for (let i=0; i<innerServices.length; i++) {
        let conceptSetting = this.__getConceptSetting(innerServices[i]);
        root.add(conceptSetting);
      }

      this._add(tree);
    },

    __getConceptSetting: function(innerService) {
      let conceptSetting = new qx.ui.tree.TreeFolder(innerService.name);
      conceptSetting.metaData = innerService;
      conceptSetting.addListener("dblclick", function(e) {
        this.fireDataEvent("NodeDoubleClicked", innerService.key);
        e.stopPropagation();
      }, this);
      return conceptSetting;
    }
  }
});

qx.Class.define("qxapp.component.widget.cell.Output", {
  extend: qx.ui.core.Widget,

  construct: function(cellData) {
    this.base(arguments);

    this.setHandler(cellData);
  },

  properties: {
    handler: {
      check: "qxapp.component.widget.cell.Handler",
      nullable: false
    }
  },

  members: {
    getTitle: function() {
      return this.getHandler().getTitle();
    },

    getOutput: function() {
      return this.getHandler().getOutput();
    }
  }
});

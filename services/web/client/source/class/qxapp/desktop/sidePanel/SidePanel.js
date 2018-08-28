qx.Class.define("qxapp.desktop.sidePanel.SidePanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10, null, "separator-vertical"));

    let topView = new qx.ui.core.Widget();
    let midView = new qx.ui.core.Widget();
    let bottomView = new qx.ui.core.Widget();

    this._add(topView, {
      flex: 1
    });
    this._add(midView, {
      flex: 1
    });
    this._add(bottomView, {
      flex: 1
    });
  },

  properties: {
    topView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "_applyTopView"
    },

    midView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "_applyMidView"
    },

    bottomView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "_applyBottomView"
    }
  },

  events: {},

  members: {
    _applyTopView: function(newWidget) {
      this._removeAt(0);
      this._addAt(newWidget, 0);
    },

    _applyMidView: function(newWidget) {
      this._removeAt(1);
      this._addAt(newWidget, 1);
    },

    _applyBottomView: function(newWidget) {
      this._removeAt(2);
      this._addAt(newWidget, 2);
    }
  }
});

qx.Class.define("qxapp.desktop.sidePanel.SidePanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10, null, "separator-vertical"));

    let topView = new qx.ui.core.Widget();
    let midView = new qx.ui.core.Widget();
    let bottomView = new qx.ui.core.Widget();

    this._add(topView, {
      height: "33%",
      flex: 1
    });
    this._add(midView, {
      height: "33%",
      flex: 1
    });
    this._add(bottomView, {
      height: "33%",
      flex: 1
    });
  },

  properties: {
    topView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyTopView"
    },

    midView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyMidView"
    },

    bottomView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyBottomView"
    }
  },

  events: {},

  members: {
    __applyTopView: function(newWidget) {
      this.__replaceWidgetAt(newWidget, 0);
    },

    __applyMidView: function(newWidget) {
      this.__replaceWidgetAt(newWidget, 1);
    },

    __applyBottomView: function(newWidget) {
      this.__replaceWidgetAt(newWidget, 2);
    },

    __replaceWidgetAt: function(newWidget, indexOf) {
      if (this._indexOf(newWidget) !== indexOf) {
        this._removeAt(indexOf);
        this._addAt(newWidget, indexOf, {
          height: "33%",
          flex: 1
        });
      }
    }
  }
});

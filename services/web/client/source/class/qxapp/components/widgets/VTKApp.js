qx.Class.define("qxapp.components.widgets.VTKApp", {
  extend: qx.ui.core.Widget,

  construct : function(initWidth, initHeight) {
    this.base(arguments);

    let threeDAppLayout = new qx.ui.layout.Canvas();
    this._setLayout(threeDAppLayout);

    const backgroundColor = qxapp.theme.Color.colors["three-background"];
    let threeDView = this.__threeDView = new qxapp.components.widgets.VTKView(initWidth, initHeight, backgroundColor);

    this._add(threeDView, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });
  },

  members: {
    __threeDView: null
  }
});

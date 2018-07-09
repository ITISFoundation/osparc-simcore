qx.Class.define("qxapp.components.widgets.VTKApp", {
  extend: qx.ui.core.Widget,

  construct : function(initWidth, initHeight) {
    this.base(arguments);

    let threeDAppLayout = new qx.ui.layout.Canvas();
    this._setLayout(threeDAppLayout);

    let app = this.__app = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this._add(app, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    const backgroundColor = qxapp.theme.Color.colors["three-background"];
    let threeDView = this.__threeDView = new qxapp.components.widgets.VTKView(initWidth, initHeight, backgroundColor);

    let entityList = this.__entityList = new qxapp.components.widgets.EntityList();
    entityList.setBackgroudColor(backgroundColor);

    app.add(threeDView, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    let enlityListWindow = new qx.ui.window.Window();
    enlityListWindow.set({
      contentPadding: 0,
      width: 200,
      height: 250,
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      caption: "Entity List",
      layout: new qx.ui.layout.Canvas()
    });
    enlityListWindow.add(entityList, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });
    app.add(enlityListWindow);
    enlityListWindow.moveTo(10, 10);
    enlityListWindow.open();
  },

  members: {
    __app: null,
    __threeDView: null,
    __entityList: null
  }
});

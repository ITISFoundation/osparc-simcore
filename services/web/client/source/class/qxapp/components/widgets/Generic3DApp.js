qx.Class.define("qxapp.components.widgets.Generic3DApp", {
  extend: qx.ui.core.Widget,

  construct : function(initWidth, initHeight, viewerType = "threejs") {
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
    let threeDView = null;
    if (viewerType === "threejs") {
      threeDView = this.__threeDView = new qxapp.components.widgets.ThreeDView(initWidth, initHeight, backgroundColor);
    } else if (viewerType === "vtkjs") {
      threeDView = this.__threeDView = new qxapp.components.widgets.VTKView(initWidth, initHeight, backgroundColor);
    }

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

    this.__createThreeDConns();
    this.__createEntityListConns();
  },

  members: {
    __app: null,
    __threeDView: null,
    __entityList: null,

    __createThreeDConns: function() {
      this.__threeDView.addListener("entityAdded", function(e) {
        let entityName = e.getData()[0];
        let entityId = e.getData()[1];
        this.__entityList.addEntity(entityName, entityId);
      }, this);

      this.__threeDView.addListener("entityRemoved", function(e) {
        let entityId = e.getData();
        this.__entityList.removeEntity(entityId);
      }, this);
    },

    __createEntityListConns: function() {
      // Entity list
      this.__entityList.addListener("removeEntityRequested", function(e) {
        let entityId = e.getData();
        if (this.__threeDView.removeEntityByID(entityId)) {
          this.__entityList.removeEntity(entityId);
        }
      }, this);

      this.__entityList.addListener("selectionChanged", function(e) {
        let entityIds = e.getData();
        this.__threeDView.unhighlightAll();
        this.__threeDView.highlightEntities(entityIds);
      }, this);

      this.__entityList.addListener("visibilityChanged", function(e) {
        let entityId = e.getData()[0];
        let show = e.getData()[1];
        this.__threeDView.showHideEntity(entityId, show);
      }, this);

      this.__entityList.addListener("addBunny", function() {
        this.__threeDView.importVTKObject("../resource/models/bunny.vtk");
      }, this);
    }
  }
});

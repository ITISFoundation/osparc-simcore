/* global window */

qx.Class.define("qxapp.components.MenuBar", {
  extend: qx.ui.container.Composite,

  include: [qx.locale.MTranslation],

  construct: function(width, height, backgroundColor, fontColor) {
    this.base(arguments);

    let box = new qx.ui.layout.HBox();
    box.set({
      // alignX: "center",
      // alignY: "middle",
      spacing: 10
    });

    this.set({
      layout: box,
      width: width,
      height: height
    });

    let bar = this.__getMenuBar(width, backgroundColor, fontColor);
    this.add(bar);
  },

  events : {
    "fileNewPressed": "qx.event.type.Event",
    "fileLoadScenePressed": "qx.event.type.Event",
    "fileSaveScenePressed": "qx.event.type.Event",
    "fileDownloadScenePressed": "qx.event.type.Event",
    "fileLoadModelPressed": "qx.event.type.Data",
    "editPreferencesPressed": "qx.event.type.Data"
  },

  members: {
    __getMenuBar: function(width, backgroundColor, fontColor) {
      let frame = new qx.ui.container.Composite(new qx.ui.layout.Grow());

      let menubar = new qx.ui.menubar.MenuBar();
      menubar.set({
        width: width,
        backgroundColor: backgroundColor
      });

      window.addEventListener("resize", function() {
        menubar.set({
          width: window.innerWidth
        });
      });

      frame.add(menubar);

      let fileMenu = new qx.ui.menubar.Button(this.tr("File"), null, this.__getFileMenu());
      let editMenu = new qx.ui.menubar.Button(this.tr("Edit"), null, this.__getEditMenu());
      let viewMenu = new qx.ui.menubar.Button(this.tr("View"), null, null);
      let helpMenu = new qx.ui.menubar.Button(this.tr("Help"), null, null);
      let menuOpts = [fileMenu, editMenu, viewMenu, helpMenu];

      for (let i = 0; i < menuOpts.length; i++) {
        menuOpts[i].setTextColor(fontColor);
        menubar.add(menuOpts[i]);
      }

      return frame;
    },

    __getFileMenu: function() {
      let fileMenu = new qx.ui.menu.Menu();

      let newButton = new qx.ui.menu.Button(this.tr("New"), null, null);
      let loadSceneButton = new qx.ui.menu.Button(this.tr("Load scene"), null, null);
      let saveSceneButton = new qx.ui.menu.Button(this.tr("Save scene"), null, null);
      let downloadSceneButton = new qx.ui.menu.Button(this.tr("Download scene"), null, null);
      let loadModelsButton = new qx.ui.menu.Button(this.tr("Load Models"), null, null, this.__getModelsList());

      newButton.addListener("execute", function(e) {
        this.fireDataEvent("fileNewPressed");
      }, this);

      loadSceneButton.addListener("execute", function(e) {
        this.fireDataEvent("fileLoadScenePressed");
      }, this);

      saveSceneButton.addListener("execute", function(e) {
        this.fireDataEvent("fileSaveScenePressed");
      }, this);

      downloadSceneButton.addListener("execute", function(e) {
        this.fireDataEvent("fileDownloadScenePressed");
      }, this);

      fileMenu.add(newButton);
      fileMenu.add(loadSceneButton);
      fileMenu.add(saveSceneButton);
      fileMenu.add(downloadSceneButton);
      fileMenu.add(loadModelsButton);

      return fileMenu;
    },

    __getModelsList: function() {
      let modelsMenu = new qx.ui.menu.Menu();

      let ratButton = new qx.ui.menu.Button("Rat", null, null);
      ratButton.addListener("execute", function(e) {
        this.fireDataEvent("fileLoadModelPressed", "Rat");
      }, this);
      modelsMenu.add(ratButton);

      let bigRatButton = new qx.ui.menu.Button("BigRat", null, null);
      bigRatButton.addListener("execute", function(e) {
        this.fireDataEvent("fileLoadModelPressed", "BigRat");
      }, this);
      modelsMenu.add(bigRatButton);

      return modelsMenu;
    },

    __getEditMenu: function() {
      let editMenu = new qx.ui.menu.Menu();

      let preferencesButton = new qx.ui.menu.Button(this.tr("Preferences"), null, null);

      preferencesButton.addListener("execute", function(e) {
        this.fireDataEvent("editPreferencesPressed");
      }, this);

      editMenu.add(preferencesButton);

      return editMenu;
    }
  }
});

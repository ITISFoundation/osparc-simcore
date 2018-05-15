/* ************************************************************************

   Copyright: 2018 undefined

   License: MIT license

   Authors: undefined

************************************************************************ */

/**
 * This is the main application class of "app"
 *
 * @asset(app/*)
 */

/* global document */

qx.Class.define("qxapp.Application", {
  extend: qx.application.Standalone,

  include: [qx.locale.MTranslation],

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members:
  {
    __threeView: null,
    __entityList: null,
    __availableServicesBar: null,

    /**
     * This method contains the initial application code and gets called
     * during startup of the application
     */
    main: function() {
      // Call super class
      this.base(arguments);

      // Enable logging in debug variant
      if (qx.core.Environment.get("qx.debug")) {
        // support native logging capabilities, e.g. Firebug for Firefox
        qx.log.appender.Native;
        // support additional cross-browser console. Press F7 to toggle visibility
        qx.log.appender.Console;
      }

      /*
      -------------------------------------------------------------------------
        Below is your actual application code...
      -------------------------------------------------------------------------
      */

      this._appModel = qx.data.marshal.Json.createModel(this._getDefaultData());

      qx.locale.Manager.getInstance().setLocale(this._appModel.getLocaleCode());
      qx.locale.Manager.getInstance().addListener("changeLocale", function(e) {
        qx.locale.Manager.getInstance().setLocale(e.getData());
      }, this);

      // Document is the application root
      let doc = this.getRoot();

      // openning web socket
      this._socket = new qxapp.wrappers.WebSocket("app");
      this._socket.connect();

      let body = document.body;
      let html = document.documentElement;

      let docWidth = Math.max(body.scrollWidth, body.offsetWidth, html.clientWidth, html.scrollWidth, html.offsetWidth);
      let docHeight = Math.max(body.scrollHeight, body.offsetHeight, html.clientHeight, html.scrollHeight, html.offsetHeight);

      // initialize components
      const menuBarHeight = 35;
      const avaiBarHeight = 55;

      this._menuBar = new qxapp.components.MenuBar(
        docWidth, menuBarHeight,
        this._appModel.getColors().getMenuBar()
          .getBackground(), this._appModel.getColors().getMenuBar()
          .getFont());

      this._userMenu = new qxapp.components.UserMenu(
        this._appModel,
        this._appModel.getColors().getMenuBar()
          .getBackground(), this._appModel.getColors().getMenuBar()
          .getFont());

      this.__availableServicesBar = new qxapp.components.AvailableServices(
        docWidth, avaiBarHeight,
        this._appModel.getColors().getToolBar()
          .getBackground(), this._appModel.getColors().getToolBar()
          .getFont());

      this.__threeView = new qxapp.components.ThreeView(
        docWidth, docHeight,
        this._appModel.getColors().get3DView()
          .getBackground());

      this.__entityList = new qxapp.components.EntityList(
        250, 300,
        this._appModel.getColors().getSettingsView()
          .getBackground(), this._appModel.getColors().getSettingsView()
          .getFont());


      // components to document
      doc.add(this.__threeView);

      let toolBarcontainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(1)).set({
        backgroundColor: "white",
        allowGrowY: false
      });
      toolBarcontainer.add(this._menuBar);
      toolBarcontainer.add(this.__availableServicesBar);
      // toolBarcontainer.add(this.__threeView);
      doc.add(toolBarcontainer);

      doc.add(this._userMenu, {
        right: 30
      });

      this.__entityList.moveTo(10, menuBarHeight + avaiBarHeight + 10);
      this.__entityList.open();

      this._initSignals();
    },

    _getDefaultData: function() {
      let myDefaultData = {
        "LocaleCode": "en",
        "Colors": {
          "MenuBar": {
            "Background": "#535353", // 83, 83, 83
            "Font": "#FFFFFF" // 255, 255, 255
          },
          "ToolBar": {
            "Background": "#252526", // 37, 37, 38
            "Font": "#FFFFFF" // 255, 255, 255
          },
          "SettingsView": {
            "Background": "#252526", // 37, 37, 38
            "Font": "#FFFFFF" // 255, 255, 255
          },
          "3DView": {
            "Background": "#3F3F3F" // 63, 63, 63
          }
        },
        "ActiveUser": 0,
        "Users": [
          {
            "Name": "Odei",
            "ID": 0
          },
          {
            "Name": "Sylvain",
            "ID": 1
          },
          {
            "Name": "Alessandro",
            "ID": 2
          }
        ],
        "UseExternalModeler": 0,
        "ExportSceneAsBinary": 0
      };
      return myDefaultData;
    },

    getActiveUserName: function() {
      const activeUserId = this._appModel.getActiveUser();
      return this._appModel.getUsers().toArray()[activeUserId].getName();
    },

    _initSignals: function() {
      // Menu bar
      this._menuBar.addListener("fileNewPressed", function(e) {
        this.__threeView.removeAll();
      }, this);

      this._menuBar.addListener("fileLoadScenePressed", function(e) {
        if (!this._socket.slotExists("importScene")) {
          this._socket.on("importScene", function(val) {
            if (val.type === "importScene") {
              this.__threeView.importSceneFromBuffer(val.value);
            }
          }, this);
        }
        this._socket.emit("importScene", this.getActiveUserName());
      }, this);

      this._menuBar.addListener("fileSaveScenePressed", function(e) {
        const donwloadFile = false;
        const exportSceneAsBinary = this._appModel.getExportSceneAsBinary();
        this.__threeView.serializeScene(donwloadFile, exportSceneAsBinary);
      }, this);

      this._menuBar.addListener("fileDownloadScenePressed", function(e) {
        const donwloadFile = true;
        const exportSceneAsBinary = this._appModel.getExportSceneAsBinary();
        this.__threeView.serializeScene(donwloadFile, exportSceneAsBinary);
      }, this);

      this._menuBar.addListener("fileLoadModelPressed", function(e) {
        let selectedModel = e.getData();
        if (!this._socket.slotExists("importModelScene")) {
          this._socket.on("importModelScene", function(val) {
            if (val.type === "importModelScene") {
              this.__threeView.importSceneFromBuffer(val.value);
            }
          }, this);
        }
        this._socket.emit("importModel", selectedModel);
      }, this);

      this._menuBar.addListener("editPreferencesPressed", function(e) {
        this._showPreferences();
      }, this);

      // Services
      this.__availableServicesBar.addListener("selectionModeChanged", function(e) {
        let selectionMode = e.getData();
        this.__threeView.setSelectionMode(selectionMode);
      }, this);

      this.__availableServicesBar.addListener("newBlockRequested", function(e) {
        let enableBoxTool = Boolean(e.getData());
        if (enableBoxTool) {
          // let useExternalModeler = this._appModel.getUseExternalModeler();
          let boxCreator = new qxapp.modeler.BoxCreator(this.__threeView);
          this.__threeView.startTool(boxCreator);
        } else {
          this.__threeView.stopTool();
        }
      }, this);

      this.__availableServicesBar.addListener("newSphereRequested", function(e) {
        let enableSphereTool = Boolean(e.getData());
        if (enableSphereTool) {
          let useExternalModeler = Boolean(this._appModel.getUseExternalModeler());
          if (useExternalModeler === false) {
            let sphereCreator = new qxapp.modeler.SphereCreator(this.__threeView);
            this.__threeView.startTool(sphereCreator);
          } else {
            let sphereCreator = new qxapp.modeler.SphereCreatorS4L(this.__threeView);
            this.__threeView.startTool(sphereCreator);
            sphereCreator.addListenerOnce("newSphereS4LRequested", function(ev) {
              let radius = ev.getData()[0];
              let centerPoint = ev.getData()[1];
              let uuid = ev.getData()[2];
              if (!this._socket.slotExists("newSphereS4LRequested")) {
                this._socket.on("newSphereS4LRequested", function(val) {
                  if (val.type === "newSphereS4LRequested") {
                    sphereCreator.sphereFromS4L(val);
                  }
                }, this);
              }
              this._socket.emit("newSphereS4LRequested", [radius, centerPoint, uuid]);
            }, this);
          }
        } else {
          this.__threeView.stopTool();
        }
      }, this);

      this.__availableServicesBar.addListener("newCylinderRequested", function(e) {
        let enableCylinderTool = Boolean(e.getData());
        if (enableCylinderTool) {
          // let useExternalModeler = this._appModel.getUseExternalModeler();
          let cylinderCreator = new qxapp.modeler.CylinderCreator(this.__threeView);
          this.__threeView.startTool(cylinderCreator);
        } else {
          this.__threeView.stopTool();
        }
      }, this);

      this.__availableServicesBar.addListener("newDodecaRequested", function(e) {
        let enableDodecahedronTool = Boolean(e.getData());
        if (enableDodecahedronTool) {
          // let useExternalModeler = this._appModel.getUseExternalModeler();
          let dodecahedronCreator = new qxapp.modeler.DodecahedronCreator(this.__threeView);
          this.__threeView.startTool(dodecahedronCreator);
        } else {
          this.__threeView.stopTool();
        }
      }, this);

      this.__availableServicesBar.addListener("newSplineRequested", function(e) {
        // this.__threeView.SetSelectionMode(0);
        let enableSplineTool = Boolean(e.getData());
        if (enableSplineTool) {
          let useExternalModeler = Boolean(this._appModel.getUseExternalModeler());
          if (useExternalModeler === false) {
            let splineCreator = new qxapp.modeler.SplineCreator(this.__threeView);
            this.__threeView.startTool(splineCreator);
          } else {
            let splineCreator = new qxapp.modeler.SplineCreatorS4L(this.__threeView);
            this.__threeView.startTool(splineCreator);
            splineCreator.addListenerOnce("newSplineS4LRequested", function(ev) {
              let pointList = ev.getData()[0];
              let uuid = ev.getData()[1];
              if (!this._socket.slotExists("newSplineS4LRequested")) {
                this._socket.on("newSplineS4LRequested", function(val) {
                  if (val.type === "newSplineS4LRequested") {
                    splineCreator.splineFromS4L(val);
                  }
                }, this);
              }
              this._socket.emit("newSplineS4LRequested", [pointList, uuid]);
            }, this);
          }
        } else {
          this.__threeView.stopTool();
        }
      }, this);

      this.__availableServicesBar.addListener("moveToolRequested", function(e) {
        this.__threeView.setSelectionMode(0);
        let enableMoveTool = Boolean(e.getData());
        if (enableMoveTool) {
          let selObjId = this.__entityList.getSelectedEntityId();
          if (selObjId) {
            this.__threeView.startMoveTool(selObjId, "translate");
          } else {
            this.__availableServicesBar.getMoveBtn().setValue(false);
          }
        } else {
          this.__threeView.stopMoveTool();
        }
      }, this);

      this.__availableServicesBar.addListener("rotateToolRequested", function(e) {
        this.__threeView.setSelectionMode(0);
        let enableRotateTool = Boolean(e.getData());
        if (enableRotateTool) {
          let selObjId = this.__entityList.getSelectedEntityId();
          if (selObjId) {
            this.__threeView.startMoveTool(selObjId, "rotate");
          } else {
            this.__availableServicesBar.getRotateBtn().setValue(false);
          }
        } else {
          this.__threeView.stopMoveTool();
        }
      }, this);

      this.__availableServicesBar.addListener("booleanOperationRequested", function(e) {
        let operationType = e.getData();
        if (this.__threeView.getEntities().length>1) {
          let entityMeshesIDs = this.__entityList.getSelectedEntityIds();
          if (entityMeshesIDs.length>1) {
            this.__threeView.getThreeWrapper().addListenerOnce("sceneWithMeshesToBeExported", function(ev) {
              let sceneWithMeshes = ev.getData();
              if (!this._socket.slotExists("newBooleanOperationRequested")) {
                this._socket.on("newBooleanOperationRequested", function(val) {
                  if (val.type === "newBooleanOperationRequested") {
                    this.__threeView.importSceneFromBuffer(val.value);
                  }
                }, this);
              }
              this._socket.emit("newBooleanOperationRequested", [JSON.stringify(sceneWithMeshes), operationType]);
            }, this);
            this.__threeView.getThreeWrapper().createSceneWithMeshes(entityMeshesIDs);
          }
        }
      }, this);


      // Entity list
      this.__entityList.addListener("removeEntityRequested", function(e) {
        let entityId = e.getData();
        if (this.__threeView.removeEntityByID(entityId)) {
          this.__entityList.removeEntity(entityId);
        }
      }, this);

      this.__entityList.addListener("selectionChanged", function(e) {
        let entityIds = e.getData();
        this.__threeView.unhighlightAll();
        this.__threeView.highlightEntities(entityIds);
      }, this);

      this.__entityList.addListener("visibilityChanged", function(e) {
        let entityId = e.getData()[0];
        let show = e.getData()[1];
        this.__threeView.showHideEntity(entityId, show);
      }, this);


      // 3D View
      this.__threeView.addListener("entitySelected", function(e) {
        let entityId = e.getData();
        this.__entityList.onEntitySelectedChanged([entityId]);
      }, this);

      this.__threeView.addListener("entitySelectedAdd", function(e) {
        let entityId = e.getData();
        let selectedEntityIds = this.__entityList.getSelectedEntityIds();
        if (selectedEntityIds.indexOf(entityId) === -1) {
          selectedEntityIds.push(entityId);
          this.__entityList.onEntitySelectedChanged(selectedEntityIds);
        }
      }, this);

      this.__threeView.addListener("entityAdded", function(e) {
        let entityName = e.getData()[0];
        let entityId = e.getData()[1];
        this.__entityList.addEntity(entityName, entityId);
      }, this);

      this.__threeView.addListener("entityRemoved", function(e) {
        let entityId = e.getData();
        this.__entityList.removeEntity(entityId);
      }, this);

      this.__threeView.addListener(("entitiesToBeExported"), function(e) {
        if (!this._socket.slotExists("exportEntities")) {
          this._socket.on("exportEntities", function(val) {
            if (val.type === "exportEntities") {
              console.log("Entities exported: ", val.value);
            }
          }, this);
        }
        this._socket.emit("exportEntities", [this.getActiveUserName(), e.getData()]);
      }, this);

      this.__threeView.addListener(("SceneToBeExported"), function(e) {
        if (!this._socket.slotExists("exportScene")) {
          this._socket.on("exportScene", function(val) {
            if (val.type === "exportScene") {
              console.log("Scene exported: ", val.value);
            }
          }, this);
        }
        this._socket.emit("exportScene", [this.getActiveUserName(), e.getData()]);
      }, this);
    },

    _showPreferences: function() {
      let preferencesDlg = new qxapp.components.Preferences(
        this._appModel, 250, 300,
        this._appModel.getColors().getSettingsView()
          .getBackground(), this._appModel.getColors().getSettingsView()
          .getFont());

      preferencesDlg.open();
      preferencesDlg.center();
    }
  }
});

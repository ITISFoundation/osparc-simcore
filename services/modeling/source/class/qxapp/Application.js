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
    _threeView: null,
    _entityList: null,

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

      this._availableServicesBar = new qxapp.components.AvailableServices(
        docWidth, avaiBarHeight,
        this._appModel.getColors().getToolBar()
          .getBackground(), this._appModel.getColors().getToolBar()
          .getFont());

      this._threeView = new qxapp.components.ThreeView(
        docWidth, docHeight,
        this._appModel.getColors().get3DView()
          .getBackground());

      this._entityList = new qxapp.components.EntityList(
        250, 300,
        this._appModel.getColors().getSettingsView()
          .getBackground(), this._appModel.getColors().getSettingsView()
          .getFont());


      // components to document
      doc.add(this._threeView);

      let toolBarcontainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(1)).set({
        backgroundColor: "white",
        allowGrowY: false
      });
      toolBarcontainer.add(this._menuBar);
      toolBarcontainer.add(this._availableServicesBar);
      // toolBarcontainer.add(this._threeView);
      doc.add(toolBarcontainer);

      doc.add(this._userMenu, {
        right: 30
      });

      this._entityList.moveTo(10, menuBarHeight + avaiBarHeight + 10);
      this._entityList.open();

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

    _getActiveUserName: function() {
      const activeUserId = this._appModel.getActiveUser();
      return this._appModel.getUsers().toArray()[activeUserId].getName();
    },

    _initSignals: function() {
      // Menu bar
      this._menuBar.addListener("fileNewPressed", function(e) {
        this._threeView.removeAll();
      }, this);

      this._menuBar.addListener("fileLoadScenePressed", function(e) {
        if (!this._socket.slotExists("importScene")) {
          this._socket.on("importScene", function(val) {
            if (val.type === "importScene") {
              this._threeView.importSceneFromBuffer(val.value);
            }
          }, this);
        }
        this._socket.emit("importScene", this._getActiveUserName());
      }, this);

      this._menuBar.addListener("fileSaveScenePressed", function(e) {
        const donwloadFile = false;
        const exportSceneAsBinary = this._appModel.getExportSceneAsBinary();
        this._threeView.serializeScene(donwloadFile, exportSceneAsBinary);
      }, this);

      this._menuBar.addListener("fileDownloadScenePressed", function(e) {
        const donwloadFile = true;
        const exportSceneAsBinary = this._appModel.getExportSceneAsBinary();
        this._threeView.serializeScene(donwloadFile, exportSceneAsBinary);
      }, this);

      this._menuBar.addListener("fileLoadModelPressed", function(e) {
        let selectedModel = e.getData();
        if (!this._socket.slotExists("importModelScene")) {
          this._socket.on("importModelScene", function(val) {
            if (val.type === "importModelScene") {
              this._threeView.importSceneFromBuffer(val.value);
            }
          }, this);
        }
        this._socket.emit("importModel", selectedModel);
      }, this);

      this._menuBar.addListener("editPreferencesPressed", function(e) {
        this._showPreferences();
      }, this);

      // Services
      this._availableServicesBar.addListener("selectionModeChanged", function(e) {
        let selectionMode = e.getData();
        this._threeView.setSelectionMode(selectionMode);
      }, this);

      this._availableServicesBar.addListener("newBlockRequested", function(e) {
        let enableBoxTool = Boolean(e.getData());
        if (enableBoxTool) {
          // let useExternalModeler = this._appModel.getUseExternalModeler();
          let boxCreator = new qxapp.modeler.BoxCreator(this._threeView);
          this._threeView.startTool(boxCreator);
        } else {
          this._threeView.stopTool();
        }
      }, this);

      this._availableServicesBar.addListener("newSphereRequested", function(e) {
        let enableSphereTool = Boolean(e.getData());
        if (enableSphereTool) {
          let useExternalModeler = Boolean(this._appModel.getUseExternalModeler());
          if (useExternalModeler === false) {
            let sphereCreator = new qxapp.modeler.SphereCreator(this._threeView);
            this._threeView.startTool(sphereCreator);
          } else {
            let sphereCreator = new qxapp.modeler.SphereCreatorS4L(this._threeView);
            this._threeView.startTool(sphereCreator);
            sphereCreator.addListenerOnce("newSphereS4LRequested", function(ev) {
              let radius = ev.getData()[0];
              let center_point = ev.getData()[1];
              let uuid = ev.getData()[2];
              if (!this._socket.slotExists("newSphereS4LRequested")) {
                this._socket.on("newSphereS4LRequested", function(val) {
                  if (val.type === "newSphereS4LRequested") {
                    sphereCreator.sphereFromS4L(val);
                  }
                }, this);
              }
              this._socket.emit("newSphereS4LRequested", [radius, center_point, uuid]);
            }, this);
          }
        } else {
          this._threeView.stopTool();
        }
      }, this);

      this._availableServicesBar.addListener("newCylinderRequested", function(e) {
        let enableCylinderTool = Boolean(e.getData());
        if (enableCylinderTool) {
          // let useExternalModeler = this._appModel.getUseExternalModeler();
          let cylinderCreator = new qxapp.modeler.CylinderCreator(this._threeView);
          this._threeView.startTool(cylinderCreator);
        } else {
          this._threeView.stopTool();
        }
      }, this);

      this._availableServicesBar.addListener("newDodecaRequested", function(e) {
        let enableDodecahedronTool = Boolean(e.getData());
        if (enableDodecahedronTool) {
          // let useExternalModeler = this._appModel.getUseExternalModeler();
          let dodecahedronCreator = new qxapp.modeler.DodecahedronCreator(this._threeView);
          this._threeView.startTool(dodecahedronCreator);
        } else {
          this._threeView.stopTool();
        }
      }, this);

      this._availableServicesBar.addListener("newSplineRequested", function(e) {
        // this._threeView.SetSelectionMode(0);
        let enableSplineTool = Boolean(e.getData());
        if (enableSplineTool) {
          let useExternalModeler = Boolean(this._appModel.getUseExternalModeler());
          if (useExternalModeler === false) {
            let splineCreator = new qxapp.modeler.SplineCreator(this._threeView);
            this._threeView.startTool(splineCreator);
          } else {
            let splineCreator = new qxapp.modeler.SplineCreatorS4L(this._threeView);
            this._threeView.startTool(splineCreator);
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
          this._threeView.stopTool();
        }
      }, this);

      this._availableServicesBar.addListener("moveToolRequested", function(e) {
        this._threeView.setSelectionMode(0);
        let enableMoveTool = Boolean(e.getData());
        if (enableMoveTool) {
          let selObjId = this._entityList.getSelectedEntityId();
          if (selObjId) {
            this._threeView.startMoveTool(selObjId, "translate");
          } else {
            this._availableServicesBar._moveBtn.setValue(false);
          }
        } else {
          this._threeView.stopMoveTool();
        }
      }, this);

      this._availableServicesBar.addListener("rotateToolRequested", function(e) {
        this._threeView.setSelectionMode(0);
        let enableRotateTool = Boolean(e.getData());
        if (enableRotateTool) {
          let selObjId = this._entityList.getSelectedEntityId();
          if (selObjId) {
            this._threeView.startMoveTool(selObjId, "rotate");
          } else {
            this._availableServicesBar._rotateBtn.setValue(false);
          }
        } else {
          this._threeView.stopMoveTool();
        }
      }, this);

      this._availableServicesBar.addListener("booleanOperationRequested", function(e) {
        let operationType = e.getData();
        if (this._threeView._entities.length>1) {
          let entityMeshesIDs = this._entityList.getSelectedEntityIds();
          if (entityMeshesIDs.length>1) {
            this._threeView._threeWrapper.addListenerOnce("sceneWithMeshesToBeExported", function(ev) {
              let sceneWithMeshes = ev.getData();
              if (!this._socket.slotExists("newBooleanOperationRequested")) {
                this._socket.on("newBooleanOperationRequested", function(val) {
                  if (val.type === "newBooleanOperationRequested") {
                    this._threeView.importSceneFromBuffer(val.value);
                  }
                }, this);
              }
              this._socket.emit("newBooleanOperationRequested", [JSON.stringify(sceneWithMeshes), operationType]);
            }, this);
            this._threeView._threeWrapper.createSceneWithMeshes(entityMeshesIDs);
          }
        }
      }, this);


      // Entity list
      this._entityList.addListener("removeEntityRequested", function(e) {
        let entityId = e.getData();
        if (this._threeView.removeEntityByID(entityId)) {
          this._entityList.removeEntity(entityId);
        }
      }, this);

      this._entityList.addListener("selectionChanged", function(e) {
        let entityIds = e.getData();
        this._threeView.unhighlightAll();
        this._threeView.highlightEntities(entityIds);
      }, this);

      this._entityList.addListener("visibilityChanged", function(e) {
        let entityId = e.getData()[0];
        let show = e.getData()[1];
        this._threeView.showHideEntity(entityId, show);
      }, this);


      // 3D View
      this._threeView.addListener("entitySelected", function(e) {
        let entityId = e.getData();
        this._entityList.onEntitySelectedChanged([entityId]);
      }, this);

      this._threeView.addListener("entitySelectedAdd", function(e) {
        let entityId = e.getData();
        let selectedEntityIds = this._entityList.getSelectedEntityIds();
        if (selectedEntityIds.indexOf(entityId) === -1) {
          selectedEntityIds.push(entityId);
          this._entityList.onEntitySelectedChanged(selectedEntityIds);
        }
      }, this);

      this._threeView.addListener("entityAdded", function(e) {
        let entityName = e.getData()[0];
        let entityId = e.getData()[1];
        this._entityList.addEntity(entityName, entityId);
      }, this);

      this._threeView.addListener("entityRemoved", function(e) {
        let entityId = e.getData();
        this._entityList.removeEntity(entityId);
      }, this);

      this._threeView.addListener(("entitiesToBeExported"), function(e) {
        if (!this._socket.slotExists("exportEntities")) {
          this._socket.on("exportEntities", function(val) {
            if (val.type === "exportEntities") {
              console.log("Entities exported: ", val.value);
            }
          }, this);
        }
        this._socket.emit("exportEntities", [this._getActiveUserName(), e.getData()]);
      }, this);

      this._threeView.addListener(("SceneToBeExported"), function(e) {
        if (!this._socket.slotExists("exportScene")) {
          this._socket.on("exportScene", function(val) {
            if (val.type === "exportScene") {
              console.log("Scene exported: ", val.value);
            }
          }, this);
        }
        this._socket.emit("exportScene", [this._getActiveUserName(), e.getData()]);
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

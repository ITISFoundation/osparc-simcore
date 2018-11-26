/* global document */
/* global window */
/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "enforceInMethodNames": true, "allow": ["__dirtyColors"] }] */

const NO_TOOL = 0;
const TOOL_ACTIVE = 1;
const ENTITY_PICKING = 2;
const FACE_PICKING = 3;

qx.Class.define("qxapp.component.ThreeView", {
  extend: qx.ui.container.Composite,

  construct : function(width, height, backgroundColor) {
    this.base(arguments);
    this.set({
      width: width,
      height: height
    });

    let box = new qx.ui.layout.VBox();
    box.set({
      spacing: 10,
      alignX: "center",
      alignY: "middle"
    });

    this.set({
      layout: box
    });

    this.__transformControls = [];
    this.__entities = [];

    this.__threeWrapper = new qxapp.wrappers.ThreeWrapper();

    this.__threeWrapper.addListener("ThreeLibReady", e => {
      let ready = e.getData();
      if (ready) {
        this.__threeDViewer = new qx.ui.core.Widget();
        this.add(this.__threeDViewer, {
          flex: 1
        });

        this.__threeDViewer.addListenerOnce("appear", function() {
          this.__threeDViewer.getContentElement().getDomElement()
            .appendChild(this.__threeWrapper.getDomElement());

          this.__threeWrapper.setBackgroundColor(backgroundColor);
          // this.__threeWrapper.SetCameraPosition(18, 0, 25);
          this.__threeWrapper.setCameraPosition(21, 21, 9); // Z up
          this.__threeWrapper.setSize(this.getWidth(), this.getHeight());

          document.addEventListener("mousedown", this._onMouseDown.bind(this), false);
          document.addEventListener("mousemove", this._onMouseHover.bind(this), false);

          window.addEventListener("resize", function() {
            this.set({
              width: window.innerWidth,
              height: window.innerHeight
            });
            this.__threeWrapper.setSize(window.innerWidth, window.innerHeight);
          }, this);

          this._render();

          this.fireDataEvent("ThreeViewReady", true);
        }, this);
      } else {
        console.log("Three.js was not loaded");
      }
    }, this);

    this.__threeWrapper.addListener(("EntityToBeAdded"), function(e) {
      let newEntity = e.getData();
      if (newEntity) {
        this.addEntityToScene(newEntity);
      }
    }, this);

    this.__threeWrapper.addListener(("SceneToBeExported"), function(e) {
      this.fireDataEvent("SceneToBeExported", e.getData());
    }, this);
  },

  events : {
    "entitySelected": "qx.event.type.Data",
    "entitySelectedAdd": "qx.event.type.Data",
    "entityAdded": "qx.event.type.Data",
    "entityRemoved": "qx.event.type.Data",
    "entitiesToBeExported": "qx.event.type.Data",
    "SceneToBeExported": "qx.event.type.Data",
    "ThreeViewReady": "qx.event.type.Data"
  },

  members: {
    __threeDViewer: null,
    __threeWrapper: null,
    __transformControls: null,
    __entities: null,
    __intersected: null,
    __selectionMode: NO_TOOL,
    __activeTool: null,

    getThreeWrapper: function() {
      return this.__threeWrapper;
    },

    getEntities: function() {
      return this.__entities;
    },

    _render: function() {
      this.__threeWrapper.render();
    },

    _updateTransformControls: function() {
      for (let i = 0; i < this.__transformControls.length; i++) {
        this.__transformControls[i].update();
      }
      this._render();
    },

    _onMouseHover: function(event) {
      event.preventDefault();
      if (this.__selectionMode === NO_TOOL ||
        // hacky
        event.target.nodeName != "CANVAS") {
        return;
      }

      let posX = (event.clientX / window.innerWidth) * 2 - 1;
      let posY = -(event.clientY / window.innerHeight) * 2 + 1;

      if (this.__selectionMode === TOOL_ACTIVE && this.__activeTool) {
        let isShiftKeyPressed = event.shiftKey;
        if (isShiftKeyPressed) {
          return;
        }

        let intersects = this.__threeWrapper.intersectEntities(this.__entities, posX, posY);
        let attended = this.__activeTool.onMouseHover(event, intersects);
        if (attended) {
          return;
        }
      }
    },

    _onMouseDown: function(event) {
      event.preventDefault();
      if (this.__selectionMode === NO_TOOL ||
        // hacky
        event.target.nodeName != "CANVAS") {
        return;
      }

      let posX = (event.clientX / window.innerWidth) * 2 - 1;
      let posY = -(event.clientY / window.innerHeight) * 2 + 1;
      let intersects = this.__threeWrapper.intersectEntities(this.__entities, posX, posY);

      if (this.__selectionMode === TOOL_ACTIVE && this.__activeTool) {
        let isShiftKeyPressed = event.shiftKey;
        if (isShiftKeyPressed) {
          return;
        }

        let attended = this.__activeTool.onMouseDown(event, intersects);
        if (attended) {
          return;
        }
      }

      if (intersects.length > 0) {
        if (this.__selectionMode === ENTITY_PICKING) {
          let isCtrlKeyPressed = event.ctrlKey;
          if (this.__intersected !== null && !isCtrlKeyPressed) {
            this.unhighlightAll();
          }
          this.__intersected = intersects[0];
          if (isCtrlKeyPressed) {
            this.fireDataEvent("entitySelectedAdd", this.__intersected.object.uuid);
          } else {
            this.fireDataEvent("entitySelected", this.__intersected.object.uuid);
          }
          this.highlightEntities([this.__intersected.object.uuid]);
        } else if (this.__selectionMode === FACE_PICKING) {
          if (this.__intersected !== null) {
            this.__intersected.face.color.setHex(this.__intersected.currentHex);
          }
          this.__intersected = intersects[0];
          this.fireDataEvent("entitySelected", null);
          this.__intersected.currentHex = this.__intersected.face.color.getHex();
          const highlightedColor = 0x000000;
          this.__intersected.face.color.setHex(highlightedColor);
        }
        this.__intersected.object.geometry.__dirtyColors = true;
        this.__intersected.object.geometry.colorsNeedUpdate = true;
      } else {
        if (this.__intersected) {
          this.fireDataEvent("entitySelected", null);
          if (this.__selectionMode === ENTITY_PICKING) {
            this.unhighlightAll();
          } else if (this.__selectionMode === FACE_PICKING) {
            this.__intersected.face.color.setHex(this.__intersected.currentHex);
          }
          this.__intersected.object.geometry.__dirtyColors = true;
          this.__intersected.object.geometry.colorsNeedUpdate = true;
        }
        // remove previous intersection object reference
        this.__intersected = null;
      }

      this._render();
    },

    addEntityToScene: function(entity) {
      this.__threeWrapper.addEntityToScene(entity);
      this.__entities.push(entity);
      this.fireDataEvent("entityAdded", [entity.uuid, entity.name]);
    },

    removeAll: function() {
      for (let i = this.__entities.length-1; i >= 0; i--) {
        this.removeEntity(this.__entities[i]);
      }
    },

    removeEntity: function(entity) {
      let uuid = null;
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i] === entity) {
          uuid = this.__entities[i].uuid;
          this.__entities.splice(i, 1);
          break;
        }
      }

      if (uuid) {
        this.__threeWrapper.removeEntityFromSceneById(uuid);
        this.fireDataEvent("entityRemoved", uuid);
        this._render();
      }
    },

    removeEntityByID: function(uuid) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].uuid === uuid) {
          this.removeEntity(this.__entities[i]);
          return;
        }
      }
    },

    startTool: function(myTool) {
      this.__activeTool = myTool;
      this.__activeTool.startTool();
      this.setSelectionMode(TOOL_ACTIVE);
    },

    stopTool: function() {
      if (this.__activeTool) {
        this.__activeTool.stopTool();
      }
      this.__activeTool = null;
      this.setSelectionMode(NO_TOOL);
    },

    addSnappingPlane: function(fixedAxe = 2, fixedPosition = 0) {
      let instersectionPlane = this.__threeWrapper.createInvisiblePlane(fixedAxe, fixedPosition);
      instersectionPlane.name = "PlaneForSnapping";
      this.__entities.push(instersectionPlane);
    },

    removeSnappingPlane: function() {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].name === "PlaneForSnapping") {
          this.__entities.splice(i, 1);
          break;
        }
      }
    },

    startMoveTool: function(selObjId, mode) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].uuid === selObjId) {
          let transformControl = this.__threeWrapper.createTransformControls();
          transformControl.addEventListener("change", this._updateTransformControls.bind(this));
          if (mode === "rotate") {
            transformControl.setMode("rotate");
          } else {
            transformControl.setMode("translate");
          }
          transformControl.attach(this.__entities[i]);
          this.__transformControls.push(transformControl);
          this.__threeWrapper.addEntityToScene(transformControl);
        }
      }
      this._render();
    },

    stopMoveTool: function() {
      for (let i = 0; i < this.__transformControls.length; i++) {
        if (this.__threeWrapper.removeEntityFromScene(this.__transformControls[i])) {
          this.__transformControls[i].detach();
        }
      }
      this.__transformControls = [];
      this._render();
    },

    setSelectionMode: function(mode) {
      if (mode === FACE_PICKING) {
        this._showEdges(true);
        this.highlightAll();
      } else {
        this._showEdges(false);
        this.unhighlightAll();
      }

      this.__selectionMode = mode;
      this.stopMoveTool();
      this._render();
    },

    createEntityFromResponse: function(response, name, uuid) {
      let sphereGeometry = this.__threeWrapper.fromEntityMeshToEntity(response[0]);
      // let sphereMaterial = this.__threeWrapper.CreateMeshNormalMaterial();
      let color = response[0].material.diffuse;
      let sphereMaterial = this.__threeWrapper.createNewMaterial(color.r, color.g, color.b);
      let entity = this.__threeWrapper.createEntity(sphereGeometry, sphereMaterial);

      this.__threeWrapper.applyTransformationMatrixToEntity(entity, response[0].transform4x4);

      entity.name = name;
      entity.uuid = uuid;
      this.addEntityToScene(entity);
    },

    highlightAll: function() {
      for (let i = 0; i < this.__entities.length; i++) {
        this.__entities[i].material.opacity = 0.9;
      }
      this._render();
    },

    unhighlightAll: function() {
      for (let i = 0; i < this.__entities.length; i++) {
        this.__entities[i].material.opacity = 0.6;
      }
      this._render();
    },

    highlightEntities: function(ids) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (ids.indexOf(this.__entities[i].uuid) >= 0) {
          this.__entities[i].material.opacity = 0.9;
        }
      }
      this._render();
    },

    showHideEntity: function(id, show) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].uuid === id) {
          this.__entities[i].visible = show;
          break;
        }
      }
      this._render();
    },

    _showEdges: function(showEdges) {
      if (showEdges) {
        for (let i = 0; i < this.__entities.length; i++) {
          let wireframe = this.__threeWrapper.createWireframeFromGeometry(this.__entities[i].geometry);
          this.__entities[i].add(wireframe);
        }
      } else {
        for (let i = 0; i < this.__entities.length; i++) {
          let wireObj = this.__entities[i].getObjectByName("wireframe");
          if (wireObj) {
            this.__entities[i].remove(wireObj);
          }
        }
      }
      this._render();
    },

    importSceneFromBuffer: function(modelBuffer) {
      this.__threeWrapper.importSceneFromBuffer(modelBuffer);
    },

    serializeScene: function(downloadFile, exportSceneAsBinary) {
      this.__threeWrapper.exportScene(downloadFile, exportSceneAsBinary);
    }
  }
});

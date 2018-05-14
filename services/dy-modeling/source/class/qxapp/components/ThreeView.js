/* global document */
/* global window */

const NO_TOOL = 0;
const TOOL_ACTIVE = 1;
const ENTITY_PICKING = 2;
const FACE_PICKING = 3;

qx.Class.define("qxapp.components.ThreeView", {
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

    this._transformControls = [];
    this._entities = [];

    this._threeWrapper = new qxapp.wrappers.ThreeWrapper();

    this._threeWrapper.addListener(("ThreeLibReady"), function(e) {
      let ready = e.getData();
      if (ready) {
        this._threeDViewer = new qx.ui.core.Widget();
        this.add(this._threeDViewer, {
          flex: 1
        });

        this._threeDViewer.addListenerOnce("appear", function() {
          this._threeDViewer.getContentElement().getDomElement()
            .appendChild(this._threeWrapper.getDomElement());

          this._threeWrapper.setBackgroundColor(backgroundColor);
          // this._threeWrapper.SetCameraPosition(18, 0, 25);
          this._threeWrapper.setCameraPosition(21, 21, 9); // Z up
          this._threeWrapper.setSize(this.getWidth(), this.getHeight());

          document.addEventListener("mousedown", this._onMouseDown.bind(this), false);
          document.addEventListener("mousemove", this._onMouseHover.bind(this), false);

          let that = this;
          window.addEventListener("resize", function() {
            that.set({
              width: window.innerWidth,
              height: window.innerHeight
            });
            that._threeWrapper.setSize(window.innerWidth, window.innerHeight);
          }, that);

          this._render();
        }, this);
      } else {
        console.log("Three.js was not loaded");
      }
    }, this);

    this._threeWrapper.addListener(("EntityToBeAdded"), function(e) {
      let newEntity = e.getData();
      if (newEntity) {
        this.addEntityToScene(newEntity);
      }
    }, this);

    this._threeWrapper.addListener(("SceneToBeExported"), function(e) {
      this.fireDataEvent("SceneToBeExported", e.getData());
    }, this);
  },

  events : {
    "entitySelected": "qx.event.type.Data",
    "entitySelectedAdd": "qx.event.type.Data",
    "entityAdded": "qx.event.type.Data",
    "entityRemoved": "qx.event.type.Data",
    "entitiesToBeExported": "qx.event.type.Data",
    "SceneToBeExported": "qx.event.type.Data"
  },

  members: {
    _threeDViewer: null,
    _threeWrapper: null,
    _transformControls: null,
    _entities: null,
    _intersected: null,
    _selectionMode: NO_TOOL,
    _activeTool: null,

    _render : function() {
      this._threeWrapper.render();
    },

    _updateTransformControls : function() {
      for (let i = 0; i < this._transformControls.length; i++) {
        this._transformControls[i].update();
      }
      this._render();
    },

    _onMouseHover : function(event) {
      event.preventDefault();
      if (this._selectionMode === NO_TOOL ||
        // hacky
        event.target.nodeName != "CANVAS") {
        return;
      }

      let posX = (event.clientX / window.innerWidth) * 2 - 1;
      let posY = -(event.clientY / window.innerHeight) * 2 + 1;

      if (this._selectionMode === TOOL_ACTIVE && this._activeTool) {
        let isShiftKeyPressed = event.shiftKey;
        if (isShiftKeyPressed) {
          return;
        }

        let intersects = this._threeWrapper.intersectEntities(this._entities, posX, posY);
        let attended = this._activeTool.onMouseHover(event, intersects);
        if (attended) {
          return;
        }
      }
    },

    _onMouseDown : function(event) {
      event.preventDefault();
      if (this._selectionMode === NO_TOOL ||
        // hacky
        event.target.nodeName != "CANVAS") {
        return;
      }

      let posX = (event.clientX / window.innerWidth) * 2 - 1;
      let posY = -(event.clientY / window.innerHeight) * 2 + 1;
      let intersects = this._threeWrapper.intersectEntities(this._entities, posX, posY);

      if (this._selectionMode === TOOL_ACTIVE && this._activeTool) {
        let isShiftKeyPressed = event.shiftKey;
        if (isShiftKeyPressed) {
          return;
        }

        let attended = this._activeTool.onMouseDown(event, intersects);
        if (attended) {
          return;
        }
      }

      if (intersects.length > 0) {
        if (this._selectionMode === ENTITY_PICKING) {
          let isCtrlKeyPressed = event.ctrlKey;
          if (this._intersected !== null && !isCtrlKeyPressed) {
            this.unhighlightAll();
          }
          this._intersected = intersects[0];
          if (isCtrlKeyPressed) {
            this.fireDataEvent("entitySelectedAdd", this._intersected.object.uuid);
          } else {
            this.fireDataEvent("entitySelected", this._intersected.object.uuid);
          }
          this.highlightEntities([this._intersected.object.uuid]);
        } else if (this._selectionMode === FACE_PICKING) {
          if (this._intersected !== null) {
            this._intersected.face.color.setHex(this._intersected.currentHex);
          }
          this._intersected = intersects[0];
          this.fireDataEvent("entitySelected", null);
          this._intersected.currentHex = this._intersected.face.color.getHex();
          const highlightedColor = 0x000000;
          this._intersected.face.color.setHex(highlightedColor);
        }
        this._intersected.object.geometry.__dirtyColors = true;
        this._intersected.object.geometry.colorsNeedUpdate = true;
      } else {
        if (this._intersected) {
          this.fireDataEvent("entitySelected", null);
          if (this._selectionMode === ENTITY_PICKING) {
            this.unhighlightAll();
          } else if (this._selectionMode === FACE_PICKING) {
            this._intersected.face.color.setHex(this._intersected.currentHex);
          }
          this._intersected.object.geometry.__dirtyColors = true;
          this._intersected.object.geometry.colorsNeedUpdate = true;
        }
        // remove previous intersection object reference
        this._intersected = null;
      }

      this._render();
    },

    addEntityToScene : function(entity) {
      this._threeWrapper.addEntityToScene(entity);
      this._entities.push(entity);
      this.fireDataEvent("entityAdded", [entity.uuid, entity.name]);
    },

    removeAll : function() {
      for (let i = this._entities.length-1; i >= 0; i--) {
        this.removeEntity(this._entities[i]);
      }
    },

    removeEntity : function(entity) {
      let uuid = null;
      for (let i = 0; i < this._entities.length; i++) {
        if (this._entities[i] === entity) {
          uuid = this._entities[i].uuid;
          this._entities.splice(i, 1);
          break;
        }
      }

      if (uuid) {
        this._threeWrapper.removeEntityFromSceneById(uuid);
        this.fireDataEvent("entityRemoved", uuid);
        this._render();
      }
    },

    removeEntityByID : function(uuid) {
      for (let i = 0; i < this._entities.length; i++) {
        if (this._entities[i].uuid === uuid) {
          this.removeEntity(this._entities[i]);
          return;
        }
      }
    },

    startTool : function(myTool) {
      this._activeTool = myTool;
      this._activeTool.startTool();
      this.setSelectionMode(TOOL_ACTIVE);
    },

    stopTool : function() {
      if (this._activeTool) {
        this._activeTool.stopTool();
      }
      this._activeTool = null;
      this.setSelectionMode(NO_TOOL);
    },

    addInvisiblePlane : function(fixed_axe = 2, fixed_position = 0) {
      let instersection_plane = this._threeWrapper.createInvisiblePlane(fixed_axe, fixed_position);
      instersection_plane.name = "InvisiblePlaneForSnapping";
      this._entities.push(instersection_plane);
    },

    removeInvisiblePlane : function() {
      for (let i = 0; i < this._entities.length; i++) {
        if (this._entities[i].name === "InvisiblePlaneForSnapping") {
          this._entities.splice(i, 1);
          break;
        }
      }
    },

    startMoveTool : function(selObjId, mode) {
      for (let i = 0; i < this._entities.length; i++) {
        if (this._entities[i].uuid === selObjId) {
          let transformControl = this._threeWrapper.createTransformControls();
          transformControl.addEventListener("change", this._updateTransformControls.bind(this));
          if (mode === "rotate") {
            transformControl.setMode("rotate");
          } else {
            transformControl.setMode("translate");
          }
          transformControl.attach(this._entities[i]);
          this._transformControls.push(transformControl);
          this._threeWrapper.addEntityToScene(transformControl);
        }
      }
      this._render();
    },

    stopMoveTool : function() {
      for (let i = 0; i < this._transformControls.length; i++) {
        if (this._threeWrapper.removeEntityFromScene(this._transformControls[i])) {
          this._transformControls[i].detach();
        }
      }
      this._transformControls = [];
      this._render();
    },

    setSelectionMode : function(mode) {
      if (mode === FACE_PICKING) {
        this._showEdges(true);
        this.highlightAll();
      } else {
        this._showEdges(false);
        this.unhighlightAll();
      }

      this._selectionMode = mode;
      this.stopMoveTool();
      this._render();
    },

    createEntityFromResponse : function(response, name, uuid) {
      let sphereGeometry = this._threeWrapper.fromEntityMeshToEntity(response[0]);
      // let sphereMaterial = this._threeWrapper.CreateMeshNormalMaterial();
      let color = response[0].material.diffuse;
      let sphereMaterial = this._threeWrapper.createNewMaterial(color.r, color.g, color.b);
      let entity = this._threeWrapper.createEntity(sphereGeometry, sphereMaterial);

      this._threeWrapper.applyTransformationMatrixToEntity(entity, response[0].transform4x4);

      entity.name = name;
      entity.uuid = uuid;
      this.addEntityToScene(entity);
    },

    highlightAll : function() {
      for (let i = 0; i < this._entities.length; i++) {
        this._entities[i].material.opacity = 0.9;
      }
      this._render();
    },

    unhighlightAll : function() {
      for (let i = 0; i < this._entities.length; i++) {
        this._entities[i].material.opacity = 0.6;
      }
      this._render();
    },

    highlightEntities : function(ids) {
      for (let i = 0; i < this._entities.length; i++) {
        if (ids.indexOf(this._entities[i].uuid) >= 0) {
          this._entities[i].material.opacity = 0.9;
        }
      }
      this._render();
    },

    showHideEntity : function(id, show) {
      for (let i = 0; i < this._entities.length; i++) {
        if (this._entities[i].uuid === id) {
          this._entities[i].visible = show;
          break;
        }
      }
      this._render();
    },

    _showEdges : function(show_edges) {
      if (show_edges) {
        for (let i = 0; i < this._entities.length; i++) {
          let wireframe = this._threeWrapper.createWireframeFromGeometry(this._entities[i].geometry);
          this._entities[i].add(wireframe);
        }
      } else {
        for (let i = 0; i < this._entities.length; i++) {
          let wireObj = this._entities[i].getObjectByName("wireframe");
          if (wireObj) {
            this._entities[i].remove(wireObj);
          }
        }
      }
      this._render();
    },

    importSceneFromBuffer : function(model_buffer) {
      this._threeWrapper.importSceneFromBuffer(model_buffer);
    },

    serializeScene : function(downloadFile, exportSceneAsBinary) {
      this._threeWrapper.exportScene(downloadFile, exportSceneAsBinary);
    }
  }
});

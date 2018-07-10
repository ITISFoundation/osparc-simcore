const NO_TOOL = 0;
const TOOL_ACTIVE = 1;

qx.Class.define("qxapp.components.widgets.VTKView", {
  extend: qx.ui.core.Widget,

  construct : function(initWidth, initHeight, backgroundColor) {
    this.base(arguments);

    this.__transformControls = [];
    this.__entities = [];

    this.addListenerOnce("appear", function() {
      let vtkPlaceholder = qx.dom.Element.create("div");
      qx.bom.element.Attribute.set(vtkPlaceholder, "id", "vtkPlaceholder");
      qx.bom.element.Style.set(vtkPlaceholder, "width", "100%");
      qx.bom.element.Style.set(vtkPlaceholder, "height", "100%");

      this.__vtkWrapper = new qxapp.wrappers.VTKWrapper(vtkPlaceholder);
      this.__vtkWrapper.addListener(("VtkLibReady"), function(e) {
        let ready = e.getData();
        if (ready) {
          this.__vtkWrapper.setBackgroundColor(backgroundColor);

          this.getContentElement().getDomElement()
            .appendChild(vtkPlaceholder);

          vtkPlaceholder.setAttribute("width", initWidth);
          vtkPlaceholder.setAttribute("height", initHeight);
          this.__vtkWrapper.setSize(initWidth, initHeight);

          this.addListener("resize", function(eResize) {
            let width = eResize.getData().width;
            let height = eResize.getData().height;
            vtkPlaceholder.setAttribute("width", width);
            vtkPlaceholder.setAttribute("height", height);
            this.__vtkWrapper.setSize(width, height);
          }, this);

          this.__render();
        } else {
          console.log("Vtk.js was not loaded");
        }
      }, this);

      this.__vtkWrapper.addListener(("EntityToBeAdded"), function(e) {
        let newEntity = e.getData();
        if (newEntity) {
          this.addEntityToScene(newEntity);
        }
      }, this);
    }, this);
  },

  events : {
    "entityAdded": "qx.event.type.Data",
    "entityRemoved": "qx.event.type.Data"
  },

  members: {
    __vtkWrapper: null,
    __entities: null,
    __selectionMode: NO_TOOL,
    __activeTool: null,

    importVTKObject : function(path) {
      this.__vtkWrapper.importVTKObject(path);
    },

    getVtkWrapper: function() {
      return this.__vtkWrapper;
    },

    __render: function() {
      this.__vtkWrapper.render();
    },

    addEntityToScene: function(entity) {
      this.__vtkWrapper.addEntityToScene(entity);
      this.__entities.push(entity);
      this.fireDataEvent("entityAdded", [qxapp.utils.Utils.uuidv4(), "bunny.vtk"]);
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
        this.__vtkWrapper.removeEntityFromSceneById(uuid);
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

    setSelectionMode: function(mode) {
      this.__selectionMode = mode;
      this.stopMoveTool();
      this.__render();
    },

    highlightAll: function() {
      /*
      for (let i = 0; i < this.__entities.length; i++) {
        this.__entities[i].material.opacity = 0.9;
      }
      */
      this.__render();
    },

    unhighlightAll: function() {
      /*
      for (let i = 0; i < this.__entities.length; i++) {
        this.__entities[i].material.opacity = 0.6;
      }
      */
      this.__render();
    },

    highlightEntities: function(ids) {
      /*
      for (let i = 0; i < this.__entities.length; i++) {
        if (ids.indexOf(this.__entities[i].uuid) >= 0) {
          this.__entities[i].material.opacity = 0.9;
        }
      }
      */
      this.__render();
    },

    showHideEntity: function(id, show) {
      /*
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].uuid === id) {
          this.__entities[i].visible = show;
          break;
        }
      }
      */
      this.__render();
    }
  }
});

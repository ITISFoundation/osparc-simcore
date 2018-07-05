const NO_TOOL = 0;
const TOOL_ACTIVE = 1;

qx.Class.define("qxapp.components.widgets.VTKView", {
  extend: qx.ui.core.Widget,

  construct : function(initWidth, initHeight, backgroundColor) {
    this.base(arguments);

    this.__transformControls = [];
    this.__entities = [];

    this.addListenerOnce("appear", function() {
      this.__vtkWrapper = new qxapp.wrappers.VTKWrapper();
      this.__vtkWrapper.addListener(("VtkLibReady"), function(e) {
        let ready = e.getData();
        if (ready) {
          console.log(this.__vtkWrapper);

          let currentView = this.__vtkWrapper.getDomElement();
          if (currentView) {
            this.getContentElement().getDomElement()
              .appendChild(currentView);
          }

          this.addListener("resize", function(eResize) {
            let width = eResize.getData().width;
            let height = eResize.getData().height;
            this.__vtkWrapper.setSize(width, height);
          }, this);

          this.__render();
        } else {
          console.log("Vtk.js was not loaded");
        }
      }, this);
    }, this);
  },

  members: {
    __vtkWrapper: null,
    __entities: null,
    __selectionMode: NO_TOOL,
    __activeTool: null,

    getVtkWrapper: function() {
      return this.__vtkWrapper;
    },

    __render: function() {
      this.__vtkWrapper.render();
    },

    addEntityToScene: function(entity) {
      this.__vtkWrapper.addEntityToScene(entity);
      this.__entities.push(entity);
      this.fireDataEvent("entityAdded", [entity.uuid, entity.name]);
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
      for (let i = 0; i < this.__entities.length; i++) {
        this.__entities[i].material.opacity = 0.9;
      }
      this.__render();
    },

    unhighlightAll: function() {
      for (let i = 0; i < this.__entities.length; i++) {
        this.__entities[i].material.opacity = 0.6;
      }
      this.__render();
    },

    highlightEntities: function(ids) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (ids.indexOf(this.__entities[i].uuid) >= 0) {
          this.__entities[i].material.opacity = 0.9;
        }
      }
      this.__render();
    },

    showHideEntity: function(id, show) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].uuid === id) {
          this.__entities[i].visible = show;
          break;
        }
      }
      this.__render();
    }
  }
});

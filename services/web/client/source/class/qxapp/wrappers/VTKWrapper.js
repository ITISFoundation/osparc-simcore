/**
 * @asset(vtk/*)
 * @ignore(vtk)
 */

/* global vtk */
qx.Class.define("qxapp.wrappers.VTKWrapper", {
  extend: qx.core.Object,

  construct: function(rootContainer) {
    // initialize the script loading
    const vtkPath = "vtk/vtk.min.js";
    let dynLoader = new qx.util.DynamicScriptLoader([
      vtkPath
    ]);

    dynLoader.addListenerOnce("ready", function(e) {
      console.log(vtkPath + " loaded");
      this.setLibReady(true);

      let fullScreenRenderer = vtk.Rendering.Misc.vtkFullScreenRenderWindow.newInstance({
        rootContainer: rootContainer
      });
      let actor = vtk.Rendering.Core.vtkActor.newInstance();
      let mapper = vtk.Rendering.Core.vtkMapper.newInstance();
      let cone = vtk.Filters.Sources.vtkConeSource.newInstance();

      actor.setMapper(mapper);
      mapper.setInputConnection(cone.getOutputPort());

      this.__renderer = fullScreenRenderer.getRenderer();
      this.__renderer.addActor(actor);
      this.__renderer.resetCamera();

      this.__renderWindow = fullScreenRenderer.getRenderWindow();

      this.fireDataEvent("VtkLibReady", true);
    }, this);

    dynLoader.addListener("failed", function(e) {
      let data = e.getData();
      console.log("failed to load " + data.script);
      this.fireDataEvent("VtkLibReady", false);
    }, this);

    dynLoader.start();
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  events: {
    "VtkLibReady": "qx.event.type.Data"
  },

  members: {
    __renderer: null,
    __renderWindow: null,

    getDomElement: function() {
      console.log(this.__renderWindow);
      return this.__renderer.domElement;
    },

    render: function() {
      this.__renderWindow.render();
    },

    setSize: function(width, height) {
      console.log("setSize", width, height);
    }
  }
});

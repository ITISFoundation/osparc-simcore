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

      let renderWindow = this.__renderWindow = vtk.Rendering.Core.vtkRenderWindow.newInstance();
      let renderer = this.__renderer = vtk.Rendering.Core.vtkRenderer.newInstance();
      renderWindow.addRenderer(renderer);

      let openglRenderWindow = this.__openglRenderWindow = vtk.Rendering.OpenGL.vtkRenderWindow.newInstance();
      renderWindow.addView(openglRenderWindow);

      openglRenderWindow.setContainer(rootContainer);

      const interactor = vtk.Rendering.Core.vtkRenderWindowInteractor.newInstance();
      interactor.setView(openglRenderWindow);
      interactor.initialize();
      interactor.bindEvents(rootContainer);

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
    "VtkLibReady": "qx.event.type.Data",
    "EntityToBeAdded": "qx.event.type.Data"
  },

  members: {
    __renderer: null,
    __renderWindow: null,
    __openglRenderWindow: null,

    importVTKObject: function(path) {
      let reader = vtk.IO.Legacy.vtkPolyDataReader.newInstance();
      reader.setUrl(path).then(() => {
        let polydata = reader.getOutputData(0);
        let mapper = vtk.Rendering.Core.vtkMapper.newInstance();
        let actor = vtk.Rendering.Core.vtkActor.newInstance();

        actor.setMapper(mapper);
        mapper.setInputData(polydata);

        // let pieces = path.split("/");
        // let name = pieces[pieces.length-1];
        // actor.name = name;
        // actor.uuid = qxapp.utils.Utils.uuidv4();

        this.fireDataEvent("EntityToBeAdded", actor);
      }, this);
    },

    addEntityToScene: function(entity) {
      this.__renderer.addActor(entity);
      this.render();
    },

    render: function() {
      this.__renderWindow.render();
    },

    setSize: function(width, height) {
      this.__openglRenderWindow.setSize(width, height);
      this.render();
    },

    setBackgroundColor: function(color) {
      const rgb = qxapp.utils.Utils.hexToRgb(color);
      this.__renderer.setBackground([rgb.r/256.0, rgb.g/256.0, rgb.b/256.0]);
      this.render();
    },

    __getCone: function() {
      let actor = vtk.Rendering.Core.vtkActor.newInstance();
      let mapper = vtk.Rendering.Core.vtkMapper.newInstance();
      let cone = vtk.Filters.Sources.vtkConeSource.newInstance();

      actor.setMapper(mapper);
      mapper.setInputConnection(cone.getOutputPort());

      return actor;
    }
  }
});

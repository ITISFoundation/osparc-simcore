/* global window */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(projectId) {
    this.base(arguments, "horizontal");

    this.setProjectId(String(projectId));

    let mainPanel = this.__mainPanel = new qxapp.desktop.mainPanel.MainPanel();
    let sidePanel = this.__sidePanel = new qxapp.desktop.sidePanel.SidePanel().set({
      minWidth: 0,
      maxWidth: 600
    });

    this.add(mainPanel, 0);
    this.add(sidePanel, 1);

    this.initDefault();
    this.connectEvents();
    /*
    this.__settingsView.addListener("ShowViewer", function(e) {
      let data = e.getData();
      let viewerWin = this.__createBrowserWindow(data.url, data.name);

      //  const metadata = e.getData().metadata;
      //  const nodeId = e.getData().nodeId;
      //  let url = "http://" + window.location.hostname + ":" + metadata.viewer.port;
      //  let viewerWin = this.__createBrowserWindow(url, metadata.name);

      this.__workbench.addWindowToDesktop(viewerWin);

      // Workaround for updating inputs
      if (data.name === "3d-viewer") {
        let urlUpdate = "http://" + window.location.hostname + ":" + data.viewer.port + "/retrieve";
        let req = new qx.io.request.Xhr();
        req.set({
          url: urlUpdate,
          method: "POST"
        });
        req.send();
      }
    }, this);
    */
  },

  properties: {
    projectId: {
      check: "String",
      nullable: false
    },

    canStart: {
      nullable: false,
      init: true,
      check: "Boolean",
      apply : "__applyCanStart"
    }
  },

  members: {
    __pipelineId: null,
    __mainPanel: null,
    __sidePanel: null,
    __workbench: null,
    __miniWorkbench: null,
    __extraView: null,
    __settingsView: null,
    __transDeco: null,
    __splitter: null,
    __projectDocument: null,

    initDefault: function() {
      const projectId = this.getProjectId();
      if (projectId === null || projectId === undefined) {
        return;
      }

      let project = this.__projectDocument = this.__getProjectDocument(projectId);
      let workbench = this.__workbench = new qxapp.components.workbench.Workbench(project.getWorkbench());
      this.__mainPanel.setMainView(workbench);


      let miniWorkbench = this.__miniWorkbench = new qxapp.components.workbench.WorkbenchMini(project.getWorkbench());
      this.__sidePanel.setTopView(miniWorkbench);

      let extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
        backgroundColor: "blue",
        minHeight: 200,
        maxHeight: 500
      });
      this.__sidePanel.setMidView(extraView);

      let settingsView = this.__settingsView = new qxapp.components.workbench.SettingsView().set({
        minHeight: 200,
        maxHeight: 500
      });
      this.__sidePanel.setBottomView(settingsView);
    },

    connectEvents: function() {
      this.__mainPanel.getControls().addListener("ShowLogger", function() {
        this.__workbench.showLogger();
      }, this);

      this.__mainPanel.getControls().addListener("StartPipeline", function() {
        if (this.getCanStart()) {
          this.__startPipeline();
        } else {
          this.__workbench.getLogger().info("Can not start pipeline");
        }
      }, this);

      this.__mainPanel.getControls().addListener("StopPipeline", function() {
        this.__stopPipeline();
      }, this);

      [
        this.__workbench,
        this.__miniWorkbench
      ].forEach(wb => {
        wb.addListener("NodeDoubleClicked", function(e) {
          let nodeId = e.getData();
          let node = this.__workbench.getNode(nodeId);
          this.__settingsView.setNode(node);
        }, this);
      });

      this.__projectDocument.addListener("changeWorkbench", function(e) {
        console.log("changeWorkbench", e.getData());
        let newWorkbenchData = e.getData();
        this.__miniWorkbench.loadProject(newWorkbenchData);
      }, this);
    },

    __getProjectDocument: function(projectId) {
      let project = null;
      if (projectId === null || projectId === undefined) {
        project = new qxapp.data.model.Project();
      } else {
        let projectData = qxapp.data.Store.getInstance().getProjectList()[projectId];
        projectData.id = String(projectId);
        project = new qxapp.data.model.Project(projectData);
      }

      return project;
    },

    __startPipeline: function() {
      // ui start pipeline
      // this.clearProgressData();

      let socket = qxapp.wrappers.WebSocket.getInstance();

      // callback for incoming logs
      if (!socket.slotExists("logger")) {
        socket.on("logger", function(data) {
          let d = JSON.parse(data);
          let node = d["Node"];
          let msg = d["Message"];
          this.__updateLogger(node, msg);
        }, this);
      }
      socket.emit("logger");

      // callback for incoming progress
      if (!socket.slotExists("progress")) {
        socket.on("progress", function(data) {
          let d = JSON.parse(data);
          let node = d["Node"];
          let progress = 100*Number.parseFloat(d["Progress"]).toFixed(4);
          this.__workbench.updateProgress(node, progress);
        }, this);
      }

      // post pipeline
      this.__pipelineId = null;
      let currentPipeline = this.__workbench.serializePipeline();
      console.log(currentPipeline);
      let req = new qx.io.request.Xhr();
      let data = {};
      data = currentPipeline;
      data["pipeline_mockup_id"] = qxapp.utils.Utils.uuidv4();
      req.set({
        url: "/start_pipeline",
        method: "POST",
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", function(e) {
        this.setCanStart(true);
        this.__workbench.getLogger().error("Workbench", "Error submitting pipeline");
      }, this);
      req.addListener("fail", function(e) {
        this.setCanStart(true);
        this.__workbench.getLogger().error("Workbench", "Failed submitting pipeline");
      }, this);
      req.send();

      this.__workbench.getLogger().info("Workbench", "Starting pipeline");
    },

    __stopPipeline: function() {
      let req = new qx.io.request.Xhr();
      let data = {};
      data["pipeline_id"] = this.__pipelineId;
      req.set({
        url: "/stop_pipeline",
        method: "POST",
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelineStopped, this);
      req.addListener("error", function(e) {
        this.setCanStart(false);
        this.__workbench.getLogger().error("Workbench", "Error stopping pipeline");
      }, this);
      req.addListener("fail", function(e) {
        this.setCanStart(false);
        this.__workbench.getLogger().error("Workbench", "Failed stopping pipeline");
      }, this);
      // req.send();

      // temporary solution
      this.setCanStart(true);

      this.__workbench.getLogger().info("Workbench", "Stopping pipeline. Not yet implemented");
    },

    __onPipelinesubmitted: function(e) {
      let req = e.getTarget();

      const pipelineId = req.getResponse().pipeline_id;
      this.__workbench.getLogger().debug("Workbench", "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.setCanStart(true);
        this.__pipelineId = null;
        this.__workbench.getLogger().error("Workbench", "Submition failed");
      } else {
        this.setCanStart(false);
        this.__pipelineId = pipelineId;
        this.__workbench.getLogger().info("Workbench", "Pipeline started");
      }
    },

    __onPipelineStopped: function(e) {
      this.__workbench.clearProgressData();

      this.setCanStart(true);
    },

    __applyCanStart: function(value, old) {
      this.__mainPanel.getControls().setCanStart(value);
    },

    __updateLogger: function(nodeId, msg) {
      let node = this.__workbench.getNode(nodeId);
      if (node) {
        this.__workbench.getLogger().info(node.getCaption(), msg);
      }
    },

    __createBrowserWindow: function(url, name) {
      console.log("Accessing:", url);
      let win = new qx.ui.window.Window(name);
      win.setShowMinimize(false);
      win.setLayout(new qx.ui.layout.VBox(5));
      let iframe = new qx.ui.embed.Iframe().set({
        width: 1050,
        height: 700,
        minWidth: 600,
        minHeight: 500,
        source: url,
        decorator : null
      });
      win.add(iframe, {
        flex: 1
      });
      win.moveTo(150, 150);

      win.addListener("dblclick", function(e) {
        e.stopPropagation();
      });

      return win;
    },

    serializeProjectDocument: function() {
      console.log("Workbench: saveProject()");
      this.__workbench.saveProject();
      this.__projectDocument.setWorkbench(this.__workbench.getWorkbenchData());
      console.log(this.__projectDocument.getJsonObject());
    }
  }
});

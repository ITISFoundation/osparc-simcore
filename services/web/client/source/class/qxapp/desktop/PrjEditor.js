/* global window */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(projectUuid) {
    this.base(arguments, "horizontal");

    let project = this.__projectDocument = this.__getProjectDocument(projectUuid);
    this.setProjectId(project.getUuid());

    let mainPanel = this.__mainPanel = new qxapp.desktop.mainPanel.MainPanel().set({
      minWidth: 1000
    });
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
      let iframe = this.__createIFrame(data.url, data.name);

      //  const metadata = e.getData().metadata;
      //  const nodeId = e.getData().nodeId;
      //  let url = "http://" + window.location.hostname + ":" + metadata.viewer.port;
      //  let iframe = this.__createIFrame(url, metadata.name);

      this.showInMainView(iframe);

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

  events: {
    "ChangeMainViewCaption": "qx.event.type.Data"
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
      let project = this.__projectDocument;
      let workbench = this.__workbench = new qxapp.components.workbench.Workbench(project.getWorkbench());
      this.showInMainView(workbench, "Workbench");

      let showWorkbench = new qx.ui.form.Button(this.tr("Show workbench")).set({
        allowGrowX: false
      });
      showWorkbench.addListener("execute", function() {
        this.showInMainView(this.__workbench, "Workbench");
      }, this);
      let miniWorkbench = this.__miniWorkbench = new qxapp.components.workbench.WorkbenchMini(project.getWorkbench());
      let vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      vBox.add(showWorkbench);
      vBox.add(miniWorkbench, {
        flex: 1
      });
      this.__sidePanel.setTopView(vBox);

      let extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
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

      this.__mainPanel.getControls().addListener("SavePressed", function() {
        this.serializeProjectDocument();
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

          switch (node.getMetaData().type) {
            case "dynamic": {
              const widgetManager = qxapp.components.widgets.WidgetManager.getInstance();
              let widget = widgetManager.getWidgetForNode(node);
              widget.addListener("Finished", function() {
                this.showInMainView(this.__workbench, "Workbench");
              }, this);
              this.__mainPanel.getOptions().addListener("ListClicked", function() {
                widget.listClicked();
              }, this);
              this.showInExtraView(new qx.ui.core.Widget());
              this.showInMainView(widget, node.getMetaData().name);
              break;
            }
            case "container": {
              const widgetManager = qxapp.components.widgets.WidgetManager.getInstance();
              let widget = widgetManager.getWidgetForNode(node);
              widget.addListener("NodeDoubleClicked", function(ev) {
                const data = ev.getData();
                this.__workbench.fireDataEvent("NodeDoubleClicked", data);
              }, this);
              this.showInExtraView(widget);
              this.showInMainView(this.__workbench, "Workbench");
              break;
            }
            default: {
              this.showInExtraView(new qx.ui.core.Widget());
              this.showInMainView(this.__workbench, "Workbench");
              break;
            }
          }

          this.__settingsView.setNode(node);
        }, this);
      });

      this.__projectDocument.addListener("changeWorkbench", function(e) {
        console.log("changeWorkbench", e.getData());
        let newWorkbenchData = e.getData();
        this.__miniWorkbench.loadProject(newWorkbenchData);
      }, this);
    },

    showInMainView: function(widget, label) {
      this.__mainPanel.setMainView(widget);
      this.fireDataEvent("ChangeMainViewCaption", label);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.setMidView(widget);
    },

    __getProjectDocument: function(projectId) {
      let project = null;
      if (projectId === null || projectId === undefined) {
        project = new qxapp.data.model.Project();
      } else {
        let projectData = qxapp.data.Store.getInstance().getProjectData(projectId);
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

    __createIFrame: function(url, name) {
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
      this.__projectDocument.set({
        workbench: this.__workbench.getWorkbenchData(),
        lastChangeDate: new Date()
      });
      console.log(this.__projectDocument.getJsonObject());
    }
  }
});

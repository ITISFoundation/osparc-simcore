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
        let urlUpdate = data.url + "/retrieve";
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
    __workbenchView: null,
    __treeView: null,
    __extraView: null,
    __settingsView: null,
    __transDeco: null,
    __splitter: null,
    __projectDocument: null,

    initDefault: function() {
      let project = this.__projectDocument;

      let showWorkbench = new qx.ui.form.Button(this.tr("Show workbench")).set({
        allowGrowX: false
      });
      showWorkbench.addListener("execute", function() {
        this.showInMainView(this.__workbenchView);
        const workbenchModel = this.__projectDocument.getWorkbenchModel();
        this.__workbenchView.loadRoot(workbenchModel);
      }, this);

      let treeView = this.__treeView = new qxapp.components.widgets.TreeTool(project.getWorkbenchModel());
      let vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      vBox.add(showWorkbench);
      vBox.add(treeView);
      this.__sidePanel.setTopView(vBox);

      let workbench = this.__workbenchView = new qxapp.components.workbench.Workbench(project.getWorkbenchModel());
      this.showInMainView(workbench);

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
        this.__workbenchView.showLogger();
      }, this);

      this.__mainPanel.getControls().addListener("SavePressed", function() {
        this.serializeProjectDocument();
      }, this);

      this.__mainPanel.getControls().addListener("StartPipeline", function() {
        if (this.getCanStart()) {
          this.__startPipeline();
        } else {
          this.__workbenchView.getLogger().info("Can not start pipeline");
        }
      }, this);

      this.__mainPanel.getControls().addListener("StopPipeline", function() {
        this.__stopPipeline();
      }, this);

      this.__projectDocument.getWorkbenchModel().addListener("WorkbenchModelChanged", function() {
        console.log("WorkbenchModelChanged", this.__projectDocument.getWorkbenchModel());
        this.__treeView.buildTree();
      }, this);

      [
        this.__treeView,
        this.__workbenchView
      ].forEach(wb => {
        wb.addListener("NodeDoubleClicked", function(e) {
          let nodeId = e.getData();
          let nodeModel = this.__projectDocument.getWorkbenchModel().getNodeModel(nodeId);
          this.__settingsView.setNode(nodeModel);

          let widget;
          if (nodeModel.isContainer()) {
            widget = this.__workbenchView;
          } else if (nodeModel.getMetaData().type === "dynamic") {
            const widgetManager = qxapp.components.widgets.WidgetManager.getInstance();
            widget = widgetManager.getWidgetForNode(nodeModel);
            this.showInExtraView(new qx.ui.core.Widget());
          } else {
            this.showInExtraView(new qx.ui.core.Widget());
            widget = this.__settingsView;
          }

          this.showInMainView(widget, nodeId);

          if (nodeModel.isContainer()) {
            this.__workbenchView.loadContainer(nodeModel);
          }
        }, this);
      });
    },

    showInMainView: function(widget, nodeId) {
      this.__mainPanel.setMainView(widget);
      let nodePath = this.__treeView.getPath(nodeId);
      this.fireDataEvent("ChangeMainViewCaption", nodePath);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.setMidView(widget);
    },

    __getProjectDocument: function(projectId) {
      let project = null;
      if (projectId) {
        let projectData = qxapp.data.Store.getInstance().getProjectData(projectId);
        projectData.id = String(projectId);
        project = new qxapp.data.model.ProjectModel(projectData);
      } else {
        project = new qxapp.data.model.ProjectModel();
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
          this.__workbenchView.updateProgress(node, progress);
        }, this);
      }

      // post pipeline
      this.__pipelineId = null;
      let currentPipeline = this.__workbenchView.serializePipeline();
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
        this.__workbenchView.getLogger().error("Workbench", "Error submitting pipeline");
      }, this);
      req.addListener("fail", function(e) {
        this.setCanStart(true);
        this.__workbenchView.getLogger().error("Workbench", "Failed submitting pipeline");
      }, this);
      req.send();

      this.__workbenchView.getLogger().info("Workbench", "Starting pipeline");
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
        this.__workbenchView.getLogger().error("Workbench", "Error stopping pipeline");
      }, this);
      req.addListener("fail", function(e) {
        this.setCanStart(false);
        this.__workbenchView.getLogger().error("Workbench", "Failed stopping pipeline");
      }, this);
      // req.send();

      // temporary solution
      this.setCanStart(true);

      this.__workbenchView.getLogger().info("Workbench", "Stopping pipeline. Not yet implemented");
    },

    __onPipelinesubmitted: function(e) {
      let req = e.getTarget();

      const pipelineId = req.getResponse().pipeline_id;
      this.__workbenchView.getLogger().debug("Workbench", "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.setCanStart(true);
        this.__pipelineId = null;
        this.__workbenchView.getLogger().error("Workbench", "Submition failed");
      } else {
        this.setCanStart(false);
        this.__pipelineId = pipelineId;
        this.__workbenchView.getLogger().info("Workbench", "Pipeline started");
      }
    },

    __onPipelineStopped: function(e) {
      this.__workbenchView.clearProgressData();

      this.setCanStart(true);
    },

    __applyCanStart: function(value, old) {
      this.__mainPanel.getControls().setCanStart(value);
    },

    __updateLogger: function(nodeId, msg) {
      let node = this.__workbenchView.getNodeUI(nodeId);
      if (node) {
        this.__workbenchView.getLogger().info(node.getCaption(), msg);
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
      this.__projectDocument.set({
        lastChangeDate: new Date()
      });
      console.log("serializeProjectDocument", this.__projectDocument.getJsonObject());
    }
  }
});

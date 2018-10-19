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
      maxWidth: 800,
      width: 600
    });

    this.add(mainPanel, 1); // flex 1
    this.add(sidePanel, 0); // flex 0

    this.initDefault();
    this.connectEvents();
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
    __loggerView: null,
    __settingsView: null,
    __transDeco: null,
    __splitter: null,
    __projectDocument: null,
    __currentNodeId: null,

    initDefault: function() {
      let project = this.__projectDocument;

      let treeView = this.__treeView = new qxapp.component.widget.TreeTool(project.getName(), project.getWorkbenchModel());
      this.__sidePanel.setTopView(treeView);

      let extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
        minHeight: 200,
        maxHeight: 500
      });
      this.__sidePanel.setMidView(extraView);

      let loggerView = this.__loggerView = new qxapp.component.widget.logger.LoggerView();
      this.__sidePanel.setBottomView(loggerView);

      let workbenchView = this.__workbenchView = new qxapp.component.workbench.WorkbenchView(project.getWorkbenchModel());
      this.showInMainView(workbenchView, "root");

      let settingsView = this.__settingsView = new qxapp.component.widget.SettingsView().set({
        minHeight: 200,
        maxHeight: 500
      });
      settingsView.setWorkbenchModel(project.getWorkbenchModel());
    },

    connectEvents: function() {
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
        this.__workbenchModelChanged();
      }, this);

      this.__projectDocument.getWorkbenchModel().addListener("ShowInLogger", e => {
        const data = e.getData();
        const nodeLabel = data.nodeLabel;
        const msg = data.msg;
        this.getLogger().info(nodeLabel, msg);
      }, this);

      [
        this.__treeView,
        this.__workbenchView
      ].forEach(wb => {
        wb.addListener("NodeDoubleClicked", e => {
          let nodeId = e.getData();
          this.nodeSelected(nodeId);
        }, this);
      });

      this.__settingsView.addListener("ShowViewer", e => {
        const data = e.getData();
        const url = data.url;
        const name = data.name;
        // const nodeId = data.nodeId;

        let iFrame = this.__createIFrame(url);
        this.__addWidgetToMainView(iFrame);

        // Workaround for updating inputs
        if (name === "3d-viewer") {
          let urlUpdate = url + "/retrieve";
          let req = new qx.io.request.Xhr();
          req.set({
            url: urlUpdate,
            method: "POST"
          });
          req.send();
        }
      }, this);
    },

    nodeSelected: function(nodeId) {
      if (!nodeId) {
        return;
      }

      this.__currentNodeId = nodeId;
      this.__treeView.nodeSelected(nodeId);

      if (nodeId === "root") {
        const workbenchModel = this.__projectDocument.getWorkbenchModel();
        this.__workbenchView.loadModel(workbenchModel);
        this.showInMainView(this.__workbenchView, nodeId);
      } else {
        let nodeModel = this.__projectDocument.getWorkbenchModel().getNodeModel(nodeId);

        let widget;
        if (nodeModel.isContainer()) {
          widget = this.__workbenchView;
        } else {
          this.__settingsView.setNodeModel(nodeModel);
          if (nodeModel.getMetaData().type === "dynamic") {
            const widgetManager = qxapp.component.widget.WidgetManager.getInstance();
            widget = widgetManager.getWidgetForNode(nodeModel);
            if (!widget) {
              widget = this.__settingsView;
            }
          } else {
            widget = this.__settingsView;
          }
        }
        this.showInMainView(widget, nodeId);

        if (nodeModel.isContainer()) {
          this.__workbenchView.loadModel(nodeModel);
        }
      }
    },

    __workbenchModelChanged: function() {
      this.__treeView.buildTree();
      this.__treeView.nodeSelected(this.__currentNodeId);
    },

    showInMainView: function(widget, nodeId) {
      if (this.__mainPanel.isPropertyInitialized("mainView")) {
        let previousWidget = this.__mainPanel.getMainView();
        widget.addListener("Finished", function() {
          this.__mainPanel.setMainView(previousWidget);
        }, this);
      }

      this.__mainPanel.setMainView(widget);
      let nodePath = this.__projectDocument.getWorkbenchModel().getPathWithId(nodeId);
      this.fireDataEvent("ChangeMainViewCaption", nodePath);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.setMidView(widget);
    },

    getLogger: function() {
      return this.__loggerView;
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
      const slotName = "logger";
      if (!socket.slotExists(slotName)) {
        socket.on(slotName, function(data) {
          let d = JSON.parse(data);
          let node = d["Node"];
          let msg = d["Message"];
          this.__updateLogger(node, msg);
        }, this);
      }
      socket.emit(slotName);

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
      const saveContainers = false;
      const savePosition = false;
      let currentPipeline = this.__projectDocument.getWorkbenchModel().serializeWorkbench(saveContainers, savePosition);
      console.log(currentPipeline);
      let req = new qx.io.request.Xhr();
      let data = {};
      data = currentPipeline;
      data["pipeline_mockup_id"] = qxapp.utils.Utils.uuidv4();
      req.set({
        url: "/v0/start_pipeline",
        method: "POST",
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", e => {
        this.setCanStart(true);
        this.getLogger().error("Workbench", "Error submitting pipeline");
      }, this);
      req.addListener("fail", e => {
        this.setCanStart(true);
        this.getLogger().error("Workbench", "Failed submitting pipeline");
      }, this);
      req.send();

      this.getLogger().info("Workbench", "Starting pipeline");
    },

    __stopPipeline: function() {
      let req = new qx.io.request.Xhr();
      let data = {};
      data["pipeline_id"] = this.__pipelineId;
      req.set({
        url: "/v0/stop_pipeline",
        method: "POST",
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelineStopped, this);
      req.addListener("error", e => {
        this.setCanStart(false);
        this.getLogger().error("Workbench", "Error stopping pipeline");
      }, this);
      req.addListener("fail", e => {
        this.setCanStart(false);
        this.getLogger().error("Workbench", "Failed stopping pipeline");
      }, this);
      // req.send();

      // temporary solution
      this.setCanStart(true);

      this.getLogger().info("Workbench", "Stopping pipeline. Not yet implemented");
    },

    __onPipelinesubmitted: function(e) {
      let req = e.getTarget();

      const pipelineId = req.getResponse().pipeline_id;
      this.getLogger().debug("Workbench", "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.setCanStart(true);
        this.__pipelineId = null;
        this.getLogger().error("Workbench", "Submition failed");
      } else {
        this.setCanStart(false);
        this.__pipelineId = pipelineId;
        this.getLogger().info("Workbench", "Pipeline started");
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
        this.getLogger().info(node.getCaption(), msg);
      }
    },

    __createIFrame: function(url) {
      let iFrame = new qx.ui.embed.Iframe().set({
        source: url
      });
      return iFrame;
    },

    __addWidgetToMainView: function(widget) {
      let widgetContainer = new qx.ui.container.Composite(new qx.ui.layout.Canvas());

      widgetContainer.add(widget, {
        top: 0,
        right: 0,
        bottom: 0,
        left: 0
      });

      let closeBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/window-close/24",
        zIndex: widget.getZIndex() + 1
      });
      widgetContainer.add(closeBtn, {
        right: 0,
        top: 0
      });
      let previousWidget = this.__mainPanel.getMainView();
      closeBtn.addListener("execute", function() {
        this.__mainPanel.setMainView(previousWidget);
      }, this);
      this.__mainPanel.setMainView(widgetContainer);
    },

    serializeProjectDocument: function() {
      console.log("serializeProject", this.__projectDocument.serializeProject());
    }
  }
});

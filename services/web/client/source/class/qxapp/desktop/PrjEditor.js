/* global window */

/* eslint newline-per-chained-call: 0 */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(projectModel) {
    this.base(arguments, "horizontal");

    this.setProjectModel(projectModel);

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
    projectModel: {
      check: "qxapp.data.model.ProjectModel",
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
    __nodeView: null,
    __currentNodeId: null,

    initDefault: function() {
      let project = this.getProjectModel();

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
      workbenchView.addListener("removeNode", e => {
        const nodeId = e.getData();
        // remove first the connected links
        let connectedLinks = this.getProjectModel().getWorkbenchModel().getConnectedLinks(nodeId);
        for (let i=0; i<connectedLinks.length; i++) {
          const linkId = connectedLinks[i];
          if (this.getProjectModel().getWorkbenchModel().removeLink(linkId)) {
            this.__workbenchView.clearLink(linkId);
          }
        }
        if (this.getProjectModel().getWorkbenchModel().removeNode(nodeId)) {
          this.__workbenchView.clearNode(nodeId);
        }
      }, this);
      workbenchView.addListener("removeLink", e => {
        const linkId = e.getData();
        let workbenchModel = this.getProjectModel().getWorkbenchModel();
        let currentNodeModel = workbenchModel.getNodeModel(this.__currentNodeId);
        let link = workbenchModel.getLinkModel(linkId);
        let removed = false;
        if (currentNodeModel && currentNodeModel.isContainer() && link.getOutputNodeId() === currentNodeModel.getNodeId()) {
          let inputNode = workbenchModel.getNodeModel(link.getInputNodeId());
          inputNode.setIsOutputNode(false);

          // Remove also dependencies from outter nodes
          const cNodeId = inputNode.getNodeId();
          const allNodes = workbenchModel.getNodeModels(true);
          for (const nodeId in allNodes) {
            let node = allNodes[nodeId];
            if (node.isInputNode(cNodeId) && !currentNodeModel.isInnerNode(node.getNodeId())) {
              workbenchModel.removeLink(linkId);
            }
          }
          removed = true;
        } else {
          removed = workbenchModel.removeLink(linkId);
        }
        if (removed) {
          this.__workbenchView.clearLink(linkId);
        }
      }, this);
      this.showInMainView(workbenchView, "root");

      let nodeView = this.__nodeView = new qxapp.component.widget.NodeView().set({
        minHeight: 200
      });
      nodeView.setWorkbenchModel(project.getWorkbenchModel());
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

      this.getProjectModel().getWorkbenchModel().addListener("WorkbenchModelChanged", function() {
        this.__workbenchModelChanged();
      }, this);

      this.getProjectModel().getWorkbenchModel().addListener("ShowInLogger", e => {
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
    },

    nodeSelected: function(nodeId) {
      if (!nodeId) {
        return;
      }

      this.__currentNodeId = nodeId;
      this.__treeView.nodeSelected(nodeId);

      if (nodeId === "root") {
        const workbenchModel = this.getProjectModel().getWorkbenchModel();
        this.__workbenchView.loadModel(workbenchModel);
        this.showInMainView(this.__workbenchView, nodeId);
      } else {
        let nodeModel = this.getProjectModel().getWorkbenchModel().getNodeModel(nodeId);

        let widget;
        if (nodeModel.isContainer()) {
          widget = this.__workbenchView;
        } else {
          this.__nodeView.setNodeModel(nodeModel);
          if (nodeModel.getKey().includes("file-picker")) {
            widget = new qxapp.component.widget.FilePicker(nodeModel);
          } else {
            widget = this.__nodeView;
          }
        }
        this.showInMainView(widget, nodeId);

        if (nodeModel.isContainer()) {
          this.__workbenchView.loadModel(nodeModel);
        }
      }

      // Show screenshots in the ExtraView
      if (nodeId === "root") {
        this.showScreenshotInExtraView("workbench");
      } else {
        let nodeModel = this.getProjectModel().getWorkbenchModel().getNodeModel(nodeId);
        if (nodeModel.isContainer()) {
          this.showScreenshotInExtraView("container");
        } else {
          let nodeKey = nodeModel.getKey();
          if (nodeKey.includes("file-picker")) {
            this.showScreenshotInExtraView("file-picker");
          } else if (nodeKey.includes("modeler")) {
            this.showScreenshotInExtraView("modeler");
          } else if (nodeKey.includes("3d-viewer")) {
            this.showScreenshotInExtraView("postpro");
          } else if (nodeKey.includes("viewer")) {
            this.showScreenshotInExtraView("notebook");
          } else if (nodeKey.includes("jupyter")) {
            this.showScreenshotInExtraView("notebook");
          } else {
            this.showScreenshotInExtraView("form");
          }
        }
      }
    },

    __workbenchModelChanged: function() {
      this.__treeView.populateTree();
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

      let nodesPath = this.getProjectModel().getWorkbenchModel().getPathIds(nodeId);
      this.fireDataEvent("ChangeMainViewCaption", nodesPath);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.setMidView(widget);
    },

    showScreenshotInExtraView: function(name) {
      let imageWidget = new qx.ui.basic.Image("qxapp/screenshot_"+name+".png").set({
        scale: true,
        allowShrinkX: true,
        allowShrinkY: true
      });
      this.__sidePanel.setMidView(imageWidget);
    },

    getLogger: function() {
      return this.__loggerView;
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
      let currentPipeline = this.getProjectModel().getWorkbenchModel().serializeWorkbench(saveContainers, savePosition);
      let req = new qxapp.io.request.ApiRequest("/start_pipeline", "POST");
      let data = {};
      data["workbench"] = currentPipeline;
      data["project_id"] = this.getProjectModel().getUuid();
      console.log(data);
      req.set({
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
      let req = new qxapp.io.request.ApiRequest("/stop_pipeline", "POST");
      let data = {};
      data["project_id"] = this.getProjectModel().getUuid();
      req.set({
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

      const pipelineId = req.getResponse()["project_id"];
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
      let iFrame = new qxapp.component.widget.PersistentIframe(url);
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
      console.log("serializeProject", this.getProjectModel().serializeProject());
    }
  }
});

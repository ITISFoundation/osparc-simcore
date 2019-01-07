/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global window */

/* eslint newline-per-chained-call: 0 */
/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(project) {
    this.base(arguments, "horizontal");

    qxapp.utils.UuidToName.getInstance().setProject(project);

    this.__projectResources = qxapp.io.rest.ResourceFactory.getInstance().createProjectResources();

    this.setProject(project);

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

    this.saveProjectDocument();
    this.__startAutoSave();
  },

  properties: {
    project: {
      check: "qxapp.data.model.Project",
      nullable: false
    },

    canStart: {
      nullable: false,
      init: true,
      check: "Boolean",
      apply: "__applyCanStart"
    }
  },

  events: {
    "changeMainViewCaption": "qx.event.type.Data"
  },

  members: {
    __projectResources: null,
    __pipelineId: null,
    __mainPanel: null,
    __sidePanel: null,
    __workbenchUI: null,
    __treeView: null,
    __extraView: null,
    __loggerView: null,
    __nodeView: null,
    __currentNodeId: null,

    initDefault: function() {
      let project = this.getProject();

      let treeView = this.__treeView = new qxapp.component.widget.TreeTool(project.getName(), project.getWorkbench());
      treeView.addListener("addNode", () => {
        this.__addNode();
      }, this);
      treeView.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.setTopView(treeView);

      let extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
        minHeight: 200,
        maxHeight: 500
      });
      this.__sidePanel.setMidView(extraView);

      let loggerView = this.__loggerView = new qxapp.component.widget.logger.LoggerView();
      this.__sidePanel.setBottomView(loggerView);

      let workbenchUI = this.__workbenchUI = new qxapp.component.workbench.WorkbenchUI(project.getWorkbench());
      workbenchUI.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      workbenchUI.addListener("removeLink", e => {
        const linkId = e.getData();
        let workbench = this.getProject().getWorkbench();
        const currentNode = workbench.getNode(this.__currentNodeId);
        const link = workbench.getLink(linkId);
        let removed = false;
        if (currentNode && currentNode.isContainer() && link.getOutputNodeId() === currentNode.getNodeId()) {
          let inputNode = workbench.getNode(link.getInputNodeId());
          inputNode.setIsOutputNode(false);

          // Remove also dependencies from outter nodes
          const cNodeId = inputNode.getNodeId();
          const allNodes = workbench.getNodes(true);
          for (const nodeId in allNodes) {
            let node = allNodes[nodeId];
            if (node.isInputNode(cNodeId) && !currentNode.isInnerNode(node.getNodeId())) {
              workbench.removeLink(linkId);
            }
          }
          removed = true;
        } else {
          removed = workbench.removeLink(linkId);
        }
        if (removed) {
          this.__workbenchUI.clearLink(linkId);
        }
      }, this);
      this.showInMainView(workbenchUI, "root");

      let nodeView = this.__nodeView = new qxapp.component.widget.NodeView().set({
        minHeight: 200
      });
      nodeView.setWorkbench(project.getWorkbench());
    },

    connectEvents: function() {
      this.__mainPanel.getControls().addListener("startPipeline", function() {
        if (this.getCanStart()) {
          this.__startPipeline();
        } else {
          this.__workbenchUI.getLogger().info("Can not start pipeline");
        }
      }, this);

      this.__mainPanel.getControls().addListener("stopPipeline", function() {
        this.__stopPipeline();
      }, this);

      let workbench = this.getProject().getWorkbench();
      workbench.addListener("workbenchChanged", function() {
        this.__workbenchChanged();
      }, this);

      workbench.addListener("updatePipeline", e => {
        let node = e.getData();
        this.__updatePipeline(node);
      }, this);

      workbench.addListener("showInLogger", ev => {
        const data = ev.getData();
        const nodeLabel = data.nodeLabel;
        const msg = data.msg;
        this.getLogger().info(nodeLabel, msg);
      }, this);

      [
        this.__treeView,
        this.__workbenchUI
      ].forEach(wb => {
        wb.addListener("nodeDoubleClicked", e => {
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

      const workbench = this.getProject().getWorkbench();
      if (nodeId === "root") {
        this.__workbenchUI.loadModel(workbench);
        this.showInMainView(this.__workbenchUI, nodeId);
      } else {
        let node = workbench.getNode(nodeId);

        let widget;
        if (node.isContainer()) {
          widget = this.__workbenchUI;
        } else {
          this.__nodeView.setNode(node);
          if (node.getMetaData().key.includes("file-picker")) {
            widget = new qxapp.component.widget.FilePicker(node, this.getProject().getUuid());
          } else {
            widget = this.__nodeView;
          }
        }
        this.showInMainView(widget, nodeId);

        if (node.isContainer()) {
          this.__workbenchUI.loadModel(node);
        }
      }

      // Show screenshots in the ExtraView
      if (nodeId === "root") {
        this.showScreenshotInExtraView("workbench");
      } else {
        let node = workbench.getNode(nodeId);
        if (node.isContainer()) {
          this.showScreenshotInExtraView("container");
        } else {
          let nodeKey = node.getKey();
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
          } else if (nodeKey.includes("Grid")) {
            this.showScreenshotInExtraView("grid");
          } else if (nodeKey.includes("Voxel")) {
            this.showScreenshotInExtraView("voxels");
          } else {
            this.showScreenshotInExtraView("form");
          }
        }
      }
    },

    __addNode: function() {
      if (this.__mainPanel.getMainView() !== this.__workbenchUI) {
        return;
      }
      this.__workbenchUI.openServicesCatalogue();
    },

    __removeNode: function(nodeId) {
      if (this.__mainPanel.getMainView() !== this.__workbenchUI) {
        return;
      }
      // remove first the connected links
      let workbench = this.getProject().getWorkbench();
      let connectedLinks = workbench.getConnectedLinks(nodeId);
      for (let i=0; i<connectedLinks.length; i++) {
        const linkId = connectedLinks[i];
        if (workbench.removeLink(linkId)) {
          this.__workbenchUI.clearLink(linkId);
        }
      }
      if (workbench.removeNode(nodeId)) {
        this.__workbenchUI.clearNode(nodeId);
      }
    },

    __workbenchChanged: function() {
      this.__treeView.populateTree();
      this.__treeView.nodeSelected(this.__currentNodeId);
    },

    showInMainView: function(widget, nodeId) {
      if (this.__mainPanel.isPropertyInitialized("mainView")) {
        let previousWidget = this.__mainPanel.getMainView();
        widget.addListener("finished", function() {
          this.__mainPanel.setMainView(previousWidget);
        }, this);
      }

      this.__mainPanel.setMainView(widget);

      let nodesPath = this.getProject().getWorkbench().getPathIds(nodeId);
      this.fireDataEvent("changeMainViewCaption", nodesPath);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.setMidView(widget);
    },

    showScreenshotInExtraView: function(name) {
      let imageWidget = new qx.ui.basic.Image("qxapp/screenshot_" + name + ".png").set({
        scale: true,
        allowShrinkX: true,
        allowShrinkY: true
      });
      this.__sidePanel.setMidView(imageWidget);
    },

    getLogger: function() {
      return this.__loggerView;
    },

    __getCurrentPipeline: function() {
      const saveContainers = false;
      const savePosition = false;
      let currentPipeline = this.getProject().getWorkbench().serializeWorkbench(saveContainers, savePosition);
      for (const nodeId in currentPipeline) {
        let currentNode = currentPipeline[nodeId];
        if (currentNode.key.includes("/neuroman")) {
          // HACK: Only Neuroman should enter here
          currentNode.key = "simcore/services/dynamic/modeler/webserver";
          currentNode.version = "2.8.0";
          const modelSelected = currentNode.inputs["inModel"];
          delete currentNode.inputs["inModel"];
          currentNode.inputs["model_name"] = modelSelected;
        }
      }
      return currentPipeline;
    },

    __updatePipeline: function(node) {
      let currentPipeline = this.__getCurrentPipeline();
      let url = "/computation/pipeline/" + encodeURIComponent(this.getProject().getUuid());
      let req = new qxapp.io.request.ApiRequest(url, "PUT");
      let data = {};
      data["workbench"] = currentPipeline;
      req.set({
        requestData: qx.util.Serializer.toJson(data)
      });
      console.log("updating pipeline: " + url);
      console.log(data);

      req.addListener("success", e => {
        this.getLogger().debug("Workbench", "Pipeline successfully updated");
        if (node) {
          node.retrieveInputs();
        }
      }, this);
      req.addListener("error", e => {
        this.getLogger().error("Workbench", "Error updating pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error("Workbench", "Failed updating pipeline");
      }, this);
      req.send();

      this.getLogger().debug("Workbench", "Updating pipeline");
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
          let progress = 100 * Number.parseFloat(d["Progress"]).toFixed(4);
          this.__workbenchUI.updateProgress(node, progress);
        }, this);
      }

      // post pipeline
      this.__pipelineId = null;
      let currentPipeline = this.__getCurrentPipeline();
      let url = "/computation/pipeline/" + encodeURIComponent(this.getProject().getUuid()) + "/start";
      let req = new qxapp.io.request.ApiRequest(url, "POST");
      let data = {};
      data["workbench"] = currentPipeline;
      req.set({
        requestData: qx.util.Serializer.toJson(data)
      });
      console.log("starting pipeline: " + url);
      console.log(data);

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
      data["project_id"] = this.getProject().getUuid();
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
      this.__workbenchUI.clearProgressData();

      this.setCanStart(true);
    },

    __applyCanStart: function(value, old) {
      this.__mainPanel.getControls().setCanStart(value);
    },

    __updateLogger: function(nodeId, msg) {
      let node = this.__workbenchUI.getNodeUI(nodeId);
      if (node) {
        this.getLogger().info(node.getCaption(), msg);
      }
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

    saveProjectDocument: function() {
      let myPrj = this.getProject().serializeProject();
      let resource = this.__projectResources.project;
      resource.addListenerOnce("delSuccess", e => {
        let resources = this.__projectResources.projects;
        resources.post(null, myPrj);
      }, this);
      resource.del({
        "project_id": myPrj["uuid"]
      });
    },

    __startAutoSave: function() {
      let diffPatcher = new qxapp.wrappers.JsonDiffPatch();
      let oldObj = this.getProject().serializeProject();
      // Save every 5 seconds
      const interval = 5000;
      let timer = new qx.event.Timer(interval);
      timer.addListener("interval", () => {
        const newObj = this.getProject().serializeProject();
        const delta = diffPatcher.diff(oldObj, newObj);
        if (delta) {
          let deltaKeys = Object.keys(delta);
          // lastChangeDate should not be taken into account as data change
          const index = deltaKeys.indexOf("lastChangeDate");
          if (index > -1) {
            deltaKeys.splice(index, 1);
          }
          if (deltaKeys.length > 0) {
            this.__saveProjectDocument(newObj);
          }
        }
        oldObj = diffPatcher.clone(newObj);
      }, this);
      timer.start();
    },

    __saveProjectDocument: function(newObj) {
      const prjUuid = this.getProject().getUuid();

      let resource = this.__projectResources.project;
      resource.addListenerOnce("putSuccess", ev => {
        console.log("Project updated");
      }, this);
      resource.put({
        "project_id": prjUuid
      }, newObj);
    }
  }
});

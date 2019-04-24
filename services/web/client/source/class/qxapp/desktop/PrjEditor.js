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

/* eslint newline-per-chained-call: 0 */

qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(project, isNew) {
    this.base(arguments, "horizontal");

    qxapp.utils.UuidToName.getInstance().setProject(project);

    this.__projectResources = qxapp.io.rest.ResourceFactory.getInstance().createProjectResources();

    this.setProject(project);

    let mainPanel = this.__mainPanel = new qxapp.desktop.MainPanel().set({
      minWidth: 1000
    });
    let sidePanel = this.__sidePanel = new qxapp.desktop.SidePanel().set({
      minWidth: 0,
      maxWidth: 800,
      width: 500
    });

    const scroll = new qx.ui.container.Scroll().set({
      minWidth: 0
    });
    scroll.add(sidePanel);

    this.add(mainPanel, 1); // flex 1
    this.add(scroll, 0); // flex 0

    this.initDefault();
    this.connectEvents();

    if (isNew) {
      this.createProjectDocument();
    } else {
      this.updateProjectDocument();
    }
    this.__startAutoSaveTimer();
    this.__attachEventHandlers();
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
    "changeMainViewCaption": "qx.event.type.Data",
    "projectSaved": "qx.event.type.Data"
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
    __autoSaveTimer: null,

    /**
     * Destructor
     */
    destruct: function() {
      this.__stopAutoSaveTimer();
    },

    initDefault: function() {
      let project = this.getProject();

      let treeView = this.__treeView = new qxapp.component.widget.NodesTree(project.getName(), project.getWorkbench());
      treeView.addListener("addNode", () => {
        this.__addNode();
      }, this);
      treeView.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Service tree"), treeView), 0);

      let extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Overview"), extraView), 1);

      let loggerView = this.__loggerView = new qxapp.component.widget.logger.LoggerView();
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Logger"), loggerView), 2);

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
      this.__mainPanel.getControls().addListener("startPipeline", () => {
        if (this.getCanStart()) {
          this.__startPipeline();
        } else {
          this.__workbenchUI.getLogger().info("Can not start pipeline");
        }
      }, this);
      this.__mainPanel.getControls().addListener("stopPipeline", this.__stopPipeline, this);
      this.__mainPanel.getControls().addListener("retrieveInputs", () => {
        this.__updatePipeline();
      }, this);

      let workbench = this.getProject().getWorkbench();
      workbench.addListener("workbenchChanged", this.__workbenchChanged, this);

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
          this.nodeSelected(nodeId, true);
        }, this);
      });

      const workbenchUI = this.__workbenchUI;
      const treeView = this.__treeView;
      treeView.addListener("changeSelectedNode", e => {
        const node = workbenchUI.getNodeUI(e.getData());
        if (node && node.classname.includes("NodeUI")) {
          node.setActive(true);
        }
      });
      workbenchUI.addListener("changeSelectedNode", e => {
        treeView.nodeSelected(e.getData());
      });
    },

    nodeSelected: function(nodeId, openNodeAndParents = false) {
      if (!nodeId) {
        return;
      }
      if (this.__nodeView) {
        this.__nodeView.restoreIFrame();
      }
      this.__currentNodeId = nodeId;
      let widget = this.__getWidgetForNode(nodeId);
      this.showInMainView(widget, nodeId);
      if (widget === this.__workbenchUI) {
        const workbench = this.getProject().getWorkbench();
        if (nodeId === "root") {
          this.__workbenchUI.loadModel(workbench);
        } else {
          let node = workbench.getNode(nodeId);
          this.__workbenchUI.loadModel(node);
        }
      }

      this.__switchExtraView(nodeId);

      this.__treeView.nodeSelected(nodeId, openNodeAndParents);
    },

    __getWidgetForNode: function(nodeId) {
      // Find widget for the given nodeId
      const workbench = this.getProject().getWorkbench();
      let widget = null;
      if (nodeId === "root") {
        widget = this.__workbenchUI;
      } else {
        let node = workbench.getNode(nodeId);
        if (node.isContainer()) {
          if (node.hasDedicatedWidget() && node.showDedicatedWidget()) {
            if (node.isInKey("dash-plot")) {
              widget = new qxapp.component.widget.DashGrid(node);
            }
          }
          if (widget === null) {
            widget = this.__workbenchUI;
          }
        } else {
          this.__nodeView.setNode(node);
          this.__nodeView.buildLayout();
          if (node.isInKey("file-picker")) {
            widget = new qxapp.file.FilePicker(node, this.getProject().getUuid());
            widget.addListener("finished", function() {
              let loadNodeId = "root";
              const filePicker = widget.getNode();
              if (filePicker.isPropertyInitialized("parentNodeId")) {
                loadNodeId = filePicker.getParentNodeId();
              }
              this.nodeSelected(loadNodeId);
            }, this);
          } else {
            widget = this.__nodeView;
          }
        }
      }
      return widget;
    },

    __switchExtraView: function(nodeId) {
      // Show screenshots in the ExtraView
      if (nodeId === "root") {
        this.showScreenshotInExtraView("workbench");
      } else {
        const node = this.getProject().getWorkbench().getNode(nodeId);
        if (node.isContainer()) {
          if (node.isInKey("dash-plot")) {
            this.showScreenshotInExtraView("dash-plot");
          } else {
            this.showScreenshotInExtraView("container");
          }
        } else if (node.isInKey("file-picker")) {
          this.showScreenshotInExtraView("file-picker");
        } else if (node.isInKey("modeler")) {
          this.showScreenshotInExtraView("modeler");
        } else if (node.isInKey("3d-viewer")) {
          this.showScreenshotInExtraView("postpro");
        } else if (node.isInKey("viewer")) {
          this.showScreenshotInExtraView("notebook");
        } else if (node.isInKey("jupyter")) {
          this.showScreenshotInExtraView("notebook");
        } else if (node.isInKey("Grid")) {
          this.showScreenshotInExtraView("grid");
        } else if (node.isInKey("Voxel")) {
          this.showScreenshotInExtraView("voxels");
        } else {
          this.showScreenshotInExtraView("form");
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
      if (nodeId === this.__currentNodeId) {
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
      const node = this.getProject().getWorkbench().getNode(nodeId);
      if (node && node.hasDedicatedWidget()) {
        let dedicatedWrapper = new qx.ui.container.Composite(new qx.ui.layout.VBox());
        const dedicatedWidget = node.getDedicatedWidget();
        const btnLabel = dedicatedWidget ? this.tr("Setup view") : this.tr("Grid view");
        const btnIcon = dedicatedWidget ? "@FontAwesome5Solid/wrench/16" : "@FontAwesome5Solid/eye/16";
        let expertModeBtn = new qx.ui.form.Button().set({
          label: btnLabel,
          icon: btnIcon,
          gap: 10,
          alignX: "right",
          height: 25,
          maxWidth: 150
        });
        expertModeBtn.addListener("execute", () => {
          node.setDedicatedWidget(!dedicatedWidget);
          this.nodeSelected(nodeId);
        }, this);
        dedicatedWrapper.add(expertModeBtn);
        dedicatedWrapper.add(widget, {
          flex: 1
        });
        this.__mainPanel.setMainView(dedicatedWrapper);
      } else {
        this.__mainPanel.setMainView(widget);
      }

      let nodesPath = this.getProject().getWorkbench().getPathIds(nodeId);
      this.fireDataEvent("changeMainViewCaption", nodesPath);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Overview"), widget), 1);
    },

    showScreenshotInExtraView: function(name) {
      let imageWidget = new qx.ui.basic.Image("qxapp/screenshot_" + name + ".png").set({
        scale: true,
        allowShrinkX: true,
        allowShrinkY: true
      });
      const container = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
        height: 300
      });
      container.add(imageWidget);
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Overview"), container), 1);
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
        } else {
          const workbench = this.getProject().getWorkbench();
          const allNodes = workbench.getNodes(true);
          Object.values(allNodes).forEach(node2 => {
            node2.retrieveInputs();
          }, this);
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
      this.getProject().getWorkbench().clearProgressData();

      let socket = qxapp.wrapper.WebSocket.getInstance();

      // callback for incoming logs
      const slotName = "logger";
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        const d = JSON.parse(data);
        const nodeId = d["Node"];
        const msgs = d["Messages"];
        const workbench = this.getProject().getWorkbench();
        const node = workbench.getNode(nodeId);
        const who = node.getLabel();
        this.getLogger().infos(who, msgs);
      }, this);
      socket.emit(slotName);

      // callback for incoming progress
      const slotName2 = "progress";
      socket.removeSlot(slotName2);
      socket.on(slotName2, function(data) {
        const d = JSON.parse(data);
        const nodeId = d["Node"];
        const progress = 100 * Number.parseFloat(d["Progress"]).toFixed(4);
        const workbench = this.getProject().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          node.setProgress(progress);
        }
      }, this);

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
      const resp = e.getTarget().getResponse();
      const pipelineId = resp.data["project_id"];
      this.getLogger().debug("Workbench", "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.setCanStart(true);
        this.__pipelineId = null;
        this.getLogger().error("Workbench", "Submition failed");
      } else {
        // this.setCanStart(false);
        this.__pipelineId = pipelineId;
        this.getLogger().info("Workbench", "Pipeline started");
      }
    },

    __onPipelineStopped: function(e) {
      this.getProject().getWorkbench().clearProgressData();

      this.setCanStart(true);
    },

    __applyCanStart: function(value, old) {
      this.__mainPanel.getControls().setCanStart(value);
    },

    __startAutoSaveTimer: function() {
      let diffPatcher = qxapp.wrapper.JsonDiffPatch.getInstance();
      // Save every 5 seconds
      const interval = 5000;
      let timer = this.__autoSaveTimer = new qx.event.Timer(interval);
      timer.addListener("interval", () => {
        const newObj = this.getProject().serializeProject();
        const delta = diffPatcher.diff(this.__lastSavedPrj, newObj);
        if (delta) {
          let deltaKeys = Object.keys(delta);
          // lastChangeDate should not be taken into account as data change
          const index = deltaKeys.indexOf("lastChangeDate");
          if (index > -1) {
            deltaKeys.splice(index, 1);
          }
          if (deltaKeys.length > 0) {
            this.updateProjectDocument(newObj);
          }
        }
      }, this);
      timer.start();
    },

    __stopAutoSaveTimer: function() {
      if (this.__autoSaveTimer && this.__autoSaveTimer.isEnabled()) {
        this.__autoSaveTimer.stop();
        this.__autoSaveTimer.setEnabled(false);
      }
    },

    createProjectDocument: function(newObj) {
      if (newObj === undefined) {
        newObj = this.getProject().serializeProject();
      }
      let resources = this.__projectResources.projects;
      resources.addListenerOnce("postSuccess", ev => {
        console.log("Project replaced");
        this.__lastSavedPrj = qxapp.wrapper.JsonDiffPatch.getInstance().clone(newObj);
      }, this);
      resources.post(null, newObj);
    },

    updateProjectDocument: function(newObj) {
      if (newObj === undefined) {
        newObj = this.getProject().serializeProject();
      }
      const prjUuid = this.getProject().getUuid();

      let resource = this.__projectResources.project;
      resource.addListenerOnce("putSuccess", ev => {
        this.fireDataEvent("projectSaved", true);
        this.__lastSavedPrj = qxapp.wrapper.JsonDiffPatch.getInstance().clone(newObj);
      }, this);
      resource.put({
        "project_id": prjUuid
      }, newObj);
    },

    __attachEventHandlers: function() {
      this.__blocker.addListener("tap", this.__sidePanel.toggleCollapsed.bind(this.__sidePanel));
    }
  }
});

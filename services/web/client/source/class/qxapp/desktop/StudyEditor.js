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

qx.Class.define("qxapp.desktop.StudyEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(study) {
    this.base(arguments, "horizontal");

    qxapp.utils.UuidToName.getInstance().setStudy(study);

    this.__studyResources = qxapp.io.rest.ResourceFactory.getInstance().createStudyResources();

    this.setStudy(study);

    let mainPanel = this.__mainPanel = new qxapp.desktop.MainPanel().set({
      minWidth: 1000
    });
    let sidePanel = this.__sidePanel = new qxapp.desktop.SidePanel().set({
      minWidth: 0,
      maxWidth: 800,
      width: 500
    });

    const scroll = this.__scrollContainer = new qx.ui.container.Scroll().set({
      minWidth: 0
    });
    scroll.add(sidePanel);

    this.add(mainPanel, 1); // flex 1
    this.add(scroll, 0); // flex 0

    this.initDefault();
    this.connectEvents();

    this.__startAutoSaveTimer();
    this.__attachEventHandlers();
  },

  properties: {
    study: {
      check: "qxapp.data.model.Study",
      nullable: false
    }
  },

  events: {
    "changeMainViewCaption": "qx.event.type.Data",
    "studySaved": "qx.event.type.Data"
  },

  members: {
    __studyResources: null,
    __pipelineId: null,
    __mainPanel: null,
    __sidePanel: null,
    __scrollContainer: null,
    __workbenchUI: null,
    __nodesTree: null,
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
      const study = this.getStudy();

      const treeView = this.__nodesTree = new qxapp.component.widget.NodesTree(study.getName(), study.getWorkbench());
      treeView.addListener("addNode", () => {
        this.__addNode();
      }, this);
      treeView.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Service tree"), treeView), 0);

      const extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Overview"), extraView).set({
        collapsed: true
      }), 1);

      const loggerView = this.__loggerView = new qxapp.component.widget.logger.LoggerView(study.getWorkbench());
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Logger"), loggerView), 2);

      const workbenchUI = this.__workbenchUI = new qxapp.component.workbench.WorkbenchUI(study.getWorkbench());
      workbenchUI.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      workbenchUI.addListener("removeEdge", e => {
        const edgeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const currentNode = workbench.getNode(this.__currentNodeId);
        const edge = workbench.getEdge(edgeId);
        let removed = false;
        if (currentNode && currentNode.isContainer() && edge.getOutputNodeId() === currentNode.getNodeId()) {
          let inputNode = workbench.getNode(edge.getInputNodeId());
          inputNode.setIsOutputNode(false);

          // Remove also dependencies from outter nodes
          const cNodeId = inputNode.getNodeId();
          const allNodes = workbench.getNodes(true);
          for (const nodeId in allNodes) {
            let node = allNodes[nodeId];
            if (node.isInputNode(cNodeId) && !currentNode.isInnerNode(node.getNodeId())) {
              workbench.removeEdge(edgeId);
            }
          }
          removed = true;
        } else {
          removed = workbench.removeEdge(edgeId);
        }
        if (removed) {
          this.__workbenchUI.clearEdge(edgeId);
        }
      }, this);
      this.showInMainView(workbenchUI, "root");

      const nodeView = this.__nodeView = new qxapp.component.widget.NodeView().set({
        minHeight: 200
      });
      nodeView.setWorkbench(study.getWorkbench());
    },

    connectEvents: function() {
      this.__mainPanel.getControls().addListener("startPipeline", this.__startPipeline, this);
      this.__mainPanel.getControls().addListener("stopPipeline", this.__stopPipeline, this);
      this.__mainPanel.getControls().addListener("retrieveInputs", this.__updatePipeline, this);

      let workbench = this.getStudy().getWorkbench();
      workbench.addListener("workbenchChanged", this.__workbenchChanged, this);

      workbench.addListener("updatePipeline", e => {
        let node = e.getData();
        this.__updatePipeline(node);
      }, this);

      workbench.addListener("showInLogger", ev => {
        const data = ev.getData();
        const nodeId = data.nodeId;
        const msg = data.msg;
        this.getLogger().info(nodeId, msg);
      }, this);

      [
        this.__nodesTree,
        this.__workbenchUI
      ].forEach(wb => {
        wb.addListener("nodeDoubleClicked", e => {
          let nodeId = e.getData();
          this.nodeSelected(nodeId, true);
        }, this);
      });

      const workbenchUI = this.__workbenchUI;
      const treeView = this.__nodesTree;
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
        this.__loggerView.setCurrentNodeId();
        return;
      }
      if (this.__nodeView) {
        this.__nodeView.restoreIFrame();
      }
      this.__currentNodeId = nodeId;
      const widget = this.__getWidgetForNode(nodeId);
      const workbench = this.getStudy().getWorkbench();
      if (widget != this.__workbenchUI && workbench.getNode(nodeId).isInKey("file-picker")) {
        // open file picker in window
        const filePicker = new qx.ui.window.Window(widget.getNode().getLabel()).set({
          layout: new qx.ui.layout.Grow(),
          contentPadding: 0,
          width: 570,
          height: 450,
          appearance: "service-window",
          showMinimize: false,
          modal: true
        });
        const showParentWorkbench = () => {
          const node = widget.getNode();
          this.nodeSelected(node.getParentNodeId() || "root");
        };
        filePicker.add(widget);
        qx.core.Init.getApplication().getRoot().add(filePicker);
        filePicker.show();
        filePicker.center();

        widget.addListener("finished", () => filePicker.close(), this);
        filePicker.addListener("close", () => showParentWorkbench());
      } else {
        this.showInMainView(widget, nodeId);
      }
      if (widget === this.__workbenchUI) {
        if (nodeId === "root") {
          this.__workbenchUI.loadModel(workbench);
        } else {
          let node = workbench.getNode(nodeId);
          this.__workbenchUI.loadModel(node);
        }
      }

      this.__switchExtraView(nodeId);

      this.__nodesTree.nodeSelected(nodeId, openNodeAndParents);
      this.__loggerView.setCurrentNodeId(nodeId);
    },

    __getWidgetForNode: function(nodeId) {
      // Find widget for the given nodeId
      const workbench = this.getStudy().getWorkbench();
      let widget = null;
      if (nodeId === "root") {
        widget = this.__workbenchUI;
      } else {
        let node = workbench.getNode(nodeId);
        if (node.isContainer()) {
          if (node.hasDedicatedWidget() && node.showDedicatedWidget()) {
            if (node.isInKey("multi-plot")) {
              widget = new qxapp.component.widget.DashGrid(node);
            }
          }
          if (widget === null) {
            widget = this.__workbenchUI;
          }
        } else if (node.isInKey("file-picker")) {
          widget = new qxapp.file.FilePicker(node, this.getStudy().getUuid());
        } else {
          this.__nodeView.setNode(node);
          this.__nodeView.buildLayout();
          widget = this.__nodeView;
        }
      }
      return widget;
    },

    __switchExtraView: function(nodeId) {
      // Show screenshots in the ExtraView
      if (nodeId === "root") {
        this.showScreenshotInExtraView("workbench");
      } else {
        const node = this.getStudy().getWorkbench().getNode(nodeId);
        if (node.isContainer()) {
          if (node.isInKey("multi-plot")) {
            this.showScreenshotInExtraView("multi-plot");
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
      this.__workbenchUI.openServiceCatalog();
    },

    __removeNode: function(nodeId) {
      if (nodeId === this.__currentNodeId) {
        return false;
      }

      const workbench = this.getStudy().getWorkbench();
      const connectedEdges = workbench.getConnectedEdges(nodeId);
      if (workbench.removeNode(nodeId)) {
        // remove first the connected edges
        for (let i=0; i<connectedEdges.length; i++) {
          const edgeId = connectedEdges[i];
          this.__workbenchUI.clearEdge(edgeId);
        }
        this.__workbenchUI.clearNode(nodeId);
        return true;
      }
      return false;
    },

    __removeEdge: function(edgeId) {
      const workbench = this.getStudy().getWorkbench();
      if (workbench.removeEdge(edgeId, this.__currentNodeId)) {
        this.__workbenchUI.clearEdge(edgeId);
      }
    },

    __workbenchChanged: function() {
      this.__nodesTree.populateTree();
      this.__nodesTree.nodeSelected(this.__currentNodeId);
    },

    showInMainView: function(widget, nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
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

      let nodesPath = this.getStudy().getWorkbench().getPathIds(nodeId);
      this.fireDataEvent("changeMainViewCaption", nodesPath);
    },

    showInExtraView: function(widget) {
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Overview"), widget).set({
        collapsed: true
      }), 1);
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
      this.__sidePanel.addOrReplaceAt(new qxapp.desktop.PanelView(this.tr("Overview"), container).set({
        collapsed: true
      }), 1);
    },

    getLogger: function() {
      return this.__loggerView;
    },

    __getCurrentPipeline: function() {
      const saveContainers = false;
      const savePosition = false;
      let currentPipeline = this.getStudy().getWorkbench().serializeWorkbench(saveContainers, savePosition);
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
      let url = "/computation/pipeline/" + encodeURIComponent(this.getStudy().getUuid());
      let req = new qxapp.io.request.ApiRequest(url, "PUT");
      let data = {};
      data["workbench"] = currentPipeline;
      req.set({
        requestData: qx.util.Serializer.toJson(data)
      });
      console.log("updating pipeline: " + url);
      console.log(data);

      req.addListener("success", e => {
        this.getLogger().debug(null, "Pipeline successfully updated");
        if (node) {
          node.retrieveInputs();
        } else {
          const workbench = this.getStudy().getWorkbench();
          const allNodes = workbench.getNodes(true);
          Object.values(allNodes).forEach(node2 => {
            node2.retrieveInputs();
          }, this);
        }
      }, this);
      req.addListener("error", e => {
        this.getLogger().error(null, "Error updating pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error(null, "Failed updating pipeline");
      }, this);
      req.send();

      this.getLogger().debug(null, "Updating pipeline");
    },

    __startPipeline: function() {
      if (!qxapp.data.Permissions.getInstance().canDo("study.start", true)) {
        return false;
      }

      return this.updateStudyDocument(null, this.__doStartPipeline);
    },

    __doStartPipeline: function() {
      this.getStudy().getWorkbench().clearProgressData();

      const socket = qxapp.wrapper.WebSocket.getInstance();

      // callback for incoming logs
      const slotName = "logger";
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        const d = JSON.parse(data);
        const nodeId = d["Node"];
        const msgs = d["Messages"];
        this.getLogger().infos(nodeId, msgs);
      }, this);
      socket.emit(slotName);

      // callback for incoming progress
      const slotName2 = "progress";
      socket.removeSlot(slotName2);
      socket.on(slotName2, function(data) {
        const d = JSON.parse(data);
        const nodeId = d["Node"];
        const progress = 100 * Number.parseFloat(d["Progress"]).toFixed(4);
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          node.setProgress(progress);
        }
      }, this);

      // post pipeline
      this.__pipelineId = null;
      const url = "/computation/pipeline/" + encodeURIComponent(this.getStudy().getUuid()) + "/start";
      const req = new qxapp.io.request.ApiRequest(url, "POST");
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", e => {
        this.getLogger().error(null, "Error submitting pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error(null, "Failed submitting pipeline");
      }, this);
      req.send();

      this.getLogger().info(null, "Starting pipeline");
      return true;
    },

    __stopPipeline: function() {
      if (!qxapp.data.Permissions.getInstance().canDo("study.stop", true)) {
        return false;
      }

      let req = new qxapp.io.request.ApiRequest("/stop_pipeline", "POST");
      let data = {};
      data["project_id"] = this.getStudy().getUuid();
      req.set({
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelineStopped, this);
      req.addListener("error", e => {
        this.getLogger().error(null, "Error stopping pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error(null, "Failed stopping pipeline");
      }, this);
      // req.send();

      this.getLogger().info(null, "Stopping pipeline. Not yet implemented");
      return true;
    },

    __onPipelinesubmitted: function(e) {
      const resp = e.getTarget().getResponse();
      const pipelineId = resp.data["project_id"];
      this.getLogger().debug(null, "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.__pipelineId = null;
        this.getLogger().error(null, "Submition failed");
      } else {
        this.__pipelineId = pipelineId;
        this.getLogger().info(null, "Pipeline started");
      }
    },

    __onPipelineStopped: function(e) {
      this.getStudy().getWorkbench().clearProgressData();
    },

    __startAutoSaveTimer: function() {
      let diffPatcher = qxapp.wrapper.JsonDiffPatch.getInstance();
      // Save every 5 seconds
      const interval = 5000;
      let timer = this.__autoSaveTimer = new qx.event.Timer(interval);
      timer.addListener("interval", () => {
        const newObj = this.getStudy().serializeStudy();
        const delta = diffPatcher.diff(this.__lastSavedPrj, newObj);
        if (delta) {
          let deltaKeys = Object.keys(delta);
          // lastChangeDate should not be taken into account as data change
          const index = deltaKeys.indexOf("lastChangeDate");
          if (index > -1) {
            deltaKeys.splice(index, 1);
          }
          if (deltaKeys.length > 0) {
            this.updateStudyDocument(newObj);
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

    updateStudyDocument: function(newObj, cb) {
      if (newObj === null || newObj === undefined) {
        newObj = this.getStudy().serializeStudy();
      }
      const prjUuid = this.getStudy().getUuid();

      let resource = this.__studyResources.project;
      resource.addListenerOnce("putSuccess", ev => {
        this.fireDataEvent("studySaved", true);
        this.__lastSavedPrj = qxapp.wrapper.JsonDiffPatch.getInstance().clone(newObj);
        if (cb) {
          cb.call(this);
        }
      }, this);
      resource.put({
        "project_id": prjUuid
      }, newObj);
    },

    closeStudy: function() {
      this.getStudy().closeStudy();
    },

    __attachEventHandlers: function() {
      this.__blocker.addListener("tap", this.__sidePanel.toggleCollapsed.bind(this.__sidePanel));

      const maximizeIframeCb = msg => {
        this.__blocker.setStyles({
          display: msg.getData() ? "none" : "block"
        });
        this.__scrollContainer.setVisibility(msg.getData() ? "excluded" : "visible");
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);
    }
  }
});

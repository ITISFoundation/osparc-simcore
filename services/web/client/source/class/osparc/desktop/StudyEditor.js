/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint newline-per-chained-call: 0 */

qx.Class.define("osparc.desktop.StudyEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(studyData) {
    this.base(arguments, "horizontal");

    const study = new osparc.data.model.Study(studyData, true);
    study.initWorkbench();
    study.openStudy();

    osparc.utils.UuidToName.getInstance().setStudy(study);

    this.setStudy(study);

    let mainPanel = this.__mainPanel = new osparc.desktop.MainPanel().set({
      minWidth: 1000
    });
    let sidePanel = this.__sidePanel = new osparc.desktop.SidePanel().set({
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
      check: "osparc.data.model.Study",
      nullable: false
    }
  },

  events: {
    "changeMainViewCaption": "qx.event.type.Data",
    "studySaved": "qx.event.type.Data"
  },

  members: {
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

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree(study.getName(), study.getWorkbench());
      nodesTree.addListener("addNode", () => {
        this.__addNode();
      }, this);
      nodesTree.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Service tree"), nodesTree), 0);

      const extraView = this.__extraView = new osparc.component.metadata.StudyInfo(study);
      extraView.setMaxHeight(300);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Study information"), extraView), 1);

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView(study.getWorkbench());
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Logger"), loggerView), 2);

      const workbenchUI = this.__workbenchUI = new osparc.component.workbench.WorkbenchUI(study.getWorkbench());
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

      const nodeView = this.__nodeView = new osparc.component.widget.NodeView().set({
        minHeight: 200
      });
      nodeView.setWorkbench(study.getWorkbench());
    },

    connectEvents: function() {
      this.__mainPanel.getControls().addListener("startPipeline", this.__startPipeline, this);
      this.__mainPanel.getControls().addListener("stopPipeline", this.__stopPipeline, this);

      const workbench = this.getStudy().getWorkbench();
      workbench.addListener("workbenchChanged", this.__workbenchChanged, this);

      workbench.addListener("retrieveInputs", e => {
        const data = e.getData();
        const node = data["node"];
        const portKey = data["portKey"];
        this.__updatePipelineAndRetrieve(node, portKey);
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
      const nodesTree = this.__nodesTree;
      nodesTree.addListener("changeSelectedNode", e => {
        const node = workbenchUI.getNodeUI(e.getData());
        if (node && node.classname.includes("NodeUI")) {
          node.setActive(true);
        }
      });
      workbenchUI.addListener("changeSelectedNode", e => {
        nodesTree.nodeSelected(e.getData());
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
          appearance: "service-window",
          layout: new qx.ui.layout.Grow(),
          autoDestroy: true,
          contentPadding: 0,
          width: 570,
          height: 450,
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
              widget = new osparc.component.widget.DashGrid(node);
            }
          }
          if (widget === null) {
            widget = this.__workbenchUI;
          }
        } else if (node.isInKey("file-picker")) {
          widget = new osparc.file.FilePicker(node, this.getStudy().getUuid());
        } else {
          this.__nodeView.setNode(node);
          this.__nodeView.buildLayout();
          widget = this.__nodeView;
        }
      }
      return widget;
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

    __updatePipelineAndRetrieve: function(node, portKey = null) {
      this.updateStudyDocument(
        false,
        this.__retrieveInputs.bind(this, node, portKey)
      );
      this.getLogger().debug("root", "Updating pipeline");
    },

    __retrieveInputs: function(node, portKey = null) {
      this.getLogger().debug("root", "Retrieveing inputs");
      if (node) {
        node.retrieveInputs(portKey);
      }
    },

    __startPipeline: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.start", true)) {
        return false;
      }

      return this.updateStudyDocument(true, this.__doStartPipeline);
    },

    __doStartPipeline: function() {
      this.getStudy().getWorkbench().clearProgressData();

      const socket = osparc.wrapper.WebSocket.getInstance();

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
      const req = new osparc.io.request.ApiRequest(url, "POST");
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", e => {
        this.getLogger().error("root", "Error submitting pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error("root", "Failed submitting pipeline");
      }, this);
      req.send();

      this.getLogger().info("root", "Starting pipeline");
      return true;
    },

    __stopPipeline: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.stop", true)) {
        return false;
      }

      let req = new osparc.io.request.ApiRequest("/stop_pipeline", "POST");
      let data = {};
      data["project_id"] = this.getStudy().getUuid();
      req.set({
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelineStopped, this);
      req.addListener("error", e => {
        this.getLogger().error("root", "Error stopping pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error("root", "Failed stopping pipeline");
      }, this);
      // req.send();

      this.getLogger().info("root", "Stopping pipeline. Not yet implemented");
      return true;
    },

    __onPipelinesubmitted: function(e) {
      const resp = e.getTarget().getResponse();
      const pipelineId = resp.data["project_id"];
      this.getLogger().debug("root", "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.__pipelineId = null;
        this.getLogger().error("root", "Submition failed");
      } else {
        this.__pipelineId = pipelineId;
        this.getLogger().info("root", "Pipeline started");
      }
    },

    __onPipelineStopped: function(e) {
      this.getStudy().getWorkbench().clearProgressData();
    },

    __startAutoSaveTimer: function() {
      let diffPatcher = osparc.wrapper.JsonDiffPatch.getInstance();
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
            this.updateStudyDocument(false);
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

    updateStudyDocument: function(run=false, cbSuccess, cbError) {
      this.getStudy().setLastChangeDate(new Date());
      const newObj = this.getStudy().serializeStudy();
      const prjUuid = this.getStudy().getUuid();

      const params = {
        url: {
          "project_id": prjUuid,
          run
        },
        data: newObj
      };
      osparc.data.Resources.fetch("studies", "put", params).then(data => {
        this.fireDataEvent("studySaved", true);
        this.__lastSavedPrj = osparc.wrapper.JsonDiffPatch.getInstance().clone(newObj);
        if (cbSuccess) {
          cbSuccess.call(this);
        }
      }).catch(error => {
        this.getLogger().error("root", "Error updating pipeline");
      });
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

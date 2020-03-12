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

  construct: function(study) {
    this.base(arguments, "horizontal");

    let mainPanel = this.__mainPanel = new osparc.desktop.MainPanel();
    let sidePanel = this.__sidePanel = new osparc.desktop.SidePanel().set({
      minWidth: 0,
      maxWidth: 700,
      width: 400
    });

    const scroll = this.__scrollContainer = new qx.ui.container.Scroll().set({
      minWidth: 0
    });
    scroll.add(sidePanel);

    this.add(mainPanel, 1); // flex 1
    this.add(scroll, 0); // flex 0

    if (study) {
      this.setStudy(study);
    }

    this.__attachEventHandlers();
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy"
    }
  },

  events: {
    "changeMainViewCaption": "qx.event.type.Data",
    "studySaved": "qx.event.type.Data"
  },

  members: {
    __mainPanel: null,
    __sidePanel: null,
    __scrollContainer: null,
    __workbenchUI: null,
    __nodeView: null,
    __groupNodeView: null,
    __nodesTree: null,
    __extraView: null,
    __loggerView: null,
    __currentNodeId: null,
    __autoSaveTimer: null,

    _applyStudy: function(study) {
      osparc.store.Store.getInstance().setCurrentStudy(study);
      study.buildWorkbench();
      study.openStudy();
      this.__initViews();
      this.__connectEvents();
      this.__startAutoSaveTimer();

      this.__openOneNode();
    },

    __openOneNode: function() {
      const validNodeIds = [];
      const allNodes = this.getStudy().getWorkbench().getNodes(true);
      Object.values(allNodes).forEach(node => {
        if (!node.isFilePicker()) {
          validNodeIds.push(node.getNodeId());
        }
      });

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
      if (validNodeIds.length === 1 && preferencesSettings.getAutoOpenNode()) {
        this.nodeSelected(validNodeIds[0]);
      } else {
        this.nodeSelected(this.getStudy().getUuid());
      }
    },

    /**
     * Destructor
     */
    destruct: function() {
      osparc.store.Store.getInstance().setCurrentStudy(null);
      this.__stopAutoSaveTimer();
    },

    __initViews: function() {
      const study = this.getStudy();

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree(study);
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
      workbenchUI.addListener("removeEdge", e => {
        const edgeId = e.getData();
        this.__removeEdge(edgeId);
      }, this);

      this.__nodeView = new osparc.component.node.NodeView().set({
        minHeight: 200
      });

      this.__groupNodeView = new osparc.component.node.GroupNodeView().set({
        minHeight: 200
      });
    },

    __connectEvents: function() {
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

      const workbenchUI = this.__workbenchUI;
      const nodesTree = this.__nodesTree;
      [
        nodesTree,
        workbenchUI
      ].forEach(widget => {
        widget.addListener("nodeDoubleClicked", e => {
          const nodeId = e.getData();
          this.nodeSelected(nodeId);
        }, this);
      });

      nodesTree.addListener("changeSelectedNode", e => {
        const node = workbenchUI.getNodeUI(e.getData());
        if (node && node.classname.includes("NodeUI")) {
          node.setActive(true);
        }
      });
      nodesTree.addListener("exportNode", e => {
        if (!osparc.data.Permissions.getInstance().canDo("study.node.export", true)) {
          return;
        }
        const nodeId = e.getData();
        const node = this.getStudy().getWorkbench().getNode(nodeId);
        if (node && node.isContainer()) {
          // const exportGroupView = new osparc.component.export.ExportGroup(node);

          const window = new qx.ui.window.Window(this.tr("Export: ") + node.getLabel()).set({
            appearance: "service-window",
            layout: new qx.ui.layout.Grow(),
            autoDestroy: true,
            contentPadding: 0,
            width: 900,
            height: 800,
            showMinimize: false,
            modal: true
          });
          // window.add(exportGroupView);
          window.center();
          window.open();
        }
      });

      workbenchUI.addListener("changeSelectedNode", e => {
        const nodeId = e.getData();
        nodesTree.nodeSelected(nodeId);
      });
    },

    nodeSelected: function(nodeId) {
      if (!nodeId) {
        this.__loggerView.setCurrentNodeId();
        return;
      }
      if (this.__nodeView) {
        this.__nodeView.restoreIFrame();
      }
      if (this.__groupNodeView) {
        this.__groupNodeView.restoreIFrame();
      }
      this.__currentNodeId = nodeId;

      const study = this.getStudy();
      const workbench = study.getWorkbench();
      if (nodeId === study.getUuid()) {
        this.showInMainView(this.__workbenchUI, nodeId);
        this.__workbenchUI.loadModel(workbench);
      } else {
        const node = workbench.getNode(nodeId);
        if (node.isFilePicker()) {
          this.__openFilePicker(node);
        } else if (node.isContainer()) {
          this.__groupNodeView.setNode(node);
          this.showInMainView(this.__workbenchUI, nodeId);
          this.__workbenchUI.loadModel(node);
          this.__groupNodeView.populateLayout();
        } else {
          this.__nodeView.setNode(node);
          this.showInMainView(this.__nodeView, nodeId);
          this.__nodeView.populateLayout();
        }
      }
    },

    __openFilePicker: function(node) {
      const filePicker = new osparc.file.FilePicker(node, this.getStudy().getUuid());
      // open file picker in window
      const filePickerWin = new qx.ui.window.Window(node.getLabel()).set({
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
        this.nodeSelected(node.getParentNodeId() || this.getStudy().getUuid());
      };
      filePickerWin.add(filePicker);
      qx.core.Init.getApplication().getRoot().add(filePickerWin);
      filePickerWin.show();
      filePickerWin.center();

      filePicker.addListener("finished", () => filePickerWin.close(), this);
      filePickerWin.addListener("close", () => showParentWorkbench());
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
      const currentNode = workbench.getNode(this.__currentNodeId);
      const edge = workbench.getEdge(edgeId);
      let removed = false;
      if (currentNode && currentNode.isContainer() && edge.getOutputNodeId() === currentNode.getNodeId()) {
        let inputNode = workbench.getNode(edge.getInputNodeId());
        currentNode.removeOutputNode(inputNode.getNodeId());

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
    },

    __workbenchChanged: function() {
      this.__nodesTree.populateTree();
      this.__nodesTree.nodeSelected(this.__currentNodeId);
    },

    showInMainView: function(widget, nodeId) {
      this.__mainPanel.setMainView(widget);

      this.__nodesTree.nodeSelected(nodeId);
      this.__loggerView.setCurrentNodeId(nodeId);

      const controlsBar = this.__mainPanel.getControls();
      controlsBar.setWorkbenchVisibility(widget === this.__workbenchUI);
      controlsBar.setExtraViewVisibility(this.__groupNodeView && this.__groupNodeView.getNode() && nodeId === this.__groupNodeView.getNode().getNodeId());

      const nodesPath = this.getStudy().getWorkbench().getPathIds(nodeId);
      this.fireDataEvent("changeMainViewCaption", nodesPath);
    },

    getLogger: function() {
      return this.__loggerView;
    },

    __getCurrentPipeline: function() {
      const saveContainers = false;
      const savePosition = false;
      const currentPipeline = this.getStudy().getWorkbench().serializeWorkbench(saveContainers, savePosition);
      return currentPipeline;
    },

    __updatePipelineAndRetrieve: function(node, portKey = null) {
      this.updateStudyDocument(
        false,
        this.__retrieveInputs.bind(this, node, portKey)
      );
      this.getLogger().debug(null, "Updating pipeline");
    },

    __retrieveInputs: function(node, portKey = null) {
      this.getLogger().debug(null, "Retrieveing inputs");
      if (node) {
        node.retrieveInputs(portKey);
      }
    },

    __showWorkbenchUI: function() {
      const workbench = this.getStudy().getWorkbench();
      const currentNode = workbench.getNode(this.__currentNodeId);
      if (currentNode === this.__workbenchUI.getCurrentModel()) {
        this.showInMainView(this.__workbenchUI, this.__currentNodeId);
      } else {
        osparc.component.message.FlashMessenger.getInstance().logAs("No Workbench view for this node", "ERROR");
      }
    },

    __showSettings: function() {
      const workbench = this.getStudy().getWorkbench();
      const currentNode = workbench.getNode(this.__currentNodeId);
      if (this.__groupNodeView.isPropertyInitialized("node") && currentNode === this.__groupNodeView.getNode()) {
        this.showInMainView(this.__groupNodeView, this.__currentNodeId);
      } else if (this.__nodeView.isPropertyInitialized("node") && currentNode === this.__nodeView.getNode()) {
        this.showInMainView(this.__nodeView, this.__currentNodeId);
      } else {
        osparc.component.message.FlashMessenger.getInstance().logAs("No Settings view for this node", "ERROR");
      }
    },

    __isSelectionEmpty: function(selectedNodeUIs) {
      if (selectedNodeUIs === null || selectedNodeUIs.length === 0) {
        return true;
      }
      return false;
    },

    __groupSelection: function() {
      // Some checks
      if (!osparc.data.Permissions.getInstance().canDo("study.node.create", true)) {
        return;
      }

      const selectedNodeUIs = this.__workbenchUI.getSelectedNodes();
      if (this.__isSelectionEmpty(selectedNodeUIs)) {
        return;
      }

      const selectedNodes = [];
      selectedNodeUIs.forEach(selectedNodeUI => {
        selectedNodes.push(selectedNodeUI.getNode());
      });

      const workbench = this.getStudy().getWorkbench();
      const currentModel = this.__workbenchUI.getCurrentModel();
      workbench.groupNodes(currentModel, selectedNodes);

      this.nodeSelected(currentModel.getNodeId ? currentModel.getNodeId() : this.getStudy().getUuid());
      this.__workbenchChanged();

      this.__workbenchUI.resetSelectedNodes();
    },

    __ungroupSelection: function() {
      // Some checks
      if (!osparc.data.Permissions.getInstance().canDo("study.node.create", true)) {
        return;
      }
      const selectedNodeUIs = this.__workbenchUI.getSelectedNodes();
      if (this.__isSelectionEmpty(selectedNodeUIs)) {
        return;
      }
      if (selectedNodeUIs.length > 1) {
        osparc.component.message.FlashMessenger.getInstance().logAs("Select only one group", "ERROR");
        return;
      }
      const nodesGroup = selectedNodeUIs[0].getNode();
      if (!nodesGroup.isContainer()) {
        osparc.component.message.FlashMessenger.getInstance().logAs("Select a group", "ERROR");
        return;
      }

      // Collect info
      const workbench = this.getStudy().getWorkbench();
      const currentModel = this.__workbenchUI.getCurrentModel();
      workbench.ungroupNode(currentModel, nodesGroup);

      this.nodeSelected(currentModel.getNodeId ? currentModel.getNodeId() : this.getStudy().getUuid());
      this.__workbenchChanged();

      this.__workbenchUI.resetSelectedNodes();
    },

    __startPipeline: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.start", true)) {
        return false;
      }

      return this.updateStudyDocument(true, this.__doStartPipeline);
    },

    __doStartPipeline: function() {
      this.getStudy().getWorkbench().clearProgressData();
      // post pipeline
      const url = "/computation/pipeline/" + encodeURIComponent(this.getStudy().getUuid()) + "/start";
      const req = new osparc.io.request.ApiRequest(url, "POST");
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
      if (!osparc.data.Permissions.getInstance().canDo("study.stop", true)) {
        return false;
      }

      let req = new osparc.io.request.ApiRequest("/stop_pipeline", "POST");
      let data = {};
      data["projectId"] = this.getStudy().getUuid();
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
        this.getLogger().error(null, "Submission failed");
      } else {
        this.getLogger().info(null, "Pipeline started");
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
          projectId: prjUuid,
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
        this.getLogger().error(null, "Error updating pipeline");
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

      const controlsBar = this.__mainPanel.getControls();
      controlsBar.addListener("showWorkbench", this.__showWorkbenchUI, this);
      controlsBar.addListener("showSettings", this.__showSettings, this);
      controlsBar.addListener("groupSelection", this.__groupSelection, this);
      controlsBar.addListener("ungroupSelection", this.__ungroupSelection, this);
      controlsBar.addListener("startPipeline", this.__startPipeline, this);
      controlsBar.addListener("stopPipeline", this.__stopPipeline, this);

      // Listen to socket
      const socket = osparc.wrapper.WebSocket.getInstance();
      // callback for incoming logs
      const slotName = "logger";
      socket.removeSlot(slotName);
      socket.on(slotName, function(jsonString) {
        const data = JSON.parse(jsonString);
        if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy().getUuid() !== data["project_id"]) {
          // Filtering out logs from other studies
          return;
        }
        this.getLogger().infos(data["Node"], data["Messages"]);
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

      // callback for node updates
      const slotName3 = "nodeUpdated";
      socket.removeSlot(slotName3);
      socket.on(slotName3, function(data) {
        const d = JSON.parse(data);
        const nodeId = d["Node"];
        const nodeData = d["Data"];
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          node.setOutputData(nodeData);
          if (nodeData.progress) {
            const progress = Number.parseInt(nodeData.progress);
            node.setProgress(progress);
          }
        }
      }, this);
    }
  }
});

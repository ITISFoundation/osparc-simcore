/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.desktop.WorkbenchView", {
  extend: qx.ui.splitpane.Pane,

  construct: function() {
    this.base(arguments, "horizontal");

    const sidePanel = this.__sidePanel = new osparc.desktop.SidePanel().set({
      minWidth: 0,
      width: Math.min(parseInt(window.innerWidth * 0.25), 350)
    });
    osparc.utils.Utils.addBorder(sidePanel, 2, "right");
    const scroll = this.__scrollContainer = new qx.ui.container.Scroll().set({
      minWidth: 0
    });
    scroll.add(sidePanel);

    this.add(scroll, 0); // flex 0

    const mainPanel = this.__mainPanel = new osparc.desktop.MainPanel();
    this.add(mainPanel, 1); // flex 1

    this.__attachEventHandlers();
  },

  events: {
    "startStudy": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    }
  },

  members: {
    __sidePanel: null,
    __scrollContainer: null,
    __mainPanel: null,
    __workbenchUI: null,
    __nodeView: null,
    __groupNodeView: null,
    __nodesTree: null,
    __extraView: null,
    __loggerView: null,
    __currentNodeId: null,

    _applyStudy: function(study) {
      if (study) {
        this.__initViews();
        this.__connectEvents();
        this.__attachSocketEventHandlers();
      }
    },

    nodeSelected: function(nodeId) {
      if (!nodeId) {
        this.__loggerView.setCurrentNodeId("");
        return;
      }
      if (this.__nodesTree) {
        this.__nodesTree.setCurrentNodeId(nodeId);
      }
      if (this.__nodeView) {
        this.__nodeView.restoreIFrame();
      }
      if (this.__groupNodeView) {
        this.__groupNodeView.restoreIFrame();
      }
      this.__currentNodeId = nodeId;
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      const study = this.getStudy();
      const workbench = study.getWorkbench();
      if (nodeId === study.getUuid()) {
        this.__showInMainView(this.__workbenchUI, nodeId);
        this.__workbenchUI.loadModel(workbench);
      } else {
        const node = workbench.getNode(nodeId);
        if (node.isContainer()) {
          this.__groupNodeView.setNode(node);
          this.__showInMainView(this.__workbenchUI, nodeId);
          this.__workbenchUI.loadModel(node);
          this.__groupNodeView.populateLayout();
        } else if (node.isFilePicker()) {
          const nodeView = new osparc.component.node.FilePickerNodeView();
          nodeView.setNode(node);
          this.__showInMainView(nodeView, nodeId);
          nodeView.populateLayout();
        } else {
          this.__nodeView.setNode(node);
          this.__showInMainView(this.__nodeView, nodeId);
          this.__nodeView.populateLayout();
        }
      }
    },

    getLogger: function() {
      return this.__loggerView;
    },

    __editSlides: function() {
      const uiData = this.getStudy().getUi();
      const nodesSlidesTree = new osparc.component.widget.NodesSlidesTree(uiData.getSlideshow());
      const title = this.tr("Edit Slides");
      const win = osparc.ui.window.Window.popUpInWindow(nodesSlidesTree, title, 600, 500).set({
        modal: false,
        clickAwayClose: false
      });
      nodesSlidesTree.addListener("finished", () => {
        win.close();
      });
    },

    __showSweeper: function() {
      const study = this.getStudy();
      const sweeper = new osparc.component.sweeper.Sweeper(study);
      const title = this.tr("Sweeper");
      const win = osparc.ui.window.Window.popUpInWindow(sweeper, title, 400, 700);
      sweeper.addListener("iterationSelected", e => {
        win.close();
        const iterationStudyId = e.getData();
        const params = {
          url: {
            "projectId": iterationStudyId
          }
        };
        osparc.data.Resources.getOne("studies", params)
          .then(studyData => {
            study.removeIFrames();
            const data = {
              studyId: studyData.uuid
            };
            this.fireDataEvent("startStudy", data);
          });
      });
    },

    __showWorkbenchUI: function() {
      const workbench = this.getStudy().getWorkbench();
      const currentNode = workbench.getNode(this.__currentNodeId);
      if (currentNode === this.__workbenchUI.getCurrentModel()) {
        this.__showInMainView(this.__workbenchUI, this.__currentNodeId);
      } else {
        osparc.component.message.FlashMessenger.getInstance().logAs("No Workbench view for this node", "ERROR");
      }
    },

    __showSettings: function() {
      const workbench = this.getStudy().getWorkbench();
      const currentNode = workbench.getNode(this.__currentNodeId);
      if (this.__groupNodeView.isPropertyInitialized("node") && currentNode === this.__groupNodeView.getNode()) {
        this.__showInMainView(this.__groupNodeView, this.__currentNodeId);
      } else if (this.__nodeView.isPropertyInitialized("node") && currentNode === this.__nodeView.getNode()) {
        this.__showInMainView(this.__nodeView, this.__currentNodeId);
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
        return;
      }
      const runButton = this.__mainPanel.getControls().getStartButton();
      runButton.setFetching(true);
      this.updateStudyDocument(true)
        .then(() => {
          this.__doStartPipeline();
        })
        .catch(() => {
          this.getLogger().error(null, "Couldn't run the pipeline: Pipeline failed to save.");
          runButton.setFetching(false);
        });
    },

    __doStartPipeline: function() {
      if (this.getStudy().getSweeper().hasSecondaryStudies()) {
        const secondaryStudyIds = this.getStudy().getSweeper().getSecondaryStudyIds();
        secondaryStudyIds.forEach(secondaryStudyId => {
          this.__requestStartPipeline(secondaryStudyId);
        });
      } else {
        this.getStudy().getWorkbench().clearProgressData();
        this.__requestStartPipeline(this.getStudy().getUuid());
      }
    },

    __requestStartPipeline: function(studyId) {
      const url = "/computation/pipeline/" + encodeURIComponent(studyId) + ":start";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      const runButton = this.__mainPanel.getControls().getStartButton();
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", e => {
        this.getLogger().error(null, "Error submitting pipeline");
        runButton.setFetching(false);
      }, this);
      req.addListener("fail", e => {
        if (e.getTarget().getResponse().error.status == "403") {
          this.getLogger().error(null, "Pipeline is already running");
        } else {
          this.getLogger().error(null, "Failed submitting pipeline");
        }
        runButton.setFetching(false);
      }, this);
      req.send();

      this.getLogger().info(null, "Starting pipeline");
      return true;
    },

    __onPipelinesubmitted: function(e) {
      const resp = e.getTarget().getResponse();
      const pipelineId = resp.data["pipeline_id"];
      this.getLogger().debug(null, "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.getLogger().error(null, "Submission failed");
      } else {
        this.getLogger().info(null, "Pipeline started");
        /* If no projectStateUpdated comes in 60 seconds, client must
        check state of pipeline and update button accordingly. */
        const timer = setTimeout(() => {
          osparc.store.Store.getInstance().getStudyState(pipelineId);
        }, 60000);
        const socket = osparc.wrapper.WebSocket.getInstance();
        socket.getSocket().once("projectStateUpdated", jsonStr => {
          const study = JSON.parse(jsonStr);
          if (study["project_uuid"] === pipelineId) {
            clearTimeout(timer);
          }
        });
      }
    },

    __stopPipeline: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.stop", true)) {
        return;
      }

      this.__doStopPipeline();
    },

    __doStopPipeline: function() {
      if (this.getStudy().getSweeper().hasSecondaryStudies()) {
        const secondaryStudyIds = this.getStudy().getSweeper().getSecondaryStudyIds();
        secondaryStudyIds.forEach(secondaryStudyId => {
          this.__requestStopPipeline(secondaryStudyId);
        });
      } else {
        this.__requestStopPipeline(this.getStudy().getUuid());
      }
    },

    __requestStopPipeline: function(studyId) {
      const url = "/computation/pipeline/" + encodeURIComponent(studyId) + ":stop";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      req.addListener("success", e => {
        this.getLogger().debug(null, "Pipeline aborting");
      }, this);
      req.addListener("error", e => {
        this.getLogger().error(null, "Error stopping pipeline");
      }, this);
      req.addListener("fail", e => {
        this.getLogger().error(null, "Failed stopping pipeline");
      }, this);
      req.send();

      this.getLogger().info(null, "Stopping pipeline");
      return true;
    },

    __maximizeIframe: function(maximize) {
      this.getBlocker().setStyles({
        display: maximize ? "none" : "block"
      });
      this.__scrollContainer.setVisibility(maximize ? "excluded" : "visible");
    },

    __attachEventHandlers: function() {
      const blocker = this.getBlocker();
      blocker.addListener("tap", this.__sidePanel.toggleCollapsed.bind(this.__sidePanel));

      const splitter = this.getChildControl("splitter");
      splitter.setWidth(1);

      const maximizeIframeCb = msg => {
        this.__maximizeIframe(msg.getData());
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      const controlsBar = this.__mainPanel.getControls();
      controlsBar.addListener("showSweeper", this.__showSweeper, this);
      controlsBar.addListener("showWorkbench", this.__showWorkbenchUI, this);
      controlsBar.addListener("showSettings", this.__showSettings, this);
      controlsBar.addListener("groupSelection", this.__groupSelection, this);
      controlsBar.addListener("ungroupSelection", this.__ungroupSelection, this);
      controlsBar.addListener("startPipeline", this.__startPipeline, this);
      controlsBar.addListener("stopPipeline", this.__stopPipeline, this);
    },

    __initViews: function() {
      const study = this.getStudy();

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree();
      nodesTree.setStudy(study);
      nodesTree.addListener("slidesEdit", () => {
        this.__editSlides();
      }, this);
      nodesTree.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Service tree"), nodesTree), 0, {
        flex: 1
      });

      const extraView = this.__extraView = new osparc.component.metadata.StudyInfo();
      extraView.setStudy(study);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Study information"), extraView), 1, {
        flex: 1
      });

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView(study.getWorkbench());
      const loggerPanel = new osparc.desktop.PanelView(this.tr("Logger"), loggerView);
      osparc.utils.Utils.setIdToWidget(loggerPanel.getTitleLabel(), "loggerTitleLabel");
      this.__sidePanel.addOrReplaceAt(loggerPanel, 2, {
        flex: 1
      });
      if (!osparc.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
        loggerPanel.setCollapsed(true);
      }

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


    __removeNode: function(nodeId) {
      if (nodeId === this.__currentNodeId) {
        return false;
      }

      const workbench = this.getStudy().getWorkbench();
      const connectedEdges = workbench.getConnectedEdges(nodeId);
      if (workbench.removeNode(nodeId)) {
        // remove first the connected edges
        for (let i = 0; i < connectedEdges.length; i++) {
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

    __updatePipelineAndRetrieve: function(node, portKey = null) {
      this.updateStudyDocument(false)
        .then(() => {
          this.__retrieveInputs(node, portKey);
        });
      this.getLogger().debug(null, "Updating pipeline");
    },

    __retrieveInputs: function(node, portKey = null) {
      this.getLogger().debug(null, "Retrieveing inputs");
      if (node) {
        node.retrieveInputs(portKey);
      }
    },

    __showInMainView: function(widget, nodeId) {
      this.__mainPanel.setMainView(widget);

      this.__nodesTree.nodeSelected(nodeId);
      this.__loggerView.setCurrentNodeId(nodeId);

      const controlsBar = this.__mainPanel.getControls();
      controlsBar.setWorkbenchVisibility(widget === this.__workbenchUI);
      controlsBar.setExtraViewVisibility(this.__groupNodeView && this.__groupNodeView.getNode() && nodeId === this.__groupNodeView.getNode().getNodeId());
    },

    __workbenchChanged: function() {
      this.__nodesTree.populateTree();
      this.__nodesTree.nodeSelected(this.__currentNodeId);
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
        widget.addListener("nodeSelected", e => {
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
        const nodeId = e.getData();
        this.__exportMacro(nodeId);
      });

      workbenchUI.addListener("changeSelectedNode", e => {
        const nodeId = e.getData();
        nodesTree.nodeSelected(nodeId);
      });
    },

    __exportMacro: function(nodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.export", true)) {
        return;
      }
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node && node.isContainer()) {
        const exportDAGView = new osparc.component.export.ExportDAG(node);
        const window = new qx.ui.window.Window(this.tr("Export: ") + node.getLabel()).set({
          appearance: "service-window",
          layout: new qx.ui.layout.Grow(),
          autoDestroy: true,
          contentPadding: 0,
          width: 700,
          height: 700,
          showMinimize: false,
          modal: true
        });
        window.add(exportDAGView);
        window.center();
        window.open();

        window.addListener("close", () => {
          exportDAGView.tearDown();
        }, this);

        exportDAGView.addListener("finished", () => {
          window.close();
        }, this);
      }
    },

    __attachSocketEventHandlers: function() {
      // Listen to socket
      const socket = osparc.wrapper.WebSocket.getInstance();

      // callback for incoming logs
      const slotName = "logger";
      if (!socket.slotExists(slotName)) {
        socket.on(slotName, function(jsonString) {
          const data = JSON.parse(jsonString);
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy().getUuid() !== data["project_id"]) {
            // Filtering out logs from other studies
            return;
          }
          this.getLogger().infos(data["Node"], data["Messages"]);
        }, this);
      }
      socket.emit(slotName);

      // callback for incoming progress
      const slotName2 = "progress";
      if (!socket.slotExists(slotName2)) {
        socket.on(slotName2, function(data) {
          const d = JSON.parse(data);
          const nodeId = d["Node"];
          const progress = 100 * Number.parseFloat(d["Progress"]).toFixed(4);
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node) {
            node.getStatus().setProgress(progress);
          }
        }, this);
      }

      // callback for node updates
      const slotName3 = "nodeUpdated";
      if (!socket.slotExists(slotName3)) {
        socket.on(slotName3, data => {
          const d = JSON.parse(data);
          const nodeId = d["Node"];
          const nodeData = d["Data"];
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node && nodeData) {
            node.setOutputData(nodeData.outputs);
            if (nodeData.progress) {
              const progress = Number.parseInt(nodeData.progress);
              node.getStatus().setProgress(progress);
            }
          }
        }, this);
      }
    },

    __checkMaximizeable: function() {
      this.__scrollContainer.setVisibility("visible");
      this.__nodeView._maximizeIFrame(false); // eslint-disable-line no-underscore-dangle
      const node = this.getStudy().getWorkbench().getNode(this.__currentNodeId);
      if (node && node.getIFrame() && (node.getInputNodes().length === 0)) {
        node.getLoadingPage().maximizeIFrame(true);
        node.getIFrame().maximizeIFrame(true);
      }
    },

    openFirstNode: function() {
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
        // Todo Odei: A bit of a hack
        qx.event.Timer.once(() => {
          this.__checkMaximizeable();
        }, this, 10);
      } else {
        this.nodeSelected(this.getStudy().getUuid());
      }
    },

    updateStudyDocument: function(run = false) {
      this.getStudy().setLastChangeDate(new Date());
      const newObj = this.getStudy().serialize();
      const prjUuid = this.getStudy().getUuid();

      const params = {
        url: {
          projectId: prjUuid,
          run
        },
        data: newObj
      };
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "put", params)
          .then(data => {
            resolve();
          })
          .catch(error => {
            reject();
          });
      });
    }
  }
});

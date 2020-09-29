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
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const pane = this.__pane = new qx.ui.splitpane.Pane("horizontal");
    this._add(pane, {
      flex: 1
    });

    const sidePanel = this.__sidePanel = new osparc.desktop.SidePanel().set({
      minWidth: 0,
      width: Math.min(parseInt(window.innerWidth*0.25), 350)
    });
    osparc.utils.Utils.addBorder(sidePanel, 2, "right");
    const scroll = this.__scrollContainer = new qx.ui.container.Scroll().set({
      minWidth: 0
    });
    scroll.add(sidePanel);

    pane.add(scroll, 0); // flex 0

    const mainPanel = this.__mainPanel = new osparc.desktop.MainPanel();
    pane.add(mainPanel, 1); // flex 1

    this.__attachEventHandlers();
  },

  events: {
    "changeMainViewCaption": "qx.event.type.Data",
    "studyIsLocked": "qx.event.type.Event",
    "studySaved": "qx.event.type.Data",
    "startStudy": "qx.event.type.Data"
  },

  members: {
    __study: null,
    __settingStudy: null,
    __pane: null,
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
    __lastSavedStudy: null,

    setStudy: function(studyData) {
      return new Promise((resolve, reject) => {
        if (this.__settingStudy) {
          resolve();
          return;
        }
        this.__settingStudy = true;

        this._showLoadingPage(this.tr("Starting ") + (studyData.name || this.tr("Study")));

        // Before starting a study, make sure the latest version is fetched
        const params = {
          url: {
            "projectId": studyData.uuid
          }
        };
        const promises = [
          osparc.data.Resources.getOne("studies", params),
          osparc.store.Store.getInstance().getServicesDAGs()
        ];
        Promise.all(promises)
          .then(values => {
            studyData = values[0];
            const study = new osparc.data.model.Study(studyData);
            this.__study = study;
            this.__settingStudy = false;

            this._hideLoadingPage();

            resolve();

            osparc.store.Store.getInstance().setCurrentStudy(study);
            study.buildWorkbench();
            study.openStudy()
              .then(() => {
                study.getWorkbench().initWorkbench();
              })
              .catch(err => {
                if ("status" in err && err["status"] == 423) { // Locked
                  const msg = study.getName() + this.tr(" is already opened");
                  osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
                  this.fireEvent("studyIsLocked");
                } else {
                  console.error(err);
                }
              });
            this.__initViews();
            this.__connectEvents();
            this.__attachSocketEventHandlers();
            this.__startAutoSaveTimer();
            this.__openOneNode();
          });
      });
    },

    getStudy: function() {
      return this.__study;
    },

    // overridden
    _showMainLayout: function(show) {
      this.__pane.setVisibility(show ? "visible" : "excluded");
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
        // Todo Odei: A bit of a hack
        qx.event.Timer.once(() => {
          this.__checkMaximizeable();
        }, this, 10);
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
      nodesTree.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Service tree"), nodesTree), 0, {
        flex: 1
      });

      const extraView = this.__extraView = new osparc.component.metadata.StudyInfo(study);
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

    nodeSelected: function(nodeId) {
      if (!nodeId) {
        this.__loggerView.setCurrentNodeId();
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
      const filePickerWin = new osparc.ui.window.Window(node.getLabel()).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 0,
        width: 570,
        height: 450,
        showMinimize: false,
        modal: true,
        clickAwayClose: true
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

    getCurrentPathIds: function() {
      const nodesPath = this.getStudy().getWorkbench().getPathIds(this.__currentNodeId);
      return nodesPath;
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
            this.fireDataEvent("startStudy", studyData.uuid);
          });
      });
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
        return;
      }

      this.updateStudyDocument(true)
        .then(() => {
          this.__doStartPipeline();
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
      const url = "/computation/pipeline/" + encodeURIComponent(studyId) + "/start";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", e => {
        this.getLogger().error(null, "Error submitting pipeline");
      }, this);
      req.addListener("fail", e => {
        if (e.getTarget().getResponse().error.status == "403") {
          this.getLogger().error(null, "Pipeline is already running");  
        }
        else {
          this.getLogger().error(null, "Failed submitting pipeline");
        }
      }, this);
      req.send();

      this.getLogger().info(null, "Starting pipeline");
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
        const delta = diffPatcher.diff(this.__lastSavedStudy, newObj);
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

    updateStudyDocument: function(run=false) {
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
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "put", params)
          .then(data => {
            this.fireDataEvent("studySaved", true);
            this.__lastSavedStudy = osparc.wrapper.JsonDiffPatch.getInstance().clone(newObj);
            resolve();
          }).catch(error => {
            this.getLogger().error(null, "Error updating pipeline");
            reject();
          });
      });
    },

    closeStudy: function() {
      this.getStudy().closeStudy();
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

    __maximizeIframe: function(maximize) {
      this.__pane.getBlocker().setStyles({
        display: maximize ? "none" : "block"
      });
      this.__scrollContainer.setVisibility(maximize ? "excluded" : "visible");
    },

    __attachEventHandlers: function() {
      const blocker = this.__pane.getBlocker();
      blocker.addListener("tap", this.__sidePanel.toggleCollapsed.bind(this.__sidePanel));

      const splitter = this.__pane.getChildControl("splitter");
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
          if (node) {
            node.setOutputData(nodeData.outputs);
            if (nodeData.progress) {
              const progress = Number.parseInt(nodeData.progress);
              node.getStatus().setProgress(progress);
            }
          }
        }, this);
      }
    }
  }
});

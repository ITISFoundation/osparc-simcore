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
    "startSnapshot": "qx.event.type.Data"
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
      this.__mainPanel.getToolbar().setStudy(study);
    },

    getStartStopButtons: function() {
      return this.__mainPanel.getToolbar().getStartStopButtons();
    },

    getSelectedNodes: function() {
      return this.__workbenchUI.getSelectedNodes();
    },

    getSelectedNodeIDs: function() {
      if (this.__mainPanel.getMainView() === this.__workbenchUI) {
        return this.__workbenchUI.getSelectedNodeIDs();
      }
      return [this.__currentNodeId];
    },

    nodeSelected: function(nodeId) {
      if (!nodeId) {
        this.__loggerView.setCurrentNodeId("");
        return;
      }

      const study = this.getStudy();
      const workbench = study.getWorkbench();
      const node = workbench.getNode(nodeId);
      if (node && node.isParameter()) {
        this.__popUpParameterEditor(node);
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
      const prevNodeId = this.__currentNodeId;
      this.__currentNodeId = nodeId;
      study.getUi().setCurrentNodeId(nodeId);

      if (node === null || nodeId === study.getUuid()) {
        this.__showInMainView(this.__workbenchUI, study.getUuid());
        this.__workbenchUI.loadModel(workbench);
      } else if (node.isContainer()) {
        this.__groupNodeView.setNode(node);
        this.__showInMainView(this.__workbenchUI, nodeId);
        this.__workbenchUI.loadModel(node);
        this.__groupNodeView.populateLayout();
      } else if (node.isFilePicker()) {
        const nodeView = new osparc.component.node.FilePickerNodeView();
        nodeView.setNode(node);
        this.__showInMainView(nodeView, nodeId);
        nodeView.populateLayout();
        nodeView.addListener("itemSelected", () => {
          this.nodeSelected(prevNodeId);
        }, this);
      } else {
        this.__nodeView.setNode(node);
        this.__showInMainView(this.__nodeView, nodeId);
        this.__nodeView.populateLayout();
      }
    },

    __popUpParameterEditor: function(node) {
      const parameterEditor = new osparc.component.node.ParameterEditor(node);
      const win = osparc.ui.window.Window.popUpInWindow(parameterEditor, "Edit Parameter", 250, 175);
      parameterEditor.addListener("editParameter", () => {
        const label = parameterEditor.getLabel();
        node.setLabel(label);

        const val = parameterEditor.getValue();
        osparc.component.node.ParameterEditor.setParameterOutputValue(node, val);

        win.close();
      }, this);
      parameterEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    getLogger: function() {
      return this.__loggerView;
    },

    __getNodeLogger: function(nodeId) {
      const nodes = this.getStudy().getWorkbench().getNodes(true);
      for (const node of Object.values(nodes)) {
        if (nodeId === node.getNodeId()) {
          return node.getLogger();
        }
      }
      return null;
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

    __takeSnapshot: function() {
      const editSnapshotView = new osparc.component.snapshots.EditSnapshotView();
      const tagCtrl = editSnapshotView.getChildControl("tags");
      const study = this.getStudy();
      study.getSnapshots()
        .then(snapshots => {
          tagCtrl.setValue("V"+snapshots.length);
        });
      const title = this.tr("Take Snapshot");
      const win = osparc.ui.window.Window.popUpInWindow(editSnapshotView, title, 400, 180);
      editSnapshotView.addListener("takeSnapshot", () => {
        const tag = editSnapshotView.getTag();
        const message = editSnapshotView.getMessage();
        const workbenchToolbar = this.__mainPanel.getToolbar();
        const takeSnapshotBtn = workbenchToolbar.getChildControl("take-snapshot-btn");
        takeSnapshotBtn.setFetching(true);
        const params = {
          url: {
            "studyId": study.getUuid()
          },
          data: {
            "tag": tag,
            "message": message
          }
        };
        osparc.data.Resources.fetch("snapshots", "takeSnapshot", params)
          .then(data => {
            workbenchToolbar.evalSnapshotsBtn();
          })
          .catch(err => osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR"))
          .finally(takeSnapshotBtn.setFetching(false));

        win.close();
      }, this);
      editSnapshotView.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __showSnapshots: function() {
      const study = this.getStudy();
      const snapshots = new osparc.component.snapshots.SnapshotsView(study);
      const title = this.tr("Snapshots");
      const win = osparc.ui.window.Window.popUpInWindow(snapshots, title, 1000, 500);
      snapshots.addListener("openSnapshot", e => {
        win.close();
        const snapshotId = e.getData();
        this.fireDataEvent("startSnapshot", snapshotId);
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

      const selectedNodeUIs = this.getSelectedNodes();
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
      const selectedNodeUIs = this.getSelectedNodes();
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
      controlsBar.addListener("showWorkbench", this.__showWorkbenchUI, this);
      controlsBar.addListener("showSettings", this.__showSettings, this);
      controlsBar.addListener("groupSelection", this.__groupSelection, this);
      controlsBar.addListener("ungroupSelection", this.__ungroupSelection, this);
    },

    __initViews: function() {
      const study = this.getStudy();

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree();
      nodesTree.setStudy(study);
      nodesTree.addListener("removeNode", e => {
        if (this.getStudy().isReadOnly()) {
          return;
        }

        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Nodes"), nodesTree), 0, {
        flex: 1
      });

      const extraView = this.__extraView = new osparc.studycard.Medium(study);
      this.__sidePanel.addListener("panelResized", e => {
        const bounds = e.getData();
        extraView.checkResize(bounds);
      }, this);
      this.__sidePanel.addOrReplaceAt(new osparc.desktop.PanelView(this.tr("Study information"), extraView), 1, {
        flex: 1
      });

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
      const loggerPanel = new osparc.desktop.PanelView(this.tr("Logger"), loggerView);
      osparc.utils.Utils.setIdToWidget(loggerPanel.getTitleLabel(), "studyLoggerTitleLabel");
      this.__sidePanel.addOrReplaceAt(loggerPanel, 2, {
        flex: 1
      });
      if (!osparc.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
        loggerPanel.setCollapsed(true);
      }

      const workbenchUI = this.__workbenchUI = new osparc.component.workbench.WorkbenchUI(study.getWorkbench());
      workbenchUI.setStudy(study);
      workbenchUI.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
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
        return;
      }

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
      if (preferencesSettings.getConfirmDeleteNode()) {
        const msg = this.tr("Are you sure you want to delete node?");
        const win = new osparc.ui.window.Confirmation(msg);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__doRemoveNode(nodeId);
          }
        }, this);
      } else {
        this.__doRemoveNode(nodeId);
      }
    },

    __doRemoveNode: function(nodeId) {
      const workbench = this.getStudy().getWorkbench();
      const connectedEdges = workbench.getConnectedEdges(nodeId);
      if (workbench.removeNode(nodeId)) {
        // remove first the connected edges
        for (let i = 0; i < connectedEdges.length; i++) {
          const edgeId = connectedEdges[i];
          this.__workbenchUI.clearEdge(edgeId);
        }
        this.__workbenchUI.clearNode(nodeId);
      }
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

    __showInMainView: function(widget, nodeId) {
      this.__mainPanel.setMainView(widget);

      if (widget.getNode && widget.getInputsView) {
        setTimeout(() => {
          widget.getInputsView().setCollapsed(widget.getNode().getInputNodes().length === 0);
        }, 150);
      }

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
      workbench.addListener("pipelineChanged", this.__workbenchChanged, this);

      workbench.addListener("showInLogger", ev => {
        const data = ev.getData();
        const nodeId = data.nodeId;
        const msg = data.msg;
        this.getLogger().info(nodeId, msg);
      }, this);

      const workbenchUI = this.__workbenchUI;
      const workbenchToolbar = this.__mainPanel.getToolbar();
      const nodesTree = this.__nodesTree;
      [
        nodesTree,
        workbenchToolbar,
        workbenchUI
      ].forEach(widget => {
        widget.addListener("nodeSelected", e => {
          const nodeId = e.getData();
          this.nodeSelected(nodeId);
        }, this);
      });
      if (!workbenchToolbar.hasListener("takeSnapshot")) {
        workbenchToolbar.addListener("takeSnapshot", this.__takeSnapshot, this);
      }
      if (!workbenchToolbar.hasListener("showSnapshots")) {
        workbenchToolbar.addListener("showSnapshots", this.__showSnapshots, this);
      }

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
        const exportDAGView = new osparc.component.study.ExportDAG(node);
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
          const nodeId = data["Node"];
          const messages = data["Messages"];
          this.getLogger().infos(nodeId, messages);
          const nodeLogger = this.__getNodeLogger(nodeId);
          if (nodeLogger) {
            nodeLogger.infos(nodeId, messages);
          }
        }, this);
      }
      socket.emit(slotName);

      // callback for incoming progress
      const slotName2 = "progress";
      if (!socket.slotExists(slotName2)) {
        socket.on(slotName2, function(data) {
          const d = JSON.parse(data);
          const nodeId = d["Node"];
          const progress = Number.parseFloat(d["Progress"]).toFixed(4);
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node) {
            node.getStatus().setProgress(progress);
          } else if (osparc.data.Permissions.getInstance().isTester()) {
            console.log("Ignored ws 'progress' msg", d);
          }
        }, this);
      }

      // callback for node updates
      const slotName3 = "nodeUpdated";
      if (!socket.slotExists(slotName3)) {
        socket.on(slotName3, data => {
          const d = JSON.parse(data);
          const nodeId = d["Node"];
          const nodeData = d["data"];
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node && nodeData) {
            node.setOutputData(nodeData.outputs);
            if ("progress" in nodeData) {
              const progress = Number.parseInt(nodeData["progress"]);
              node.getStatus().setProgress(progress);
            }
            node.populateStates(nodeData);
          } else if (osparc.data.Permissions.getInstance().isTester()) {
            console.log("Ignored ws 'nodeUpdated' msg", d);
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
    }
  }
});

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

    this.getChildControl("side-panel");
    this.__mainPanel = this.getChildControl("main-panel");

    this.__attachEventHandlers();
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    }
  },

  members: {
    __nodesTree: null,
    __loggerView: null,
    __mainPanel: null,
    __workbenchUI: null,
    __nodeView: null,
    __groupNodeView: null,
    __currentNodeId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "container-scroll-0":
          control = new qx.ui.container.Scroll().set({
            minWidth: 0
          });
          this.add(control, 0); // flex 0
          break;
        case "side-panel": {
          control = new osparc.desktop.SidePanel().set({
            minWidth: 0,
            width: Math.min(parseInt(window.innerWidth * 0.2), 350)
          });
          osparc.utils.Utils.addBorder(control, 2, "right");
          const scroll = this.getChildControl("container-scroll-0");
          scroll.add(control);
          break;
        }
        case "main-panel":
          control = new osparc.desktop.MainPanel();
          this.add(control, 1); // flex 1
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyStudy: function(study) {
      if (study) {
        this.__initViews();
        this.__connectEvents();
        this.__attachSocketEventHandlers();
      }
      this.__mainPanel.getToolbar().setStudy(study);
    },

    __initViews: function() {
      const study = this.getStudy();

      const sidePanel = this.getChildControl("side-panel");
      sidePanel.removeAll();

      const tabView = new qx.ui.tabview.TabView().set({
        contentPadding: 5,
        barPosition: "top"
      });
      tabView.getChildControl("bar").set({
        paddingLeft: 60
      });

      const nodesPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox(5),
        backgroundColor: "material-button-background",
        icon: "@FontAwesome5Solid/list/24",
        toolTipText: this.tr("Nodes")
      });
      tabView.add(nodesPage);
      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree();
      nodesTree.setStudy(study);
      nodesPage.add(nodesTree, {
        flex: 1
      });

      const storagePage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox(5),
        backgroundColor: "material-button-background",
        icon: "@FontAwesome5Solid/database/24",
        toolTipText: this.tr("Storage")
      });
      tabView.add(storagePage);
      const filesTree = this.__filesTree = new osparc.file.FilesTree().set({
        hideRoot: true
      });
      filesTree.populateTree();
      storagePage.add(filesTree, {
        flex: 1
      });

      const parametersPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox(5),
        backgroundColor: "material-button-background",
        icon: "@FontAwesome5Solid/sliders-h/24",
        toolTipText: this.tr("Parameters")
      });
      tabView.add(parametersPage);

      sidePanel.add(tabView, {
        flex: 1
      });

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
      const loggerInPanelView = this.__createPanelView(this.tr("Logger"), loggerView);
      osparc.utils.Utils.setIdToWidget(loggerInPanelView.getTitleLabel(), "studyLoggerTitleLabel");
      if (!osparc.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
        loggerInPanelView.setCollapsed(true);
      }
      /*
      sidePanel.add(loggerInPanelView, {
        flex: 1
      });
      */

      const workbenchUI = this.__workbenchUI = new osparc.component.workbench.WorkbenchUI();
      workbenchUI.setStudy(study);

      this.__nodeView = new osparc.component.node.NodeView().set({
        minHeight: 200
      });

      this.__groupNodeView = new osparc.component.node.GroupNodeView().set({
        minHeight: 200
      });
    },

    __connectEvents: function() {
      const nodesTree = this.__nodesTree;
      nodesTree.addListener("removeNode", e => {
        if (this.getStudy().isReadOnly()) {
          return;
        }
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      nodesTree.addListener("changeSelectedNode", e => {
        const node = this.__workbenchUI.getNodeUI(e.getData());
        if (node && node.classname.includes("NodeUI")) {
          node.setActive(true);
        }
      });
      nodesTree.addListener("exportNode", e => {
        const nodeId = e.getData();
        this.__exportMacro(nodeId);
      });

      const workbenchUI = this.__workbenchUI;
      workbenchUI.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      workbenchUI.addListener("removeEdge", e => {
        const edgeId = e.getData();
        this.__removeEdge(edgeId);
      }, this);
      workbenchUI.addListener("changeSelectedNode", e => {
        const nodeId = e.getData();
        this.__nodesTree.nodeSelected(nodeId);
      });

      const workbenchToolbar = this.__mainPanel.getToolbar();
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

      const workbench = this.getStudy().getWorkbench();
      workbench.addListener("pipelineChanged", this.__workbenchChanged, this);

      workbench.addListener("showInLogger", ev => {
        const data = ev.getData();
        const nodeId = data.nodeId;
        const msg = data.msg;
        this.getLogger().info(nodeId, msg);
      }, this);
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

    __createPanelView: function(caption, widget) {
      return new osparc.desktop.PanelView(caption, widget);
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
      const study = this.getStudy();

      if (nodeId === null) {
        nodeId = study.getUuid();
      }

      const workbench = study.getWorkbench();
      const node = workbench.getNode(nodeId);
      if (node && node.isParameter()) {
        const parameterEditor = new osparc.component.node.ParameterEditor(node);
        parameterEditor.popUpInWindow();
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
      const title = this.tr("Edit Slideshow");
      const win = osparc.ui.window.Window.popUpInWindow(nodesSlidesTree, title, 600, 500).set({
        modal: false,
        clickAwayClose: false
      });
      nodesSlidesTree.addListener("finished", () => {
        win.close();
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
      this.getChildControl("container-scroll-0").setVisibility(maximize ? "excluded" : "visible");
    },

    __attachEventHandlers: function() {
      const blocker = this.getBlocker();
      blocker.addListener("tap", this.getChildControl("side-panel").toggleCollapsed.bind(this.getChildControl("side-panel")));

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

    __checkMaximizeable: function() {
      this.getChildControl("container-scroll-0").setVisibility("visible");
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

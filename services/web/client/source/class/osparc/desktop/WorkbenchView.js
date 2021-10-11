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

    this.getChildControl("splitter").setWidth(1);

    this.__sidePanels = this.getChildControl("side-panels");
    this.getChildControl("main-panel-tabs");
    this.__workbenchPanel = new osparc.desktop.WorkbenchPanel();
    this.__workbenchUI = this.__workbenchPanel.getMainView();

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
    __sidePanels: null,
    __nodesTree: null,
    __filesTree: null,
    __settingsPage: null,
    __outputsPage: null,
    __workbenchPanel: null,
    __workbenchPanelPage: null,
    __workbenchUI: null,
    __iFramePage: null,
    __loggerView: null,
    __groupNodeView: null,
    __currentNodeId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "side-panels": {
          control = new qx.ui.splitpane.Pane("horizontal").set({
            minWidth: 0,
            width: Math.min(parseInt(window.innerWidth * 0.4), 550)
          });
          control.getChildControl("splitter").setWidth(1);
          osparc.utils.Utils.addBorder(control, 2, "right");
          this.add(control, 0); // flex 0
          break;
        }
        case "side-panel-left-tabs": {
          control = new qx.ui.tabview.TabView().set({
            minWidth: 250,
            contentPadding: 6,
            barPosition: "top"
          });
          osparc.utils.Utils.addBorder(control, 2, "right");
          control.getChildControl("bar").set({
            paddingLeft: 60
          });
          const sidePanels = this.getChildControl("side-panels");
          sidePanels.add(control, 1); // flex 1
          break;
        }
        case "side-panel-right-tabs": {
          control = new qx.ui.tabview.TabView().set({
            minWidth: 300,
            contentPadding: 6,
            barPosition: "top"
          });
          control.getChildControl("bar").set({
            paddingLeft: 100
          });
          const sidePanels = this.getChildControl("side-panels");
          sidePanels.add(control, 1); // flex 1
          break;
        }
        case "main-panel-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 0,
            barPosition: "top"
          });
          control.getChildControl("bar").set({
            paddingLeft: 400
          });
          this.add(control, 1); // flex 1
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _applyStudy: function(study) {
      if (study) {
        this.__initViews();
        this.__connectEvents();
        this.__attachSocketEventHandlers();
      }
      this.__workbenchPanel.getToolbar().setStudy(study);
    },

    __createTabPage: function(icon, tooltip, widget) {
      const tabPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox(5),
        backgroundColor: "background-main",
        icon: icon+"/24"
      });
      tabPage.getChildControl("button").set({
        toolTipText: tooltip
      });
      if (widget) {
        tabPage.add(widget, {
          flex: 1
        });
      }
      return tabPage;
    },

    __initViews: function() {
      /*
      if (this.__sidePanels) {
        this.remove(this.__sidePanels);
        this.__sidePanels = this.getChildControl("side-panels");
      }
      if (this.__workbenchPanel) {
        this.remove(this.__workbenchPanel);
        this.__workbenchPanel = this.getChildControl("workbench-panel");
      }
      */

      const study = this.getStudy();


      const tabViewLeft = this.getChildControl("side-panel-left-tabs");

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree();
      nodesTree.setStudy(study);
      const nodesPage = this.__createTabPage("@FontAwesome5Solid/list", this.tr("Nodes"), nodesTree);
      tabViewLeft.add(nodesPage);

      const filesTree = this.__filesTree = new osparc.file.FilesTree().set({
        dragMechanism: true,
        hideRoot: true
      });
      filesTree.populateTree();
      const storagePage = this.__createTabPage("@FontAwesome5Solid/database", this.tr("Storage"), filesTree);
      tabViewLeft.add(storagePage);

      const parametersPage = this.__createTabPage("@FontAwesome5Solid/sliders-h", this.tr("Parameters"));
      tabViewLeft.add(parametersPage);


      const tabViewRight = this.getChildControl("side-panel-right-tabs");

      const settingsPage = this.__settingsPage = this.__createTabPage("@FontAwesome5Solid/sign-in-alt", this.tr("Settings"));
      tabViewRight.add(settingsPage);

      const outputsPage = this.__outputsPage = this.__createTabPage("@FontAwesome5Solid/sign-out-alt", this.tr("Outputs"));
      tabViewRight.add(outputsPage);


      const tabViewMain = this.getChildControl("main-panel-tabs");

      this.__workbenchUI.setStudy(study);
      const workbenchPanelPage = this.__workbenchPanelPage = this.__createTabPage("@FontAwesome5Solid/object-group", this.tr("Nodes"), this.__workbenchPanel);
      tabViewMain.add(workbenchPanelPage);

      /*
      this.__groupNodeView = new osparc.component.node.GroupNodeView().set({
        minHeight: 200
      });
      */

      const iFramePage = this.__iFramePage = this.__createTabPage("@FontAwesome5Solid/desktop", this.tr("Interactive"));
      tabViewMain.add(iFramePage);

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
      const logsPage = this.__logsPage = this.__createTabPage("@FontAwesome5Solid/file-alt", this.tr("Logger"), loggerView);
      tabViewMain.add(logsPage);
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
        const nodeUI = this.__workbenchUI.getNodeUI(e.getData());
        if (nodeUI) {
          if (nodeUI.classname.includes("NodeUI")) {
            nodeUI.setActive(true);
          }
          const node = nodeUI.getNode();
          this.__populateSecondPanel(node);
          this.__evalIframeButton(node);
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
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        this.__populateSecondPanel(node);
        this.__evalIframeButton(node);
      });

      const workbenchToolbar = this.__workbenchPanel.getToolbar();
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
      return this.__workbenchPanel.getToolbar().getStartStopButtons();
    },

    getSelectedNodes: function() {
      return this.__workbenchUI.getSelectedNodes();
    },

    getSelectedNodeIDs: function() {
      if (this.__workbenchPanel.getMainView() === this.__workbenchUI) {
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
      /*
      if (this.__groupNodeView) {
        this.__groupNodeView.restoreIFrame();
      }
      const prevNodeId = this.__currentNodeId;
      */
      this.__currentNodeId = nodeId;
      study.getUi().setCurrentNodeId(nodeId);

      this.__workbenchUI.loadModel(workbench);
      /*
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
      }
      */

      this.__evalIframeButton(node);
      const tabViewMain = this.getChildControl("main-panel-tabs");
      if (node && node.getIFrame()) {
        tabViewMain.setSelection([this.__iFramePage]);
        this.__addIFrame(node);
      } else {
        tabViewMain.setSelection([this.__workbenchPanelPage]);
      }
    },

    __evalIframeButton: function(node) {
      if (node && node.getIFrame()) {
        this.__iFramePage.getChildControl("button").set({
          enabled: true
        });
      } else {
        this.__iFramePage.getChildControl("button").set({
          enabled: false
        });
      }
    },

    __maximizeIFrame: function(maximize) {
      console.log("maximizeIFrame", maximize);
      // this.getChildControl("main-panel-tabs").setVisibility(maximize ? "visible" : "excluded");
    },

    __addIFrame: function(node) {
      this.__iFramePage.removeAll();

      const loadingPage = node.getLoadingPage();
      const iFrame = node.getIFrame();
      if (loadingPage && iFrame) {
        [
          loadingPage,
          iFrame
        ].forEach(widget => {
          if (widget) {
            widget.addListener("maximize", e => {
              this.__maximizeIFrame(true);
            }, this);
            widget.addListener("restore", e => {
              this.__maximizeIFrame(false);
            }, this);
            this.__maximizeIFrame(widget.hasState("maximized"));
          }
        });
        this.__iFrameChanged(node);

        iFrame.addListener("load", () => {
          this.__iFrameChanged(node);
        });
      } else {
        // This will keep what comes after at the bottom
        this.__iFramePage.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
      }
    },

    __iFrameChanged: function(node) {
      this.__iFramePage.removeAll();

      const loadingPage = node.getLoadingPage();
      const iFrame = node.getIFrame();
      const src = iFrame.getSource();
      const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
      this.__iFramePage.add(iFrameView, {
        flex: 1
      });
    },

    __populateSecondPanel: function(node) {
      this.__settingsPage.removeAll();
      this.__outputsPage.removeAll();
      if (node) {
        if (node.isPropertyInitialized("propsForm") && node.getPropsForm()) {
          this.__settingsPage.add(node.getPropsForm(), {
            flex: 1
          });
        }

        const portTree = new osparc.component.widget.inputs.NodeOutputTree(node, node.getMetaData().outputs);
        this.__outputsPage.add(portTree, {
          flex: 1
        });
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
      this.getChildControl("side-panels").setVisibility(maximize ? "excluded" : "visible");
    },

    __attachEventHandlers: function() {
      // const blocker = this.getBlocker();
      // blocker.addListener("tap", this.getChildControl("side-panels").toggleCollapsed.bind(this.getChildControl("side-panels")));

      const maximizeIframeCb = msg => {
        this.__maximizeIframe(msg.getData());
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);
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
      // this.__workbenchPanel.setMainView(widget);

      if (widget.getNode && widget.getInputsView) {
        setTimeout(() => {
          widget.getInputsView().setCollapsed(widget.getNode().getInputNodes().length === 0);
        }, 150);
      }

      this.__nodesTree.nodeSelected(nodeId);
      this.__loggerView.setCurrentNodeId(nodeId);
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
      return;
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

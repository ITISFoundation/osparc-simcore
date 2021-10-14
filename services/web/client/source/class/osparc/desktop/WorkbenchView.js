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
    __studyTreeItem: null,
    __nodesTree: null,
    __filesTree: null,
    __settingsPage: null,
    __outputsPage: null,
    __workbenchPanel: null,
    __workbenchPanelPage: null,
    __workbenchUI: null,
    __iFramePage: null,
    __loggerView: null,
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
          const sidePanels = this.getChildControl("side-panels");
          sidePanels.add(control, 1); // flex 1
          break;
        }
        case "main-panel-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 0,
            barPosition: "top"
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
      const study = this.getStudy();
      if (study === null) {
        return;
      }
      this.__initPrimaryColumn();
      this.__initSecondaryColumn();
      this.__initMainView();
    },

    __initPrimaryColumn: function() {
      const study = this.getStudy();

      const tabViewPrimary = this.getChildControl("side-panel-left-tabs");
      this.__removePages(tabViewPrimary);

      const topBar = tabViewPrimary.getChildControl("bar");
      this.__addTopBarSpacer(topBar);

      const homeAndNodesTree = new qx.ui.container.Composite(new qx.ui.layout.VBox(6));

      const studyTreeItem = this.__studyTreeItem = new osparc.component.widget.StudyTitleOnlyTree().set({
        minHeight: 21,
        maxHeight: 24
      });
      studyTreeItem.setStudy(study);
      homeAndNodesTree.add(studyTreeItem);

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree().set({
        hideRoot: true
      });
      nodesTree.setStudy(study);
      homeAndNodesTree.add(nodesTree, {
        flex: 1
      });
      const nodesPage = this.__createTabPage("@FontAwesome5Solid/list", this.tr("Nodes"), homeAndNodesTree);
      tabViewPrimary.add(nodesPage);

      const filesTree = this.__filesTree = new osparc.file.FilesTree().set({
        dragMechanism: true,
        hideRoot: true
      });
      filesTree.populateTree();
      const storagePage = this.__createTabPage("@FontAwesome5Solid/database", this.tr("Storage"), filesTree);
      tabViewPrimary.add(storagePage);

      this.__addTopBarSpacer(topBar);
    },

    __initSecondaryColumn: function() {
      const tabViewSecondary = this.getChildControl("side-panel-right-tabs");
      this.__removePages(tabViewSecondary);

      const topBar = tabViewSecondary.getChildControl("bar");
      this.__addTopBarSpacer(topBar);

      const infoPage = this.__infoPage = this.__createTabPage("@FontAwesome5Solid/info", this.tr("Information"));
      infoPage.exclude();
      tabViewSecondary.add(infoPage);

      const settingsPage = this.__settingsPage = this.__createTabPage("@FontAwesome5Solid/sign-in-alt", this.tr("Settings"));
      settingsPage.exclude();
      tabViewSecondary.add(settingsPage);

      const outputsPage = this.__outputsPage = this.__createTabPage("@FontAwesome5Solid/sign-out-alt", this.tr("Outputs"));
      outputsPage.exclude();
      tabViewSecondary.add(outputsPage);

      this.__addTopBarSpacer(topBar);

      this.__populateSecondPanel();
    },

    __initMainView: function() {
      const study = this.getStudy();

      const tabViewMain = this.getChildControl("main-panel-tabs");
      this.__removePages(tabViewMain);

      const topBar = tabViewMain.getChildControl("bar");
      this.__addTopBarSpacer(topBar);

      this.__workbenchUI.setStudy(study);
      this.__workbenchUI.loadModel(study.getWorkbench());
      const workbenchPanelPage = this.__workbenchPanelPage = this.__createTabPage("@FontAwesome5Solid/object-group", this.tr("Workbench"), this.__workbenchPanel);
      tabViewMain.add(workbenchPanelPage);

      const iFramePage = this.__iFramePage = this.__createTabPage("@FontAwesome5Solid/desktop", this.tr("Interactive"));
      tabViewMain.add(iFramePage);

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
      const logsPage = this.__logsPage = this.__createTabPage("@FontAwesome5Solid/file-alt", this.tr("Logger"), loggerView);
      tabViewMain.add(logsPage);

      this.__addTopBarSpacer(topBar);
    },

    __removePages: function(tabView) {
      const pages = tabView.getChildren();
      // remove pages
      for (let i=pages.length-1; i>=0; i--) {
        tabView.remove(pages[i]);
      }
      // remove spacers
      const topBar = tabView.getChildControl("bar");
      topBar.removeAll();
    },

    __addTopBarSpacer: function(tabViewTopBar) {
      const spacer = new qx.ui.core.Spacer();
      tabViewTopBar.add(spacer, {
        flex: 1
      });
    },

    __connectEvents: function() {
      const studyTreeItem = this.__studyTreeItem;
      const nodesTree = this.__nodesTree;
      const workbenchUI = this.__workbenchUI;

      studyTreeItem.addListener("nodeSelected", () => {
        nodesTree.resetSelection();
        this.__populateSecondPanel(this.getStudy());
        this.__evalIframe();
        this.__openWorkbench();
      });

      nodesTree.addListener("nodeSelected", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          this.__populateSecondPanel(node);
          this.__evalIframe(node);
          if (node.isDynamic()) {
            this.__openIframe(node);
          } else {
            this.__openWorkbench();
          }
        }
        const nodeUI = workbenchUI.getNodeUI(nodeId);
        if (nodeUI) {
          if (nodeUI.classname.includes("NodeUI")) {
            workbenchUI.activeNodeChanged(nodeUI);
          }
        }
      });
      nodesTree.addListener("fullscreenNode", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          this.__populateSecondPanel(node);
          this.__evalIframe(node);
          this.__openIframe(node);
          this.__maximizeIframe(true);
        }
        const nodeUI = workbenchUI.getNodeUI(nodeId);
        if (nodeUI) {
          if (nodeUI.classname.includes("NodeUI")) {
            workbenchUI.activeNodeChanged(nodeUI);
          }
        }
      }, this);
      nodesTree.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);

      workbenchUI.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);
      workbenchUI.addListener("removeEdge", e => {
        const edgeId = e.getData();
        this.__removeEdge(edgeId);
      }, this);
      workbenchUI.addListener("changeSelectedNode", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        this.__nodesTree.nodeSelected(nodeId);
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        this.__populateSecondPanel(node);
        this.__evalIframe(node);
      });
      workbenchUI.addListener("nodeSelected", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        this.__nodesTree.nodeSelected(nodeId);
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        this.__populateSecondPanel(node);
        this.__evalIframe(node);
        this.__openIframe(node);
      }, this);

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

      this.__currentNodeId = nodeId;
      study.getUi().setCurrentNodeId(nodeId);

      if (this.__nodesTree) {
        this.__nodesTree.nodeSelected(nodeId);
      }

      const node = study.getWorkbench().getNode(nodeId);
      this.__populateSecondPanel(node);
    },

    __evalIframe: function(node) {
      if (node && node.getIFrame()) {
        this.__iFramePage.getChildControl("button").set({
          enabled: true
        });
        this.__addIframe(node);
      } else {
        this.__iFramePage.getChildControl("button").set({
          enabled: false
        });
      }
    },

    __openWorkbench: function() {
      const tabViewMain = this.getChildControl("main-panel-tabs");
      tabViewMain.setSelection([this.__workbenchPanelPage]);
    },

    __openIframe: function(node) {
      const tabViewMain = this.getChildControl("main-panel-tabs");
      if (node && node.getIFrame()) {
        tabViewMain.setSelection([this.__iFramePage]);
      } else {
        tabViewMain.setSelection([this.__workbenchPanelPage]);
      }
    },

    __maximizeIframe: function(maximize) {
      this.getBlocker().setStyles({
        display: maximize ? "none" : "block"
      });

      this.getChildControl("side-panels").setVisibility(maximize ? "excluded" : "visible");

      const tabViewMain = this.getChildControl("main-panel-tabs");
      const mainViewtopBar = tabViewMain.getChildControl("bar");
      mainViewtopBar.setVisibility(maximize ? "excluded" : "visible");
    },

    __addIframe: function(node) {
      this.__iFramePage.removeAll();

      const loadingPage = node.getLoadingPage();
      const iFrame = node.getIFrame();
      if (loadingPage && iFrame) {
        [
          loadingPage,
          iFrame
        ].forEach(widget => {
          if (widget) {
            widget.addListener("maximize", () => this.__maximizeIframe(true), this);
            widget.addListener("restore", () => this.__maximizeIframe(false), this);
          }
        });
        this.__iFrameChanged(node);

        iFrame.addListener("load", () => this.__iFrameChanged(node), this);
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
      this.__infoPage.removeAll();
      this.__settingsPage.removeAll();
      this.__outputsPage.removeAll();
      this.__infoPage.getChildControl("button").exclude();
      this.__settingsPage.getChildControl("button").exclude();
      this.__outputsPage.getChildControl("button").exclude();

      if (node instanceof osparc.data.model.Study) {
        this.__infoPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__infoPage]);

        this.__infoPage.add(new osparc.studycard.Medium(node), {
          flex: 1
        });
      } else if (node && node.isFilePicker()) {
        this.__infoPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__infoPage]);

        const view = osparc.file.FilePicker.buildInfoView(node);
        view.setEnabled(false);
        this.__infoPage.add(view, {
          flex: 1
        });
      } else if (node && node.isParameter()) {
        this.__settingsPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__settingsPage]);

        const view = new osparc.component.node.ParameterEditor(node);
        view.buildForm(false);
        this.__settingsPage.add(view, {
          flex: 1
        });
      } else if (node) {
        this.__settingsPage.getChildControl("button").show();
        this.__outputsPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__settingsPage]);

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
      if (this.__nodesTree.getCurrentNodeId() === this.__currentNodeId) {
        this.nodeSelected(this.getStudy().getUuid());
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

    __workbenchChanged: function() {
      this.__nodesTree.populateTree();
      this.__nodesTree.nodeSelected(this.__currentNodeId);
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

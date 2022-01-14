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

    this.setOffset(2);
    osparc.desktop.WorkbenchView.decorateSplitter(this.getChildControl("splitter"));
    osparc.desktop.WorkbenchView.decorateSlider(this.getChildControl("slider"));

    this.__sidePanels = this.getChildControl("side-panels");
    this.getChildControl("main-panel-tabs");
    this.__workbenchPanel = new osparc.desktop.WorkbenchPanel();
    this.__workbenchUI = this.__workbenchPanel.getMainView();

    this.__attachEventHandlers();
  },

  statics: {
    TAB_BUTTON_HEIGHT: 50,

    decorateSplitter: function(splitter) {
      const colorManager = qx.theme.manager.Color.getInstance();
      const binaryColor = osparc.utils.Utils.getRoundedBinaryColor(colorManager.resolve("background-main"));
      splitter.set({
        width: 2,
        backgroundColor: binaryColor
      });
      colorManager.addListener("changeTheme", () => {
        const newBinaryColor = osparc.utils.Utils.getRoundedBinaryColor(colorManager.resolve("background-main"));
        splitter.setBackgroundColor(newBinaryColor);
      }, this);
    },

    decorateSlider: function(slider) {
      slider.set({
        width: 2,
        backgroundColor: "#007fd4", // Visual Studio blue
        opacity: 1
      });
    }
  },

  events: {
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event",
    "backToDashboardPressed": "qx.event.type.Event",
    "slidesEdit": "qx.event.type.Event",
    "slidesAppStart": "qx.event.type.Event",
    "takeSnapshot": "qx.event.type.Event",
    "showSnapshots": "qx.event.type.Event",
    "createIterations": "qx.event.type.Event",
    "showIterations": "qx.event.type.Event"
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
    __nodesPage: null,
    __studyTreeItem: null,
    __nodesTree: null,
    __filesTree: null,
    __storagePage: null,
    __studyOptionsPage: null,
    __infoPage: null,
    __settingsPage: null,
    __outputsPage: null,
    __workbenchPanel: null,
    __workbenchPanelPage: null,
    __workbenchUI: null,
    __iframePage: null,
    __loggerView: null,
    __currentNodeId: null,
    __startAppButton: null,
    __editSlidesButton: null,
    __collapseWithUserMenu: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "side-panels": {
          control = new qx.ui.splitpane.Pane("horizontal").set({
            offset: 2,
            width: Math.min(parseInt(window.innerWidth * (0.16 + 0.24)), 550)
          });
          osparc.desktop.WorkbenchView.decorateSplitter(control.getChildControl("splitter"));
          osparc.desktop.WorkbenchView.decorateSlider(control.getChildControl("slider"));
          this.add(control, 0); // flex 0
          break;
        }
        case "collapsible-view-left": {
          const sidePanels = this.getChildControl("side-panels");
          control = new osparc.component.widget.CollapsibleViewLight().set({
            minWidth: 15,
            width: Math.min(parseInt(window.innerWidth * 0.16), 240)
          });
          const caretExpandedLayout = control.getChildControl("caret-expanded-layout");
          caretExpandedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          const caretCollapsedLayout = control.getChildControl("caret-collapsed-layout");
          caretCollapsedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          control.bind("collapsed", control, "maxWidth", {
            converter: collapsed => collapsed ? 15 : null
          });
          control.bind("collapsed", sidePanels, "width", {
            converter: collapsed => this.__getSidePanelsNewWidth(collapsed, sidePanels, control)
          });
          control.addListener("changeCollapsed", e => {
            const collapsed = e.getData();
            const collapsibleViewLeft = this.getChildControl("collapsible-view-right");
            // if both panes are collapsed set the maxWidth of the layout to 2*15
            if (collapsed && collapsibleViewLeft.isCollapsed()) {
              sidePanels.setMaxWidth(2 * 15);
            } else {
              sidePanels.setMaxWidth(null);
            }
          }, this);
          // flex 0 by default, this will be changed if "collapsible-view-right" gets collapsed
          sidePanels.add(control, 0);
          break;
        }
        case "collapsible-view-right": {
          const sidePanels = this.getChildControl("side-panels");
          control = new osparc.component.widget.CollapsibleViewLight().set({
            minWidth: 15,
            width: Math.min(parseInt(window.innerWidth * 0.24), 310)
          });
          const caretExpandedLayout = control.getChildControl("caret-expanded-layout");
          caretExpandedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          const caretCollapsedLayout = control.getChildControl("caret-collapsed-layout");
          caretCollapsedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          control.bind("collapsed", control, "maxWidth", {
            converter: collapsed => collapsed ? 15 : null
          });
          control.bind("collapsed", sidePanels, "width", {
            converter: collapsed => this.__getSidePanelsNewWidth(collapsed, sidePanels, control)
          });
          control.addListener("changeCollapsed", e => {
            // switch flex to 1 if the secondary pane gets collapsed
            const collapsed = e.getData();
            const collapsibleViewLeft = this.getChildControl("collapsible-view-left");
            collapsibleViewLeft.setLayoutProperties({flex: collapsed ? 1 : 0});
            control.setLayoutProperties({flex: collapsed ? 0 : 1});

            // if both panes are collapsed set the maxWidth of the layout to 2*15
            if (collapsed && collapsibleViewLeft.isCollapsed()) {
              sidePanels.setMaxWidth(2 * 15);
            } else {
              sidePanels.setMaxWidth(null);
            }
          }, this);
          sidePanels.add(control, 1); // flex 1
          break;
        }
        case "side-panel-left-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 15 + 2, // collapse bar + padding
            contentPaddingRight: 2,
            barPosition: "top"
          });
          const collapsibleViewLeft = this.getChildControl("collapsible-view-left");
          collapsibleViewLeft.setContent(control);
          control.setBackgroundColor("background-main-lighter+");
          collapsibleViewLeft.getChildControl("expand-button").setBackgroundColor("background-main-lighter+");
          collapsibleViewLeft.getChildControl("collapse-button").setBackgroundColor("background-main-lighter+");
          break;
        }
        case "side-panel-right-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 15 + 2, // collapse bar + padding
            contentPaddingRight: 2,
            barPosition: "top"
          });
          const collapsibleViewRight = this.getChildControl("collapsible-view-right");
          collapsibleViewRight.setContent(control);
          break;
        }
        case "main-panel-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 2,
            barPosition: "top"
          });
          this.add(control, 1); // flex 1
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __getSidePanelsNewWidth: function(collapsed, sidePanels, collapsibleView) {
      const content = collapsibleView.getContent();
      if (sidePanels && sidePanels.getBounds() && content && content.getBounds()) {
        const oldWidth = sidePanels.getBounds().width;
        const contentWidth = content.getBounds().width;
        // if collapsed set width to show collapse button only
        return collapsed ? (oldWidth - contentWidth) : (oldWidth + contentWidth);
      }
      return null;
    },

    _applyStudy: function(study) {
      if (study) {
        this.__initViews();
        this.__connectEvents();
        this.__attachSocketEventHandlers();

        study.getWorkbench().addListener("pipelineChanged", () => this.__evalSlidesButtons());
        study.getUi().getSlideshow().addListener("changeSlideshow", () => this.__evalSlidesButtons());
        study.getUi().addListener("changeMode", () => this.__evalSlidesButtons());
        this.__evalSlidesButtons();

        // if there are no nodes, preselect the study item (show study info)
        const nodes = study.getWorkbench().getNodes(true);
        if (Object.values(nodes).length === 0) {
          this.__studyTreeItem.selectStudyItem();
        }
      }
      this.__workbenchPanel.getToolbar().setStudy(study);
    },

    __createTabPage: function(icon, tooltip, widget, backgroundColor = "background-main") {
      const tabPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox(10),
        backgroundColor,
        icon: icon + "/24"
      });
      const tabPageBtn = tabPage.getChildControl("button").set({
        toolTipText: tooltip,
        paddingTop: 12,
        height: this.self().TAB_BUTTON_HEIGHT,
        alignX: "center",
        alignY: "middle",
        backgroundColor
      });
      tabPageBtn.getContentElement().setStyles({
        "border": "0px"
      });
      tabPageBtn.bind("value", tabPageBtn, "backgroundColor", {
        converter: val => val ? backgroundColor : "contrasted-background+"
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
      const primaryColumnBGColor = "background-main-lighter+";
      const study = this.getStudy();

      const tabViewPrimary = this.getChildControl("side-panel-left-tabs");
      this.__removePages(tabViewPrimary);
      tabViewPrimary.setBackgroundColor(primaryColumnBGColor);
      const collapsibleViewLeft = this.getChildControl("collapsible-view-left");
      collapsibleViewLeft.getChildControl("expand-button").setBackgroundColor(primaryColumnBGColor);
      collapsibleViewLeft.getChildControl("collapse-button").setBackgroundColor(primaryColumnBGColor);


      const topBar = tabViewPrimary.getChildControl("bar");
      topBar.set({
        backgroundColor: "contrasted-background+",
        paddingLeft: 15
      });
      this.__addTopBarSpacer(topBar);

      const homeAndNodesTree = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
        backgroundColor: primaryColumnBGColor
      });

      const studyTreeItem = this.__studyTreeItem = new osparc.component.widget.StudyTitleOnlyTree().set({
        alignY: "middle",
        minHeight: 32,
        maxHeight: 32,
        backgroundColor: primaryColumnBGColor
      });
      studyTreeItem.setStudy(study);
      homeAndNodesTree.add(studyTreeItem);

      const nodesTree = this.__nodesTree = new osparc.component.widget.NodesTree().set({
        backgroundColor: primaryColumnBGColor,
        hideRoot: true,
        allowGrowY: true,
        minHeight: 5
      });
      nodesTree.setStudy(study);
      homeAndNodesTree.add(nodesTree);

      const addNewNodeBtn = new qx.ui.form.Button().set({
        label: this.tr("New node"),
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false,
        alignX: "center",
        marginLeft: 14
      });
      addNewNodeBtn.addListener("execute", () => this.__workbenchUI.openServiceCatalog({
        x: 50,
        y: 50
      }, {
        x: 50,
        y: 50
      }));
      homeAndNodesTree.add(addNewNodeBtn);

      const nodesPage = this.__nodesPage = this.__createTabPage("@FontAwesome5Solid/list", this.tr("Nodes"), homeAndNodesTree, primaryColumnBGColor);
      tabViewPrimary.add(nodesPage);

      const filesTree = this.__filesTree = new osparc.file.FilesTree().set({
        backgroundColor: primaryColumnBGColor,
        dragMechanism: true,
        hideRoot: true
      });
      filesTree.populateTree();
      const storagePage = this.__storagePage = this.__createTabPage("@FontAwesome5Solid/database", this.tr("Storage"), filesTree, primaryColumnBGColor);
      tabViewPrimary.add(storagePage);

      this.__addTopBarSpacer(topBar);
    },

    __initSecondaryColumn: function() {
      const tabViewSecondary = this.getChildControl("side-panel-right-tabs");
      this.__removePages(tabViewSecondary);

      const topBar = tabViewSecondary.getChildControl("bar");
      topBar.set({
        backgroundColor: "contrasted-background+",
        paddingLeft: 15
      });
      this.__addTopBarSpacer(topBar);

      const studyOptionsPage = this.__studyOptionsPage = this.__createTabPage("@FontAwesome5Solid/book", this.tr("Study options"));
      studyOptionsPage.getLayout().set({
        separator: "separator-vertical",
        spacing: 15
      });
      studyOptionsPage.exclude();
      tabViewSecondary.add(studyOptionsPage);

      const infoPage = this.__infoPage = this.__createTabPage("@FontAwesome5Solid/info", this.tr("Information"));
      infoPage.exclude();
      tabViewSecondary.add(infoPage);

      const settingsPage = this.__settingsPage = this.__createTabPage("@FontAwesome5Solid/sign-in-alt", this.tr("Settings"));
      settingsPage.exclude();
      tabViewSecondary.add(settingsPage);

      const outputsPage = this.__outputsPage = this.__createTabPage("@FontAwesome5Solid/sign-out-alt", this.tr("Outputs"));
      osparc.utils.Utils.setIdToWidget(outputsPage.getChildControl("button"), "outputsTabButton");
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

      const iframePage = this.__iframePage = this.__createTabPage("@FontAwesome5Solid/desktop", this.tr("Interactive"));
      osparc.utils.Utils.setIdToWidget(iframePage.getChildControl("button"), "iframeTabButton");
      tabViewMain.add(iframePage);

      const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
      const logsPage = this.__logsPage = this.__createTabPage("@FontAwesome5Solid/file-alt", this.tr("Logger"), loggerView);
      osparc.utils.Utils.setIdToWidget(logsPage.getChildControl("button"), "loggerTabButton");
      tabViewMain.add(logsPage);


      this.__addTopBarSpacer(topBar);


      const collapseWithUserMenu = this.__collapseWithUserMenu = new osparc.desktop.CollapseWithUserMenu();
      [
        "backToDashboardPressed",
        "collapseNavBar",
        "expandNavBar"
      ].forEach(signalName => collapseWithUserMenu.addListener(signalName, () => this.fireEvent(signalName)), this);

      topBar.add(collapseWithUserMenu);
    },

    getCollapseWithUserMenu: function() {
      return this.__collapseWithUserMenu;
    },

    __removePages: function(tabView) {
      const pages = tabView.getChildren();
      // remove pages
      for (let i = pages.length - 1; i >= 0; i--) {
        tabView.remove(pages[i]);
      }
      // remove spacers
      const topBar = tabView.getChildControl("bar");
      topBar.removeAll();
    },

    __addTopBarSpacer: function(tabViewTopBar) {
      const spacer = new qx.ui.core.Widget().set({
        backgroundColor: "contrasted-background+"
      });
      tabViewTopBar.add(spacer, {
        flex: 1
      });
    },

    __createCollapsibleViewSpacer: function() {
      const spacer = new qx.ui.core.Widget().set({
        backgroundColor: "contrasted-background+",
        height: this.self().TAB_BUTTON_HEIGHT
      });
      return spacer;
    },

    __connectEvents: function() {
      const studyTreeItem = this.__studyTreeItem;
      const nodesTree = this.__nodesTree;
      const workbenchUI = this.__workbenchUI;

      studyTreeItem.addListener("nodeSelected", () => {
        nodesTree.resetSelection();
        this.__populateSecondPanel(this.getStudy());
        this.__evalIframe();
        this.__openWorkbenchTab();
        this.__loggerView.setCurrentNodeId(null);
      });
      nodesTree.addListener("nodeSelected", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          this.__populateSecondPanel(node);
          this.__openIframeTab(node);
        }
        this.__loggerView.setCurrentNodeId(nodeId);
        const nodeUI = workbenchUI.getNodeUI(nodeId);
        if (nodeUI) {
          if (nodeUI.classname.includes("NodeUI")) {
            workbenchUI.activeNodeChanged(nodeUI);
          }
        }
      });
      workbenchUI.addListener("changeSelectedNode", e => {
        const nodeId = e.getData();
        if (nodeId) {
          studyTreeItem.resetSelection();
          this.__nodesTree.nodeSelected(nodeId);
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          this.__populateSecondPanel(node);
          this.__evalIframe(node);
          this.__loggerView.setCurrentNodeId(nodeId);
        } else {
          // empty selection
          this.__studyTreeItem.selectStudyItem();
        }
      });
      workbenchUI.addListener("nodeSelected", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        this.__nodesTree.nodeSelected(nodeId);
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        this.__populateSecondPanel(node);
        this.__openIframeTab(node);
        this.__loggerView.setCurrentNodeId(nodeId);
      }, this);

      nodesTree.addListener("fullscreenNode", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          this.__populateSecondPanel(node);
          this.__openIframeTab(node);
          node.getLoadingPage().maximizeIFrame(true);
          node.getIFrame().maximizeIFrame(true);
        }
        this.__loggerView.setCurrentNodeId(nodeId);
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
      workbenchUI.addListener("removeNodes", e => {
        const nodeIds = e.getData();
        this.__removeNodes(nodeIds);
      }, this);
      workbenchUI.addListener("removeEdge", e => {
        const edgeId = e.getData();
        this.__removeEdge(edgeId);
      }, this);

      const workbench = this.getStudy().getWorkbench();
      workbench.addListener("pipelineChanged", this.__workbenchChanged, this);

      workbench.addListener("showInLogger", e => {
        const data = e.getData();
        const nodeId = data.nodeId;
        const msg = data.msg;
        this.__loggerView.info(nodeId, msg);
      }, this);

      workbench.addListener("fileRequested", () => {
        if (this.getStudy().getUi().getMode() === "workbench") {
          const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
          tabViewLeftPanel.setSelection([this.__storagePage]);
        }
      }, this);
    },

    __attachSocketEventHandlers: function() {
      // Listen to socket
      const socket = osparc.wrapper.WebSocket.getInstance();

      // callback for incoming logs
      const slotName = "logger";
      if (!socket.slotExists(slotName)) {
        socket.on(slotName, jsonString => {
          const data = JSON.parse(jsonString);
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy().getUuid() !== data["project_id"]) {
            // Filtering out logs from other studies
            return;
          }
          const nodeId = data["node_id"];
          const messages = data["messages"];
          this.__loggerView.infos(nodeId, messages);
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
        socket.on(slotName2, data => {
          const d = JSON.parse(data);
          const nodeId = d["node_id"];
          const progress = Number.parseFloat(d["progress"]).toFixed(4);
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
          const nodeId = d["node_id"];
          const nodeData = d["data"];
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node && nodeData) {
            node.setOutputData(nodeData.outputs);
            node.populateStates(nodeData);
          } else if (osparc.data.Permissions.getInstance().isTester()) {
            console.log("Ignored ws 'nodeUpdated' msg", d);
          }
        }, this);
      }

      // callback for events
      const slotName4 = "event";
      if (!socket.slotExists(slotName4)) {
        socket.on(slotName4, eventData => {
          const eventPayload = JSON.parse(eventData);
          const action = eventPayload["action"];
          if (action == "RELOAD_IFRAME") {
            // TODO: maybe reload iframe in the future
            // for now a message is displayed to the user
            const nodeId = eventPayload["node_id"];

            const workbench = this.getStudy().getWorkbench();
            const node = workbench.getNode(nodeId);
            const label = node.getLabel();
            const text = `New inputs for service ${label}. Please reload to refresh service.`;
            osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");
          }
        }, this);
      }
    },

    listenToNodeUpdated: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      const slotName = "nodeUpdated";
      if (!socket.slotExists(slotName)) {
        socket.on(slotName, data => {
          const d = JSON.parse(data);
          const studyId = d["project_id"];
          if (studyId !== this.getStudy().getUuid()) {
            return;
          }
          this.getStudy().nodeUpdated(d);
        }, this);
      }
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
      if (nodeId === null || nodeId === undefined) {
        nodeId = study.getUuid();
      }

      this.__currentNodeId = nodeId;
      study.getUi().setCurrentNodeId(nodeId);

      if (this.__nodesTree) {
        this.__nodesTree.nodeSelected(nodeId);
      }

      if (nodeId === study.getUuid()) {
        this.__studyTreeItem.selectStudyItem();
      } else {
        const node = study.getWorkbench().getNode(nodeId);
        this.__populateSecondPanel(node);
      }
    },

    __evalIframe: function(node) {
      if (node && node.getIFrame()) {
        this.__iframePage.getChildControl("button").set({
          enabled: true
        });
        this.__addIframe(node);
      } else {
        this.__iframePage.getChildControl("button").set({
          enabled: false
        });
      }
    },

    __openWorkbenchTab: function() {
      const tabViewMain = this.getChildControl("main-panel-tabs");
      tabViewMain.setSelection([this.__workbenchPanelPage]);
    },

    __openIframeTab: function(node) {
      this.__evalIframe(node);
      const tabViewMain = this.getChildControl("main-panel-tabs");
      if (node && node.getIFrame()) {
        tabViewMain.setSelection([this.__iframePage]);
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
      this.__iframePage.removeAll();

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
        this.__iframePage.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
      }
    },

    __iFrameChanged: function(node) {
      this.__iframePage.removeAll();

      const loadingPage = node.getLoadingPage();
      const iFrame = node.getIFrame();
      const src = iFrame.getSource();
      const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
      this.__iframePage.add(iFrameView, {
        flex: 1
      });
    },

    __populateSecondPanel: function(node) {
      [
        this.__studyOptionsPage,
        this.__infoPage,
        this.__settingsPage,
        this.__outputsPage
      ].forEach(page => {
        page.removeAll();
        page.getChildControl("button").exclude();
      });

      const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
      tabViewLeftPanel.setSelection([this.__nodesPage]);

      if (node instanceof osparc.data.model.Study) {
        this.__populateSecondPanelStudy(node);
      } else if (node && node.isFilePicker()) {
        this.__populateSecondPanelFilePicker(node);
      } else if (node && node.isParameter()) {
        this.__populateSecondPanelParameter(node);
      } else if (node) {
        this.__populateSecondPanelNode(node);
      }
    },

    __populateSecondPanelStudy: function(study) {
      this.__studyOptionsPage.getChildControl("button").show();
      this.getChildControl("side-panel-right-tabs").setSelection([this.__studyOptionsPage]);

      this.__studyOptionsPage.add(new osparc.studycard.Medium(study), {
        flex: 1
      });
      this.__studyOptionsPage.add(this.__getSlideshowSection());
      this.__studyOptionsPage.add(this.__getSnapshotsSection());
      this.__studyOptionsPage.add(this.__getIterationsSection());
    },

    __getSlideshowSection: function() {
      const slideshowSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      slideshowSection.add(new qx.ui.basic.Label(this.tr("App Mode")).set({
        font: "title-14"
      }));

      const slideshowButtons = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      slideshowSection.add(slideshowButtons);

      const buttonsHeight = 28;
      const editSlidesBtn = this.__editSlidesButton = new qx.ui.form.Button().set({
        label: this.tr("Edit"),
        icon: "@FontAwesome5Solid/edit/14",
        height: buttonsHeight
      });
      editSlidesBtn.addListener("execute", () => this.fireEvent("slidesEdit"), this);
      slideshowButtons.add(editSlidesBtn);

      const startAppBtn = this.__startAppButton = new qx.ui.form.Button().set({
        label: this.tr("Start"),
        icon: "@FontAwesome5Solid/play/14",
        toolTipText: this.tr("Start App Mode"),
        height: buttonsHeight
      });
      startAppBtn.addListener("execute", () => this.fireEvent("slidesAppStart"), this);
      slideshowButtons.add(startAppBtn);

      this.__evalSlidesButtons();

      return slideshowSection;
    },

    __evalSlidesButtons: function() {
      const study = this.getStudy();
      if (study && this.__editSlidesButton) {
        const areSlidesEnabled = osparc.data.Permissions.getInstance().canDo("study.slides");
        const isOwner = osparc.data.model.Study.isOwner(study);
        this.__editSlidesButton.setEnabled(areSlidesEnabled && isOwner);
        this.__startAppButton.setEnabled(study.hasSlideshow() || study.getWorkbench().isPipelineLinear());
      }
    },

    __getSnapshotsSection: function() {
      const snapshotSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      snapshotSection.add(new qx.ui.basic.Label(this.tr("Snapshots")).set({
        font: "title-14"
      }));

      const snapshotButtons = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      snapshotSection.add(snapshotButtons);

      const buttonsHeight = 28;
      const takeSnapshotBtn = new qx.ui.form.Button().set({
        label: this.tr("New"),
        height: buttonsHeight
      });
      takeSnapshotBtn.setEnabled(osparc.data.Permissions.getInstance().canDo("study.snapshot.create"));
      takeSnapshotBtn.addListener("execute", () => this.fireEvent("takeSnapshot"), this);
      snapshotButtons.add(takeSnapshotBtn);

      const showSnapshotsBtn = new qx.ui.form.Button().set({
        label: this.tr("Show"),
        height: buttonsHeight
      });
      const store = osparc.store.Store.getInstance();
      store.bind("snapshots", showSnapshotsBtn, "enabled", {
        converter: snapshots => Boolean(snapshots.length)
      });
      showSnapshotsBtn.addListener("execute", () => this.fireEvent("showSnapshots"), this);
      snapshotButtons.add(showSnapshotsBtn);

      return snapshotSection;
    },

    __getIterationsSection: function() {
      const iterationsSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      iterationsSection.add(new qx.ui.basic.Label(this.tr("Iterations")).set({
        font: "title-14"
      }));

      const iterationButtons = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      iterationsSection.add(iterationButtons);

      const buttonsHeight = 28;
      const createIterationsBtn = new qx.ui.form.Button().set({
        label: this.tr("Create"),
        height: buttonsHeight
      });
      createIterationsBtn.setEnabled(osparc.data.Permissions.getInstance().canDo("study.snapshot.create"));
      createIterationsBtn.setEnabled(false);
      createIterationsBtn.addListener("execute", () => this.fireEvent("createIterations"), this);
      iterationButtons.add(createIterationsBtn);

      const showIterationsBtn = new qx.ui.form.Button().set({
        label: this.tr("Show"),
        height: buttonsHeight
      });
      const store = osparc.store.Store.getInstance();
      store.bind("iterations", showIterationsBtn, "enabled", {
        converter: iterations => Boolean(iterations.length)
      });
      showIterationsBtn.addListener("execute", () => this.fireEvent("showIterations"), this);
      iterationButtons.add(showIterationsBtn);

      return iterationsSection;
    },

    __populateSecondPanelFilePicker: function(filePicker) {
      if (osparc.file.FilePicker.hasOutputAssigned(filePicker.getOutputs())) {
        this.__infoPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__infoPage]);

        const view = osparc.file.FilePicker.buildInfoView(filePicker);
        view.setEnabled(false);

        this.__infoPage.add(view);

        const hbox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
        const downloadFileBtn = new qx.ui.form.Button(this.tr("Download"), "@FontAwesome5Solid/cloud-download-alt/14").set({
          allowGrowX: false
        });
        downloadFileBtn.addListener("execute", () => osparc.file.FilePicker.downloadOutput(filePicker));
        hbox.add(downloadFileBtn);
        const resetFileBtn = new qx.ui.form.Button(this.tr("Reset"), "@FontAwesome5Solid/sync-alt/14").set({
          allowGrowX: false
        });
        resetFileBtn.addListener("execute", () => {
          osparc.file.FilePicker.resetOutputValue(filePicker);
          filePicker.setLabel("File Picker");
          this.getStudy().getWorkbench().giveUniqueNameToNode(filePicker, "File Picker");
          this.__populateSecondPanel(filePicker);
        }, this);
        hbox.add(resetFileBtn);
        this.__infoPage.add(hbox);
      } else {
        // empty File Picker
        const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
        tabViewLeftPanel.setSelection([this.__storagePage]);

        this.__settingsPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__settingsPage]);

        const filePickerView = new osparc.file.FilePicker(filePicker);
        filePickerView.buildLayout();

        const fileDrop = new osparc.file.FileDrop();
        fileDrop.addListener("localFileDropped", e => {
          const files = e.getData()["data"];
          if (filePickerView.uploadPendingFiles(files)) {
            setTimeout(() => this.__populateSecondPanel(filePicker), 500);
          }
          fileDrop.resetDropAction();
        });
        fileDrop.addListener("fileLinkDropped", e => {
          const data = e.getData()["data"];
          osparc.file.FilePicker.setOutputValueFromStore(filePicker, data.getLocation(), data.getDatasetId(), data.getFileId(), data.getLabel());
          this.__populateSecondPanel(filePicker);
          fileDrop.resetDropAction();
        });

        this.__settingsPage.add(fileDrop, {
          flex: 1
        });

        filePickerView.getChildControl("reload-button").exclude();
        filePickerView.getChildControl("files-tree").exclude();
        filePickerView.getChildControl("folder-viewer").exclude();
        filePickerView.getChildControl("selected-file-layout").exclude();
        filePickerView.getChildControl("select-button").exclude();
        filePickerView.addListener("itemSelected", () => this.__populateSecondPanel(filePicker));
        this.__settingsPage.add(filePickerView);
      }
    },

    __populateSecondPanelParameter: function(parameter) {
      this.__settingsPage.getChildControl("button").show();
      this.getChildControl("side-panel-right-tabs").setSelection([this.__settingsPage]);

      const view = new osparc.component.node.ParameterEditor(parameter);
      view.buildForm(false);
      this.__settingsPage.add(view, {
        flex: 1
      });
    },

    __populateSecondPanelNode: function(node) {
      this.__settingsPage.getChildControl("button").show();
      this.__outputsPage.getChildControl("button").show();
      if (![this.__settingsPage, this.__outputsPage].includes(this.getChildControl("side-panel-right-tabs").getSelection()[0])) {
        this.getChildControl("side-panel-right-tabs").setSelection([this.__settingsPage]);
      }

      if (node.isPropertyInitialized("propsForm") && node.getPropsForm()) {
        const scrollContariner = new qx.ui.container.Scroll();
        scrollContariner.add(node.getPropsForm());
        this.__settingsPage.add(scrollContariner, {
          flex: 1
        });
      }

      if (node.hasOutputs()) {
        const portTree = new osparc.component.widget.inputs.NodeOutputTree(node, node.getMetaData().outputs).set({
          allowGrowY: false
        });
        this.__outputsPage.add(portTree);
      }

      const outputFilesBtn = new qx.ui.form.Button(this.tr("Artifacts"), "@FontAwesome5Solid/folder-open/14").set({
        allowGrowX: false
      });
      osparc.utils.Utils.setIdToWidget(outputFilesBtn, "nodeOutputFilesBtn");
      outputFilesBtn.addListener("execute", () => osparc.component.node.BaseNodeView.openNodeDataManager(node));
      this.__outputsPage.add(outputFilesBtn);
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

      this.__workbenchUI.resetSelection();
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

      this.__workbenchUI.resetSelection();
    },

    __attachEventHandlers: function() {
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
        const msg = this.tr("Are you sure you want to delete the selected node?");
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

    __removeNodes: function(nodeIds) {
      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
      if (preferencesSettings.getConfirmDeleteNode()) {
        const msg = this.tr("Are you sure you want to delete the selected ") + nodeIds.length + " nodes?";
        const win = new osparc.ui.window.Confirmation(msg);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            nodeIds.forEach(nodeId => this.__doRemoveNode(nodeId));
          }
        }, this);
      } else {
        nodeIds.forEach(nodeId => this.__doRemoveNode(nodeId));
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
      if ([this.__currentNodeId, null].includes(this.__nodesTree.getCurrentNodeId())) {
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

    openFirstNode: function() {
      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
      if (preferencesSettings.getAutoOpenNode()) {
        const nodes = this.getStudy().getWorkbench().getNodes(true);
        const validNodes = Object.values(nodes).filter(node => node.isComputational() || node.isDynamic());
        if (validNodes.length === 1 && validNodes[0].isDynamic()) {
          const dynamicNode = validNodes[0];
          this.nodeSelected(dynamicNode.getNodeId());
          qx.event.Timer.once(() => {
            this.__openIframeTab(dynamicNode);
            dynamicNode.getLoadingPage().maximizeIFrame(true);
            dynamicNode.getIFrame().maximizeIFrame(true);
          }, this, 10);
          return;
        }
      }
      this.__maximizeIframe(false);
      this.nodeSelected(this.getStudy().getUuid());
    }
  }
});

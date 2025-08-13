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

/* eslint-disable no-underscore-dangle */

qx.Class.define("osparc.desktop.WorkbenchView", {
  extend: qx.ui.splitpane.Pane,

  construct: function() {
    this.base(arguments, "horizontal");

    this.setOffset(2);
    osparc.desktop.WorkbenchView.decorateSplitter(this.getChildControl("splitter"));
    osparc.desktop.WorkbenchView.decorateSlider(this.getChildControl("slider"));

    this.getChildControl("side-panels");
    this.getChildControl("main-panel-tabs");
    this.__workbenchPanel = new osparc.desktop.WorkbenchPanel();
    this.__workbenchUI = this.__workbenchPanel.getMainView();

    this.__attachEventHandlers();
  },

  statics: {
    PRIMARY_COL_BG_COLOR: "transparent",
    TAB_BUTTON_HEIGHT: 46,

    decorateSplitter: function(splitter) {
      splitter.set({
        width: 2,
        backgroundColor: "workbench-view-splitter"
      });
    },

    decorateSlider: function(slider) {
      slider.set({
        width: 2,
        backgroundColor: "visual-blue",
        opacity: 1
      });
    },

    openNodeDataManager: function(node) {
      const win = osparc.widget.StudyDataManager.popUpInWindow(node.getStudy().serialize(), node.getNodeId(), node.getLabel());
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
    }
  },

  events: {
    "changeSelectedNode": "qx.event.type.Data",
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event",
    "backToDashboardPressed": "qx.event.type.Event",
    "slidesEdit": "qx.event.type.Event",
    "annotationRectStart": "qx.event.type.Event",
    "takeSnapshot": "qx.event.type.Event",
    "showSnapshots": "qx.event.type.Event",
    "createIterations": "qx.event.type.Event",
    "showIterations": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      nullable: false
    },

    maximized: {
      check: "Boolean",
      init: null,
      nullable: false,
      apply: "__applyMaximized",
      event: "changeMaximized"
    }
  },

  members: {
    __nodesPage: null,
    __studyTreeItem: null,
    __nodesTree: null,
    __storagePage: null,
    __studyOptionsPage: null,
    __fileInfoPage: null,
    __serviceOptionsPage: null,
    __workbenchPanel: null,
    __workbenchPanelPage: null,
    __workbenchUI: null,
    __workbenchUIConnected: null,
    __iframePage: null,
    __loggerPage: null,
    __loggerView: null,
    __currentNodeId: null,
    __startAppButton: null,
    __editSlidesButton: null,
    __startAppButtonTB: null,
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
          control = new osparc.widget.CollapsibleViewLight().set({
            minWidth: osparc.widget.CollapsibleViewLight.CARET_WIDTH,
            width: Math.min(parseInt(window.innerWidth * 0.16), 240)
          });
          control.getChildControl("expand-button").setBackgroundColor(this.self().PRIMARY_COL_BG_COLOR);
          control.getChildControl("collapse-button").setBackgroundColor(this.self().PRIMARY_COL_BG_COLOR);
          const caretExpandedLayout = control.getChildControl("caret-expanded-layout");
          caretExpandedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          const caretCollapsedLayout = control.getChildControl("caret-collapsed-layout");
          caretCollapsedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          control.bind("collapsed", control, "maxWidth", {
            converter: collapsed => collapsed ? osparc.widget.CollapsibleViewLight.CARET_WIDTH : null
          });
          control.bind("collapsed", sidePanels, "width", {
            converter: collapsed => this.__getSidePanelsNewWidth(collapsed, sidePanels, control)
          });
          control.addListener("changeCollapsed", e => {
            const collapsed = e.getData();
            const collapsibleViewLeft = this.getChildControl("collapsible-view-right");
            // if both panes are collapsed set the maxWidth of the layout to 2*15
            if (collapsed && collapsibleViewLeft.isCollapsed()) {
              sidePanels.setMaxWidth(2 * osparc.widget.CollapsibleViewLight.CARET_WIDTH);
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
          control = new osparc.widget.CollapsibleViewLight().set({
            minWidth: 15,
            width: Math.min(parseInt(window.innerWidth * 0.24), 310)
          });
          const caretExpandedLayout = control.getChildControl("caret-expanded-layout");
          caretExpandedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          const caretCollapsedLayout = control.getChildControl("caret-collapsed-layout");
          caretCollapsedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          control.bind("collapsed", control, "maxWidth", {
            converter: collapsed => collapsed ? osparc.widget.CollapsibleViewLight.CARET_WIDTH : null
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
              sidePanels.setMaxWidth(2 * osparc.widget.CollapsibleViewLight.CARET_WIDTH);
            } else {
              sidePanels.setMaxWidth(null);
            }
          }, this);
          sidePanels.add(control, 1); // flex 1
          break;
        }
        case "side-panel-left-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: osparc.widget.CollapsibleViewLight.CARET_WIDTH + 2, // collapse bar + padding
            contentPaddingRight: 2,
            barPosition: "top"
          });
          const collapsibleViewLeft = this.getChildControl("collapsible-view-left");
          collapsibleViewLeft.setContent(control);
          break;
        }
        case "side-panel-right-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: osparc.widget.CollapsibleViewLight.CARET_WIDTH + 2, // collapse bar + padding
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

    getNodesTree: function() {
      return this.__nodesTree;
    },

    getWorkbenchUI: function() {
      return this.__workbenchUI;
    },

    __getSidePanelsNewWidth: function(collapsing, sidePanels, collapsibleView) {
      let sidePanelsNewWidth = null;
      const sidePanelsWidth = (sidePanels.getBounds() && ("width" in sidePanels.getBounds())) ? sidePanels.getBounds().width : 250;
      if (collapsing) {
        const content = collapsibleView.getChildControl("scroll-content");
        sidePanelsNewWidth = (content.getBounds() && ("width" in content.getBounds())) ? sidePanelsWidth - content.getBounds().width : 150;
      } else if ("precollapseWidth" in collapsibleView) {
        sidePanelsNewWidth = sidePanelsWidth + (collapsibleView.precollapseWidth - osparc.widget.CollapsibleViewLight.CARET_WIDTH);
      }
      return sidePanelsNewWidth;
    },

    __applyStudy: function(study) {
      if (study) {
        this.__initViews();
        this.__connectEvents();

        study.getWorkbench().addListener("pipelineChanged", () => this.__evalSlidesButtons());
        study.getWorkbench().addListener("nodeAdded", e => {
          const node = e.getData();
          this.__nodeAdded(node);
        });
        study.getWorkbench().addListener("nodeRemoved", e => {
          const {nodeId, connectedEdgeIds} = e.getData();
          this.__nodeRemoved(nodeId, connectedEdgeIds);
        });
        study.getUi().getSlideshow().addListener("changeSlideshow", () => this.__evalSlidesButtons());
        study.getUi().addListener("changeMode", () => this.__evalSlidesButtons());
        this.__evalSlidesButtons();

        // if there are no nodes, preselect the study item (show study info)
        const nodes = study.getWorkbench().getNodes();
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
        icon: icon + "/16"
      });
      const tabPageBtn = tabPage.getChildControl("button").set({
        toolTipText: tooltip,
        margin: [12, 2, 0],
        padding: [8, 10, 8, 10],
        height: this.self().TAB_BUTTON_HEIGHT,
        alignX: "center",
        alignY: "middle",
        backgroundColor
      });
      tabPageBtn.bind("value", tabPageBtn, "backgroundColor", {
        converter: val => val ? "default-button-disabled-background" : undefined
      });
      tabPageBtn.bind("value", tabPageBtn, "textColor", {
        converter: val => val ? "default-button-text-outline" : "default-button-text-action"
      });
      tabPageBtn.bind("value", tabPageBtn, "decorator", {
        converter: val => val ? "tab-button-selected" : "tab-button"
      });
      if (widget) {
        const scrollView = new qx.ui.container.Scroll();
        scrollView.add(widget);
        tabPage.add(scrollView, {
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

      this.setMaximized(false);
    },

    __initPrimaryColumn: function() {
      const study = this.getStudy();

      const tabViewPrimary = this.getChildControl("side-panel-left-tabs");
      this.__removePages(tabViewPrimary);
      tabViewPrimary.setBackgroundColor(this.self().PRIMARY_COL_BG_COLOR);

      const topBar = tabViewPrimary.getChildControl("bar");
      topBar.set({
        height: this.self().TAB_BUTTON_HEIGHT,
        backgroundColor: "workbench-view-navbar"
      });
      this.__addTopBarSpacer(topBar);

      const homeAndNodesTree = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
        backgroundColor: "transparent"
      });

      const studyTreeItem = this.__studyTreeItem = new osparc.widget.StudyTitleOnlyTree().set({
        alignY: "middle",
        minHeight: 32,
        maxHeight: 32,
        backgroundColor: "transparent"
      });
      studyTreeItem.setStudy(study);
      homeAndNodesTree.add(studyTreeItem);

      const nodesTree = this.__nodesTree = new osparc.widget.NodesTree().set({
        backgroundColor: "transparent",
        allowGrowY: true,
        minHeight: 5
      });
      nodesTree.setStudy(study);
      homeAndNodesTree.add(nodesTree);

      const addNewNodeBtn = new qx.ui.form.Button().set({
        appearance: "form-button",
        label: this.tr("New Node"),
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false,
        alignX: "center",
        marginLeft: 10
      });
      this.getStudy().bind("pipelineRunning", addNewNodeBtn, "enabled", {
        converter: running => !running
      });
      osparc.utils.Utils.setIdToWidget(addNewNodeBtn, "newNodeBtn");
      addNewNodeBtn.addListener("execute", () => {
        this.__workbenchUI.openServiceCatalog({
          x: 50,
          y: 50
        });
      });
      homeAndNodesTree.add(addNewNodeBtn);

      const nodesPage = this.__nodesPage = this.__createTabPage("@FontAwesome5Solid/list", this.tr("Nodes"), homeAndNodesTree, this.self().PRIMARY_COL_BG_COLOR);
      tabViewPrimary.add(nodesPage);

      const filesTree = new osparc.file.FilesTree().set({
        backgroundColor: "transparent",
        dragMechanism: true,
        hideRoot: true
      });
      filesTree.populateLocations();
      const storagePage = this.__storagePage = this.__createTabPage("@FontAwesome5Solid/database", this.tr("Storage"), filesTree, this.self().PRIMARY_COL_BG_COLOR);
      tabViewPrimary.add(storagePage);

      this.__addTopBarSpacer(topBar);
    },

    __initSecondaryColumn: function() {
      const tabViewSecondary = this.getChildControl("side-panel-right-tabs");
      this.__removePages(tabViewSecondary);
      tabViewSecondary.setBackgroundColor(this.self().PRIMARY_COL_BG_COLOR);
      const topBar = tabViewSecondary.getChildControl("bar");
      topBar.set({
        height: this.self().TAB_BUTTON_HEIGHT,
        backgroundColor: "workbench-view-navbar"
      });
      this.__addTopBarSpacer(topBar);

      const studyOptionsPage = this.__studyOptionsPage = this.__createTabPage("@FontAwesome5Solid/book", this.tr("Project options"));
      studyOptionsPage.getLayout().set({
        separator: "separator-vertical",
        spacing: 10
      });
      studyOptionsPage.exclude();
      tabViewSecondary.add(studyOptionsPage);

      const fileInfoPage = this.__fileInfoPage = this.__createTabPage("@FontAwesome5Solid/info", this.tr("Information"));
      fileInfoPage.exclude();
      tabViewSecondary.add(fileInfoPage);

      const serviceOptionsPage = this.__serviceOptionsPage = this.__createTabPage("@FontAwesome5Solid/exchange-alt", this.tr("Service options"));
      serviceOptionsPage.exclude();
      tabViewSecondary.add(serviceOptionsPage);

      this.__addTopBarSpacer(topBar);

      this.__populateSecondaryColumn();
    },

    __initMainView: function() {
      const study = this.getStudy();

      const tabViewMain = this.getChildControl("main-panel-tabs");
      this.__removePages(tabViewMain);

      const topBar = tabViewMain.getChildControl("bar");
      topBar.set({
        height: this.self().TAB_BUTTON_HEIGHT,
        alignY: "top",
        backgroundColor: "workbench-view-navbar"
      });
      this.__addTopBarSpacer(topBar);

      this.__workbenchUI.setStudy(study);
      this.__workbenchUI.loadModel(study.getWorkbench());
      const workbenchPanelPage = this.__workbenchPanelPage = this.__createTabPage("@FontAwesome5Solid/object-group", this.tr("Workbench"), this.__workbenchPanel);
      tabViewMain.add(workbenchPanelPage);

      const iframePage = this.__iframePage = this.__createTabPage("@FontAwesome5Solid/desktop", this.tr("Interactive"));
      osparc.utils.Utils.setIdToWidget(iframePage.getChildControl("button"), "iframeTabButton");
      tabViewMain.add(iframePage);

      const loggerView = this.__loggerView = new osparc.widget.logger.LoggerView();
      const loggerPage = this.__loggerPage = this.__createTabPage("@FontAwesome5Solid/file-alt", this.tr("Logger"), loggerView);
      osparc.utils.Utils.setIdToWidget(loggerPage.getChildControl("button"), "loggerTabButton");
      tabViewMain.add(loggerPage);

      this.__addTopBarSpacer(topBar);

      const conversationButton = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        toolTipText: this.tr("Conversations"),
        icon: "@FontAwesome5Solid/comments/16",
        marginRight: 10,
        marginTop: 7,
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
      });
      osparc.study.Conversations.makeButtonBlink(conversationButton);
      conversationButton.addListener("execute", () => osparc.study.Conversations.popUpInWindow(study.serialize()));
      topBar.add(conversationButton);

      const startAppButtonTB = this.__startAppButtonTB = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        label: this.tr("App Mode"),
        toolTipText: this.tr("Start App Mode"),
        icon: osparc.dashboard.CardBase.MODE_APP,
        marginRight: 10,
        marginTop: 7,
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
      });
      startAppButtonTB.addListener("execute", () => study.getUi().setMode("app"));
      topBar.add(startAppButtonTB);

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
      // remove pages
      osparc.utils.Utils.removeAllChildren(tabView);
      // remove spacers
      const topBar = tabView.getChildControl("bar");
      topBar.removeAll();
    },

    __addTopBarSpacer: function(tabViewTopBar) {
      const spacer = new qx.ui.core.Widget().set({
        backgroundColor: "workbench-view-navbar"
      });
      tabViewTopBar.add(spacer, {
        flex: 1
      });
    },

    __createCollapsibleViewSpacer: function() {
      const spacer = new qx.ui.core.Widget().set({
        backgroundColor: "workbench-view-navbar",
        height: this.self().TAB_BUTTON_HEIGHT
      });
      return spacer;
    },

    __connectEvents: function() {
      const studyTreeItem = this.__studyTreeItem;
      const nodesTree = this.__nodesTree;
      const workbenchUI = this.__workbenchUI;

      studyTreeItem.addListener("changeSelectedNode", () => {
        nodesTree.resetSelection();
        this.showPipeline();

        this.getStudy().getUi().setCurrentNodeId(this.getStudy().getUuid());
      });
      nodesTree.addListener("changeSelectedNode", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          this.__populateSecondaryColumn(node);
          this.__openIframeTab(node);
        }
        this.__loggerView.setCurrentNodeId(nodeId);
        this.__workbenchUI.nodeSelected(nodeId);
        this.fireDataEvent("changeSelectedNode", nodeId);

        this.getStudy().getUi().setCurrentNodeId(nodeId);
      });

      if (this.__workbenchUIConnected === null) {
        workbenchUI.addListener("changeSelectedNode", e => {
          // one click
          const nodeId = e.getData();
          if (nodeId) {
            studyTreeItem.resetSelection();
            this.__nodesTree.nodeSelected(nodeId);
            const workbench = this.getStudy().getWorkbench();
            const node = workbench.getNode(nodeId);
            this.__populateSecondaryColumn(node);
            this.__evalIframe(node);
            this.__loggerView.setCurrentNodeId(nodeId);
            this.fireDataEvent("changeSelectedNode", nodeId);

            this.getStudy().getUi().setCurrentNodeId(nodeId);
          } else {
            // empty selection
            this.__studyTreeItem.selectStudyItem();

            this.getStudy().getUi().setCurrentNodeId(this.getStudy().getUuid());
          }
        });
        workbenchUI.addListener("nodeSelected", e => {
          // double click
          const nodeId = e.getData();
          if (nodeId) {
            studyTreeItem.resetSelection();
            this.__nodesTree.nodeSelected(nodeId);
            const workbench = this.getStudy().getWorkbench();
            const node = workbench.getNode(nodeId);
            this.__populateSecondaryColumn(node);
            this.__openIframeTab(node);
            this.__loggerView.setCurrentNodeId(nodeId);

            this.getStudy().getUi().setCurrentNodeId(nodeId);
          }
        }, this);
      }

      nodesTree.addListener("fullscreenNode", e => {
        const nodeId = e.getData();
        if (nodeId) {
          studyTreeItem.resetSelection();
          this.fullscreenNode(nodeId);
          this.getStudy().getUi().setCurrentNodeId(nodeId);
        }
      }, this);
      nodesTree.addListener("removeNode", e => {
        const nodeId = e.getData();
        this.__removeNode(nodeId);
      }, this);

      if (this.__workbenchUIConnected === null) {
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
        workbenchUI.addListener("requestOpenLogger", e => {
          const nodeId = e.getData();
          this.__loggerView.filterByNode(nodeId);
          this.__openLoggerTab();
        }, this);
      }

      const workbench = this.getStudy().getWorkbench();
      workbench.addListener("pipelineChanged", this.__workbenchChanged, this);

      workbench.addListener("showInLogger", e => {
        const data = e.getData();
        const nodeId = data.nodeId;
        const msg = data.msg;
        const logLevel = ("level" in data) ? data["level"] : "INFO";
        this.logsToLogger(nodeId, [msg], logLevel);
      }, this);

      workbench.addListener("fileRequested", () => {
        if (this.getStudy().getUi().getMode() === "workbench") {
          const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
          tabViewLeftPanel.setSelection([this.__storagePage]);
        }
      }, this);

      this.__workbenchUIConnected = true;
    },

    logsToLogger: function(nodeId, logs, logLevel) {
      // the node logger is mainly used in App Mode
      const nodeLogger = this.__getNodeLogger(nodeId);
      switch (logLevel) {
        case "DEBUG":
          this.__loggerView.debugs(nodeId, logs);
          if (nodeLogger) {
            nodeLogger.debugs(nodeId, logs);
          }
          break;
        case "WARNING":
          this.__loggerView.warns(nodeId, logs);
          if (nodeLogger) {
            nodeLogger.warns(nodeId, logs);
          }
          break;
        case "ERROR":
          this.__loggerView.errors(nodeId, logs);
          if (nodeLogger) {
            nodeLogger.errors(nodeId, logs);
          }
          break;
        default:
          this.__loggerView.infos(nodeId, logs);
          if (nodeLogger) {
            nodeLogger.infos(nodeId, logs);
          }
          break;
      }
    },

    getStartStopButtons: function() {
      return this.__workbenchPanel.getToolbar().getChildControl("start-stop-btns");
    },

    getSelectedNodeIDs: function() {
      if (this.__workbenchPanel.getMainView() === this.__workbenchUI) {
        return this.__workbenchUI.getSelectedNodeIDs();
      }
      return [this.__currentNodeId];
    },

    nodeSelected: function(nodeId) {
      if (!this.isPropertyInitialized("study")) {
        return;
      }
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
        this.__populateSecondaryColumn(node);
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

    __openLoggerTab: function() {
      const tabViewMain = this.getChildControl("main-panel-tabs");
      tabViewMain.setSelection([this.__loggerPage]);
    },

    __applyMaximized: function(maximized) {
      this.getBlocker().setStyles({
        display: maximized ? "none" : "block"
      });

      this.getChildControl("side-panels").setVisibility(maximized ? "excluded" : "visible");

      const tabViewMain = this.getChildControl("main-panel-tabs");
      const mainViewTopBar = tabViewMain.getChildControl("bar");
      mainViewTopBar.setVisibility(maximized ? "excluded" : "visible");
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
            widget.addListener("maximize", () => this.setMaximized(true), this);
            widget.addListener("restore", () => this.setMaximized(false), this);
          }
        });
        node.getIframeHandler().addListener("iframeChanged", () => this.__iFrameChanged(node), this);
        iFrame.addListener("load", () => this.__iFrameChanged(node), this);
        this.__iFrameChanged(node);
      } else {
        // This will keep what comes after at the bottom
        this.__iframePage.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
      }
    },

    __iFrameChanged: function(node) {
      this.__iframePage.removeAll();

      if (node && node.getIFrame()) {
        const loadingPage = node.getLoadingPage();
        const iFrame = node.getIFrame();
        const src = iFrame.getSource();
        const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
        this.__iframePage.add(iFrameView, {
          flex: 1
        });
      }
    },

    __populateSecondaryColumn: function(node) {
      [
        this.__studyOptionsPage,
        this.__fileInfoPage,
        this.__serviceOptionsPage
      ].forEach(page => {
        page.removeAll();
        page.getChildControl("button").exclude();
      });

      const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
      tabViewLeftPanel.setSelection([this.__nodesPage]);

      if (node instanceof osparc.data.model.Study) {
        this.__populateSecondaryColumnStudy(node);
      } else if (node && node.isFilePicker()) {
        this.__populateSecondaryColumnFilePicker(node);
      } else if (node && node.isParameter()) {
        this.__populateSecondaryColumnParameter(node);
      } else if (node) {
        this.__populateSecondaryColumnNode(node);
      }

      if (node instanceof osparc.data.model.Node) {
        node.getStudy().bind("pipelineRunning", this.__serviceOptionsPage, "enabled", {
          converter: pipelineRunning => !pipelineRunning
        });
      }
    },

    __populateSecondaryColumnStudy: function(study) {
      this.__studyOptionsPage.getChildControl("button").show();
      this.getChildControl("side-panel-right-tabs").setSelection([this.__studyOptionsPage]);

      const scrollView = new qx.ui.container.Scroll();
      const secondaryColumnStudyContent = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
        backgroundColor: "transparent"
      });
      scrollView.add(secondaryColumnStudyContent);
      this.__studyOptionsPage.add(scrollView, {
        flex: 1
      });

      secondaryColumnStudyContent.add(new osparc.info.StudyMedium(study), {
        flex: 1
      });

      secondaryColumnStudyContent.add(this.__getSlideshowSection());

      secondaryColumnStudyContent.add(this.__getAnnotationsSection());

      const snaps = this.__getSnapshotsSection();
      snaps.exclude();
      const isVCDisabled = osparc.utils.DisabledPlugins.isVersionControlDisabled();
      snaps.setVisibility(isVCDisabled ? "excluded" : "visible");
      secondaryColumnStudyContent.add(snaps);

      const iters = this.__getIterationsSection();
      const isMMDisabled = osparc.utils.DisabledPlugins.isMetaModelingDisabled();
      snaps.setVisibility(isMMDisabled ? "excluded" : "visible");
      secondaryColumnStudyContent.add(iters);
    },

    __getSlideshowSection: function() {
      const slideshowSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      slideshowSection.add(new qx.ui.basic.Label(this.tr("App Mode")).set({
        font: "text-14"
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
        icon: osparc.dashboard.CardBase.MODE_APP,
        toolTipText: this.tr("Start App Mode"),
        height: buttonsHeight
      });
      startAppBtn.addListener("execute", () => this.getStudy().getUi().setMode("app"), this);
      slideshowButtons.add(startAppBtn);

      this.__evalSlidesButtons();

      return slideshowSection;
    },

    __evalSlidesButtons: function() {
      const study = this.getStudy();
      if (study && this.__editSlidesButton) {
        const canIWrite = osparc.data.model.Study.canIWrite(study.getAccessRights());
        this.__editSlidesButton.setEnabled(canIWrite);
        const canStart = study.hasSlideshow() || study.getWorkbench().isPipelineLinear();
        this.__startAppButton.setEnabled(canStart);
        this.__startAppButtonTB.setVisibility(canStart ? "visible" : "excluded");
      }
    },

    __getAnnotationsSection: function() {
      const annotationsSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      annotationsSection.add(new qx.ui.basic.Label(this.tr("Add to Workbench")).set({
        font: "text-14"
      }));

      const annotationsButtons = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 5));
      annotationsSection.add(annotationsButtons);

      const buttonsHeight = 28;

      const addConversationBtn = new qx.ui.form.Button().set({
        label: this.tr("Conversation"),
        icon: "@FontAwesome5Solid/comment/14",
        height: buttonsHeight
      });
      addConversationBtn.addListener("execute", () => this.__workbenchUI.startConversation(), this);
      annotationsButtons.add(addConversationBtn);

      const addNoteBtn = new qx.ui.form.Button().set({
        label: this.tr("Note"),
        icon: "@FontAwesome5Solid/sticky-note/14",
        height: buttonsHeight
      });
      addNoteBtn.addListener("execute", () => this.__workbenchUI.startAnnotationsNote(), this);
      annotationsButtons.add(addNoteBtn);

      const addRectBtn = new qx.ui.form.Button().set({
        label: this.tr("Box"),
        icon: "@FontAwesome5Regular/square/14",
        height: buttonsHeight
      });
      addRectBtn.addListener("execute", () => this.__workbenchUI.startAnnotationsRect(), this);
      annotationsButtons.add(addRectBtn);

      const addTextBtn = new qx.ui.form.Button().set({
        label: this.tr("Text"),
        icon: "@FontAwesome5Solid/font/14",
        height: buttonsHeight
      });
      addTextBtn.addListener("execute", () => this.__workbenchUI.startAnnotationsText(), this);
      annotationsButtons.add(addTextBtn);

      return annotationsSection;
    },

    __getSnapshotsSection: function() {
      const snapshotSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      snapshotSection.add(new qx.ui.basic.Label(this.tr("Checkpoints")).set({
        font: "text-14"
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
        font: "text-14"
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

    __populateSecondaryColumnFilePicker: function(filePicker) {
      const fpView = new osparc.file.FilePicker(filePicker, "workbench");
      if (osparc.file.FilePicker.hasOutputAssigned(filePicker.getOutputs())) {
        this.__fileInfoPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__fileInfoPage]);

        this.__fileInfoPage.add(fpView, {
          flex: 1
        });
      } else {
        // empty File Picker
        const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
        tabViewLeftPanel.setSelection([this.__storagePage]);

        this.__serviceOptionsPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__serviceOptionsPage]);

        this.__serviceOptionsPage.add(fpView, {
          flex: 1
        });
      }
      [
        "itemReset",
        "itemSelected",
        "fileUploaded"
      ].forEach(ev => fpView.addListener(ev, () => this.__populateSecondaryColumn(filePicker)));
    },

    __populateSecondaryColumnParameter: function(parameter) {
      this.__serviceOptionsPage.getChildControl("button").show();
      this.getChildControl("side-panel-right-tabs").setSelection([this.__serviceOptionsPage]);

      const view = new osparc.node.ParameterEditor(parameter);
      view.buildForm(false);
      this.__serviceOptionsPage.add(view, {
        flex: 1
      });
    },

    __populateSecondaryColumnNode: async function(node) {
      this.__serviceOptionsPage.getChildControl("button").show();
      this.getChildControl("side-panel-right-tabs").setSelection([this.__serviceOptionsPage]);

      const spacing = 8;
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        separator: "separator-vertical",
        spacing: spacing*2
      }));

      this.__serviceOptionsPage.bind("width", vBox, "width");

      // HEADER
      const nodeMetadata = node.getMetadata();
      const version = osparc.store.Services.getVersionDisplay(nodeMetadata["key"], nodeMetadata["version"]);
      const header = new qx.ui.basic.Label(`${nodeMetadata["name"]} ${version}`).set({
        paddingLeft: 5
      });
      vBox.add(header);

      // INPUTS FORM
      if (node.hasPropsForm()) {
        const inputsForm = node.getPropsForm();
        const inputs = new osparc.desktop.PanelView(this.tr("Inputs"), inputsForm);
        inputs._innerContainer.set({
          margin: spacing
        });
        vBox.add(inputs);
      }

      // OUTPUTS
      const outputsBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(spacing));
      const outputsForm = node.getOutputsForm();
      if (node.hasOutputs() && outputsForm) {
        outputsForm.set({
          offerProbes: true
        });
        outputsBox.add(outputsForm);
      }

      const nodeFilesBtn = new qx.ui.form.Button(this.tr("Service data"), "@FontAwesome5Solid/folder-open/14").set({
        allowGrowX: false,
        allowGrowY: false
      });
      osparc.utils.Utils.setIdToWidget(nodeFilesBtn, "nodeFilesBtn");
      nodeFilesBtn.addListener("execute", () => this.self().openNodeDataManager(node));
      outputsBox.add(nodeFilesBtn);

      const outputs = new osparc.desktop.PanelView(this.tr("Outputs"), outputsBox);
      outputs._innerContainer.set({
        margin: spacing
      });
      vBox.add(outputs);

      // NODE OPTIONS
      const nodeOptions = this.__getNodeOptionsPage(node);
      if (nodeOptions) {
        const options = new osparc.desktop.PanelView(this.tr("Options"), nodeOptions);
        options._innerContainer.set({
          margin: spacing
        });
        nodeOptions.bind("visibility", options, "visibility");
        vBox.add(options);
      }

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(vBox);
      this.__serviceOptionsPage.add(scrollContainer, {
        flex: 1
      });
    },

    __getNodeOptionsPage: function(node) {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return null;
      }

      const nodeOptions = new osparc.widget.NodeOptions(node);
      return nodeOptions;
    },

    getLogger: function() {
      return this.__loggerView;
    },

    __getNodeLogger: function(nodeId) {
      const nodes = this.getStudy().getWorkbench().getNodes();
      for (const node of Object.values(nodes)) {
        if (nodeId === node.getNodeId()) {
          return node.getLogger();
        }
      }
      return null;
    },

    __attachEventHandlers: function() {
      const maximizeIframeCb = msg => this.setMaximized(msg.getData());
      this.addListener("appear", () => qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this), this);
      this.addListener("disappear", () => qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this), this);
    },

    __nodeAdded: function(node) {
      this.__workbenchUI.addNode(node);
    },

    __removeNode: function(nodeId) {
      const workbench = this.getStudy().getWorkbench();
      const node = workbench.getNode(nodeId);
      if (node) {
        const avoidConfirmation = node.isFilePicker() && !osparc.file.FilePicker.hasOutputAssigned(node.getOutputs());
        const preferencesSettings = osparc.Preferences.getInstance();
        if (!avoidConfirmation && preferencesSettings.getConfirmDeleteNode()) {
          const msg = this.tr("Are you sure you want to delete the selected node?");
          const win = new osparc.ui.window.Confirmation(msg).set({
            caption: this.tr("Delete Node"),
            confirmText: this.tr("Delete"),
            confirmAction: "delete"
          });
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
      }
    },

    __removeNodes: function(nodeIds) {
      const preferencesSettings = osparc.Preferences.getInstance();
      if (preferencesSettings.getConfirmDeleteNode()) {
        const msg = this.tr("Are you sure you want to delete the selected ") + nodeIds.length + " nodes?";
        const win = new osparc.ui.window.Confirmation(msg).set({
          caption: this.tr("Delete Nodes"),
          confirmText: this.tr("Delete"),
          confirmAction: "delete"
        });
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
      workbench.removeNode(nodeId);
      if ([this.__currentNodeId, null].includes(this.__nodesTree.getCurrentNodeId())) {
        this.nodeSelected(this.getStudy().getUuid());
      }
    },

    __nodeRemoved: function(nodeId, connectedEdgeIds) {
      // remove first the connected edges
      connectedEdgeIds.forEach(edgeId => {
        this.__workbenchUI.clearEdge(edgeId);
      });
      // then remove the node
      this.__workbenchUI.clearNode(nodeId);
    },

    __removeEdge: function(edgeId) {
      const workbench = this.getStudy().getWorkbench();
      const removed = workbench.removeEdge(edgeId);
      if (removed) {
        this.__workbenchUI.clearEdge(edgeId);
      }
    },

    __workbenchChanged: function() {
      this.__nodesTree.populateTree();
      this.__nodesTree.nodeSelected(this.__currentNodeId);
    },

    showPipeline: function() {
      this.__populateSecondaryColumn(this.getStudy());
      this.__evalIframe();
      this.__openWorkbenchTab();
      this.__loggerView.setCurrentNodeId(null);

      this.getStudy().getUi().setCurrentNodeId(this.getStudy().getUuid());
    },

    fullscreenNode: function(nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node && node.isDynamic()) {
        qx.event.Timer.once(() => {
          this.__populateSecondaryColumn(node);
          this.__openIframeTab(node);
          node.getIFrame().maximizeIFrame(true);
        }, this, 10);
      }
      this.__loggerView.setCurrentNodeId(nodeId);
      this.__workbenchUI.nodeSelected(nodeId);
    },

    openFirstNode: function() {
      const validNodes = this.getStudy().getNonFrontendNodes();
      if (validNodes.length === 1 && validNodes[0].isDynamic()) {
        const dynamicNode = validNodes[0];
        this.fullscreenNode(dynamicNode.getNodeId());
        this.getStudy().getUi().setCurrentNodeId(dynamicNode.getNodeId());
      } else {
        this.setMaximized(false);
        this.nodeSelected(this.getStudy().getUuid());
      }
    }
  }
});

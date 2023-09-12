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
    TAB_BUTTON_HEIGHT: 46,

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
    "changeSelectedNode": "qx.event.type.Data",
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event",
    "backToDashboardPressed": "qx.event.type.Event",
    "slidesEdit": "qx.event.type.Event",
    "slidesAppStart": "qx.event.type.Event",
    "annotationRectStart": "qx.event.type.Event",
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
    __nodeOptionsPage: null,
    __workbenchPanel: null,
    __workbenchPanelPage: null,
    __workbenchUI: null,
    __workbenchUIConnected: null,
    __iframePage: null,
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
          control = new osparc.component.widget.CollapsibleViewLight().set({
            minWidth: osparc.component.widget.CollapsibleViewLight.CARET_WIDTH,
            width: Math.min(parseInt(window.innerWidth * 0.16), 240)
          });
          const caretExpandedLayout = control.getChildControl("caret-expanded-layout");
          caretExpandedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          const caretCollapsedLayout = control.getChildControl("caret-collapsed-layout");
          caretCollapsedLayout.addAt(this.__createCollapsibleViewSpacer(), 0);
          control.bind("collapsed", control, "maxWidth", {
            converter: collapsed => collapsed ? osparc.component.widget.CollapsibleViewLight.CARET_WIDTH : null
          });
          control.bind("collapsed", sidePanels, "width", {
            converter: collapsed => this.__getSidePanelsNewWidth(collapsed, sidePanels, control)
          });
          control.addListener("changeCollapsed", e => {
            const collapsed = e.getData();
            const collapsibleViewLeft = this.getChildControl("collapsible-view-right");
            // if both panes are collapsed set the maxWidth of the layout to 2*15
            if (collapsed && collapsibleViewLeft.isCollapsed()) {
              sidePanels.setMaxWidth(2 * osparc.component.widget.CollapsibleViewLight.CARET_WIDTH);
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
            converter: collapsed => collapsed ? osparc.component.widget.CollapsibleViewLight.CARET_WIDTH : null
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
              sidePanels.setMaxWidth(2 * osparc.component.widget.CollapsibleViewLight.CARET_WIDTH);
            } else {
              sidePanels.setMaxWidth(null);
            }
          }, this);
          sidePanels.add(control, 1); // flex 1
          break;
        }
        case "side-panel-left-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: osparc.component.widget.CollapsibleViewLight.CARET_WIDTH + 2, // collapse bar + padding
            contentPaddingRight: 2,
            barPosition: "top"
          });
          const collapsibleViewLeft = this.getChildControl("collapsible-view-left");
          collapsibleViewLeft.setContent(control);
          control.setBackgroundColor("background-main-2");
          collapsibleViewLeft.getChildControl("expand-button").setBackgroundColor("background-main-2");
          collapsibleViewLeft.getChildControl("collapse-button").setBackgroundColor("background-main-2");
          break;
        }
        case "side-panel-right-tabs": {
          control = new qx.ui.tabview.TabView().set({
            contentPadding: osparc.component.widget.CollapsibleViewLight.CARET_WIDTH + 2, // collapse bar + padding
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
      const sidePanelsWidth = sidePanels.getBounds().width;
      if (collapsing) {
        const content = collapsibleView.getChildControl("scroll-content");
        sidePanelsNewWidth = sidePanelsWidth - content.getBounds().width;
      } else if ("precollapseWidth" in collapsibleView) {
        sidePanelsNewWidth = sidePanelsWidth + (collapsibleView.precollapseWidth - osparc.component.widget.CollapsibleViewLight.CARET_WIDTH);
      }
      return sidePanelsNewWidth;
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
      osparc.utils.Utils.removeBorder(tabPageBtn);
      tabPageBtn.bind("value", tabPageBtn, "backgroundColor", {
        converter: val => val ? backgroundColor : "background-main-4"
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
      const primaryColumnBGColor = "background-main-2";
      const study = this.getStudy();

      const tabViewPrimary = this.getChildControl("side-panel-left-tabs");
      this.__removePages(tabViewPrimary);
      tabViewPrimary.setBackgroundColor(primaryColumnBGColor);
      const collapsibleViewLeft = this.getChildControl("collapsible-view-left");
      collapsibleViewLeft.getChildControl("expand-button").setBackgroundColor(primaryColumnBGColor);
      collapsibleViewLeft.getChildControl("collapse-button").setBackgroundColor(primaryColumnBGColor);


      const topBar = tabViewPrimary.getChildControl("bar");
      topBar.set({
        height: this.self().TAB_BUTTON_HEIGHT,
        backgroundColor: "background-main-4",
        paddingLeft: osparc.component.widget.CollapsibleViewLight.CARET_WIDTH
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
        allowGrowY: true,
        minHeight: 5
      });
      nodesTree.setStudy(study);
      homeAndNodesTree.add(nodesTree);

      const addNewNodeBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("New Node"),
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false,
        alignX: "center",
        marginLeft: 14
      });
      addNewNodeBtn.addListener("execute", () => {
        this.__workbenchUI.openServiceCatalog({
          x: 50,
          y: 50
        }, {
          x: 50,
          y: 50
        });
      });
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
        height: this.self().TAB_BUTTON_HEIGHT,
        backgroundColor: "background-main-4",
        paddingLeft: osparc.component.widget.CollapsibleViewLight.CARET_WIDTH
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

      const nodeOptionsPage = this.__nodeOptionsPage = this.__createTabPage("@FontAwesome5Solid/cogs", this.tr("Service Options"));
      nodeOptionsPage.getLayout().setSpacing(20);
      osparc.utils.Utils.setIdToWidget(nodeOptionsPage.getChildControl("button"), "nodeOptionsTabButton");
      nodeOptionsPage.exclude();
      tabViewSecondary.add(nodeOptionsPage);

      this.__addTopBarSpacer(topBar);

      this.__populateSecondPanel();
    },

    __initMainView: function() {
      const study = this.getStudy();

      const tabViewMain = this.getChildControl("main-panel-tabs");
      this.__removePages(tabViewMain);

      const topBar = tabViewMain.getChildControl("bar");
      topBar.set({
        height: this.self().TAB_BUTTON_HEIGHT,
        backgroundColor: "background-main-4"
      });
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

      const startAppButtonTB = this.__startAppButtonTB = new qx.ui.form.Button().set({
        label: this.tr("App Mode"),
        toolTipText: this.tr("Start App Mode"),
        icon: "@FontAwesome5Solid/play/14",
        alignY: "middle",
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS
      });
      startAppButtonTB.addListener("execute", () => this.fireEvent("slidesAppStart"));
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
        backgroundColor: "background-main-4"
      });
      tabViewTopBar.add(spacer, {
        flex: 1
      });
    },

    __createCollapsibleViewSpacer: function() {
      const spacer = new qx.ui.core.Widget().set({
        backgroundColor: "background-main-4",
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
        this.__populateSecondPanel(this.getStudy());
        this.__evalIframe();
        this.__openWorkbenchTab();
        this.__loggerView.setCurrentNodeId(null);
      });
      nodesTree.addListener("changeSelectedNode", e => {
        studyTreeItem.resetSelection();
        const nodeId = e.getData();
        const workbench = this.getStudy().getWorkbench();
        const node = workbench.getNode(nodeId);
        if (node) {
          this.__populateSecondPanel(node);
          this.__openIframeTab(node);
        }
        this.__loggerView.setCurrentNodeId(nodeId);
        this.__workbenchUI.nodeSelected(nodeId);
        this.fireDataEvent("changeSelectedNode", nodeId);
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
            this.__populateSecondPanel(node);
            this.__evalIframe(node);
            this.__loggerView.setCurrentNodeId(nodeId);
            this.fireDataEvent("changeSelectedNode", nodeId);
          } else {
            // empty selection
            this.__studyTreeItem.selectStudyItem();
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
            this.__populateSecondPanel(node);
            this.__openIframeTab(node);
            this.__loggerView.setCurrentNodeId(nodeId);
          }
        }, this);
      }

      nodesTree.addListener("fullscreenNode", e => {
        const nodeId = e.getData();
        if (nodeId) {
          studyTreeItem.resetSelection();
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node) {
            this.__populateSecondPanel(node);
            this.__openIframeTab(node);
            node.getLoadingPage().maximizeIFrame(true);
            node.getIFrame().maximizeIFrame(true);
          }
          this.__loggerView.setCurrentNodeId(nodeId);
          this.__workbenchUI.nodeSelected(nodeId);
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
      }

      const workbench = this.getStudy().getWorkbench();
      workbench.addListener("pipelineChanged", this.__workbenchChanged, this);

      workbench.addListener("showInLogger", e => {
        const data = e.getData();
        const nodeId = data.nodeId;
        const msg = data.msg;
        const logLevel = ("level" in data) ? data["level"] : "INFO";
        switch (logLevel) {
          case "DEBUG":
            this.__loggerView.debug(nodeId, msg);
            break;
          case "WARNING":
            this.__loggerView.warn(nodeId, msg);
            break;
          case "ERROR":
            this.__loggerView.error(nodeId, msg);
            break;
          default:
            this.__loggerView.info(nodeId, msg);
            break;
        }
      }, this);

      workbench.addListener("fileRequested", () => {
        if (this.getStudy().getUi().getMode() === "workbench") {
          const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
          tabViewLeftPanel.setSelection([this.__storagePage]);
        }
      }, this);

      this.__workbenchUIConnected = true;
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
          const logLevelMap = osparc.component.widget.logger.LoggerView.LOG_LEVEL_MAP;
          const logLevel = ("log_level" in data) ? logLevelMap[data["log_level"]] : "INFO";
          switch (logLevel) {
            case "DEBUG":
              this.__loggerView.debugs(nodeId, messages);
              break;
            case "WARNING":
              this.__loggerView.warns(nodeId, messages);
              break;
            case "ERROR":
              this.__loggerView.errors(nodeId, messages);
              break;
            default:
              this.__loggerView.infos(nodeId, messages);
              break;
          }
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
        socket.on(slotName2, jsonString => {
          const data = JSON.parse(jsonString);
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy().getUuid() !== data["project_id"]) {
            // Filtering out logs from other studies
            return;
          }
          const nodeId = data["node_id"];
          const progress = Number.parseFloat(data["progress"]).toFixed(4);
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node) {
            node.getStatus().setProgress(progress);
          } else if (osparc.data.Permissions.getInstance().isTester()) {
            console.log("Ignored ws 'progress' msg", data);
          }
        }, this);
      }

      this.listenToNodeUpdated();

      this.listenToNodeProgress();

      // callback for events
      const slotName3 = "event";
      if (!socket.slotExists(slotName3)) {
        socket.on(slotName3, jsonString => {
          const data = JSON.parse(jsonString);
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy().getUuid() !== data["project_id"]) {
            // Filtering out logs from other studies
            return;
          }
          const action = data["action"];
          if (action == "RELOAD_IFRAME") {
            // TODO: maybe reload iframe in the future
            // for now a message is displayed to the user
            const nodeId = data["node_id"];

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
        socket.on(slotName, jsonString => {
          const data = JSON.parse(jsonString);
          this.getStudy().nodeUpdated(data);
        }, this);
      }
    },

    listenToNodeProgress: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      const slotName = "nodeProgress";
      if (!socket.slotExists(slotName)) {
        socket.on(slotName, jsonString => {
          const data = JSON.parse(jsonString);
          this.getStudy().nodeNodeProgressSequence(data);
        }, this);
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
        this.__outputsPage,
        this.__nodeOptionsPage
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

      this.__studyOptionsPage.add(new osparc.info.StudyMedium(study), {
        flex: 1
      });

      this.__studyOptionsPage.add(this.__getSlideshowSection());

      this.__studyOptionsPage.add(this.__getAnnotationsSection());

      const snaps = this.__getSnapshotsSection();
      snaps.exclude();
      this.__studyOptionsPage.add(snaps);
      osparc.utils.DisabledPlugins.isVersionControlDisabled()
        .then(isDisabled => {
          if (!isDisabled) {
            snaps.show();
          }
        });

      const iters = this.__getIterationsSection();
      iters.exclude();
      this.__studyOptionsPage.add(iters);
      osparc.utils.DisabledPlugins.isMetaModelingDisabled()
        .then(isDisabled => {
          if (!isDisabled) {
            iters.show();
          }
        });
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
        const canIWrite = osparc.data.model.Study.canIWrite(study.getAccessRights());
        this.__editSlidesButton.setEnabled(canIWrite);
        const canStart = study.hasSlideshow() || study.getWorkbench().isPipelineLinear();
        this.__startAppButton.setEnabled(canStart);
        this.__startAppButtonTB.setVisibility(canStart ? "visible" : "hidden");
      }
    },

    __getAnnotationsSection: function() {
      const annotationsSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      annotationsSection.add(new qx.ui.basic.Label(this.tr("Annotations")).set({
        font: "text-14"
      }));

      const annotationsButtons = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      annotationsSection.add(annotationsButtons);

      const buttonsHeight = 28;
      const addNoteBtn = new qx.ui.form.Button().set({
        label: this.tr("Note"),
        icon: "@FontAwesome5Solid/plus/14",
        height: buttonsHeight
      });
      addNoteBtn.addListener("execute", () => this.__workbenchUI.startAnnotationsNote(), this);
      annotationsButtons.add(addNoteBtn);

      const addRectBtn = new qx.ui.form.Button().set({
        label: this.tr("Rectangle"),
        icon: "@FontAwesome5Solid/plus/14",
        height: buttonsHeight
      });
      addRectBtn.addListener("execute", () => this.__workbenchUI.startAnnotationsRect(), this);
      annotationsButtons.add(addRectBtn);

      const addTextBtn = new qx.ui.form.Button().set({
        label: this.tr("Text"),
        icon: "@FontAwesome5Solid/plus/14",
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

    __populateSecondPanelFilePicker: function(filePicker) {
      const fpView = new osparc.file.FilePicker(filePicker, "workbench");
      if (osparc.file.FilePicker.hasOutputAssigned(filePicker.getOutputs())) {
        this.__infoPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__infoPage]);

        this.__infoPage.add(fpView, {
          flex: 1
        });
      } else {
        // empty File Picker
        const tabViewLeftPanel = this.getChildControl("side-panel-left-tabs");
        tabViewLeftPanel.setSelection([this.__storagePage]);

        this.__settingsPage.getChildControl("button").show();
        this.getChildControl("side-panel-right-tabs").setSelection([this.__settingsPage]);

        this.__settingsPage.add(fpView, {
          flex: 1
        });
      }
      [
        "itemReset",
        "itemSelected",
        "fileUploaded"
      ].forEach(ev => fpView.addListener(ev, () => this.__populateSecondPanel(filePicker)));
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

    __populateSecondPanelNode: async function(node) {
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
        const nodeOutputs = new osparc.component.widget.NodeOutputs(node, node.getMetaData().outputs).set({
          offerProbes: true
        });
        this.__outputsPage.add(nodeOutputs);
      }

      const outputFilesBtn = new qx.ui.form.Button(this.tr("Service data"), "@FontAwesome5Solid/folder-open/14").set({
        allowGrowX: false
      });
      osparc.utils.Utils.setIdToWidget(outputFilesBtn, "nodeOutputFilesBtn");
      outputFilesBtn.addListener("execute", () => osparc.component.node.BaseNodeView.openNodeDataManager(node));
      this.__outputsPage.add(outputFilesBtn);

      const showPage = await this.__populateNodeOptionsPage(node);
      // if it's deprecated or retired show the LifeCycleView right away
      if (showPage && node.hasOutputs() && node.isDynamic() && (node.isDeprecated() || node.isRetired())) {
        this.getChildControl("side-panel-right-tabs").setSelection([this.__nodeOptionsPage]);
      }
    },

    __populateNodeOptionsPage: async function(node) {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return false;
      }

      let showPage = false;
      let showStartStopButton = false;

      const sections = [];

      // Life Cycle
      if (
        node.isDynamic() &&
        (node.isUpdatable() || node.isDeprecated() || node.isRetired())
      ) {
        const lifeCycleView = new osparc.component.node.LifeCycleView(node);
        node.addListener("versionChanged", () => this.__populateSecondPanel(node));
        sections.push(lifeCycleView);
        showPage = true;
        showStartStopButton = true;
      }

      // Boot Options
      if (node.hasBootModes()) {
        const bootOptionsView = new osparc.component.node.BootOptionsView(node);
        node.addListener("bootModeChanged", () => this.__populateSecondPanel(node));
        sections.push(bootOptionsView);
        showPage = true;
        showStartStopButton = true;
      }

      // Update Resource Limits
      if (
        await osparc.data.Permissions.getInstance().checkCanDo("override_services_specifications") &&
        (node.isComputational() || node.isDynamic())
      ) {
        const updateResourceLimitsView = new osparc.component.node.UpdateResourceLimitsView(node);
        node.addListener("limitsChanged", () => this.__populateSecondPanel(node));
        sections.push(updateResourceLimitsView);
        showPage = true;
        showStartStopButton |= node.isDynamic();
      }

      this.__nodeOptionsPage.removeAll();
      if (showPage) {
        const introLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
        const title = new qx.ui.basic.Label(this.tr("Service Options")).set({
          font: "text-14"
        });
        introLayout.add(title);

        if (showStartStopButton) {
          // Only available to dynamic services
          const instructions = new qx.ui.basic.Label(this.tr("To procceed with the following actions, the service needs to be Stopped.")).set({
            font: "text-13",
            rich: true,
            wrap: true
          });
          introLayout.add(instructions);

          const startStopButton = new osparc.component.node.StartStopButton();
          startStopButton.setNode(node);
          introLayout.add(startStopButton);
        }

        this.__nodeOptionsPage.add(introLayout);
        sections.forEach(section => this.__nodeOptionsPage.add(section));
        this.__nodeOptionsPage.getChildControl("button").setVisibility(showPage ? "visible" : "excluded");
      }

      return showPage;
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
      const workbench = this.getStudy().getWorkbench();
      const node = workbench.getNode(nodeId);
      if (node) {
        const avoidConfirmation = node.isFilePicker() && !osparc.file.FilePicker.hasOutputAssigned(node.getOutputs());
        const preferencesSettings = osparc.Preferences.getInstance();
        if (!avoidConfirmation && preferencesSettings.getConfirmDeleteNode()) {
          const msg = this.tr("Are you sure you want to delete the selected node?");
          const win = new osparc.ui.window.Confirmation(msg).set({
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

    __doRemoveNode: async function(nodeId) {
      const workbench = this.getStudy().getWorkbench();
      const connectedEdges = workbench.getConnectedEdges(nodeId);
      const removed = await workbench.removeNode(nodeId);
      if (removed) {
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
      const removed = workbench.removeEdge(edgeId);
      if (removed) {
        this.__workbenchUI.clearEdge(edgeId);
      }
    },

    __workbenchChanged: function() {
      this.__nodesTree.populateTree();
      this.__nodesTree.nodeSelected(this.__currentNodeId);
    },

    openFirstNode: function() {
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
      this.__maximizeIframe(false);
      this.nodeSelected(this.getStudy().getUuid());
    }
  }
});

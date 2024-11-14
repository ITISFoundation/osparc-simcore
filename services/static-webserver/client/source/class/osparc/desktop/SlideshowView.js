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

qx.Class.define("osparc.desktop.SlideshowView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    const slideshowToolbar = this.__slideshowToolbar = new osparc.desktop.SlideshowToolbar().set({
      backgroundColor: "workbench-view-navbar"
    });

    const collapseWithUserMenu = this.__collapseWithUserMenu = new osparc.desktop.CollapseWithUserMenu();
    [
      "backToDashboardPressed",
      "collapseNavBar",
      "expandNavBar"
    ].forEach(signalName => collapseWithUserMenu.addListener(signalName, () => this.fireEvent(signalName)), this);
    // eslint-disable-next-line no-underscore-dangle
    slideshowToolbar._add(collapseWithUserMenu);

    slideshowToolbar.addListener("saveSlideshow", () => {
      if (this.__currentNodeId) {
        const slideshow = this.getStudy().getUi().getSlideshow();
        if (!Object.keys(slideshow).includes(this.__currentNodeId)) {
          this.__openFirstNode();
        }
      } else {
        this.__openFirstNode();
      }
    }, this);
    slideshowToolbar.addListener("nodeSelectionRequested", e => {
      const nodeId = e.getData();
      this.__moveToNode(nodeId);
    }, this);
    slideshowToolbar.addListener("addServiceBetween", e => {
      const {
        leftNodeId,
        rightNodeId
      } = e.getData();
      this.__requestServiceBetween(leftNodeId, rightNodeId);
    }, this);
    slideshowToolbar.addListener("removeNode", e => {
      const nodeId = e.getData();
      this.__removeNode(nodeId);
    }, this);
    slideshowToolbar.addListener("showNode", e => {
      const {
        nodeId,
        desiredPos
      } = e.getData();
      this.__showNode(nodeId, desiredPos);
    }, this);
    slideshowToolbar.addListener("hideNode", e => {
      const nodeId = e.getData();
      this.__hideNode(nodeId);
    }, this);
    slideshowToolbar.addListener("slidesStop", () => this.fireEvent("slidesStop"), this);
    this._add(slideshowToolbar);

    const mainView = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
      alignX: "center"
    }));
    this._add(mainView, {
      flex: 1
    });

    const prevNextButtons = this.__prevNextButtons = new osparc.navigation.PrevNextButtons();
    prevNextButtons.addListener("nodeSelected", e => {
      const nodeId = e.getData();
      this.__moveToNode(nodeId);
    }, this);
    prevNextButtons.addListener("runPressed", e => {
      const nodeId = e.getData();
      this.fireDataEvent("startPartialPipeline", [nodeId]);
    }, this);
    const prevButton = this.__prevButton = prevNextButtons.getPreviousButton().set({
      alignX: "right",
      alignY: "middle"
    });
    const nextButton = this.__nextButton = prevNextButtons.getNextButton().set({
      alignX: "left",
      alignY: "middle"
    });
    const runButton = this.__runButton = prevNextButtons.getRunButton().set({
      alignX: "left",
      alignY: "middle"
    });
    mainView.add(prevButton);
    mainView.add(nextButton);
    mainView.add(runButton);
  },

  events: {
    "slidesStop": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Data",
    "stopPipeline": "qx.event.type.Event",
    "backToDashboardPressed": "qx.event.type.Event",
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    },

    maximized: {
      check: "Boolean",
      init: null,
      nullable: false,
      apply: "__applyMaximized",
      event: "changeMaximized"
    },

    pageContext: {
      check: ["guided", "app"],
      nullable: false,
      init: "guided"
    }
  },

  statics: {
    CARD_MARGIN: 6
  },

  members: {
    __slideshowToolbar: null,
    __collapseWithUserMenu: null,
    __mainView: null,
    __prevNextButtons: null,
    __prevButton: null,
    __nextButton: null,
    __runButton: null,
    __nodeView: null,
    __currentNodeId: null,

    getSelectedNodeIDs: function() {
      return [this.__currentNodeId];
    },

    getCollapseWithUserMenu: function() {
      return this.__collapseWithUserMenu;
    },

    __isNodeReady: function(lastCurrentNodeId) {
      const node = this.getStudy().getWorkbench().getNode(lastCurrentNodeId);
      return osparc.data.model.NodeStatus.isCompNodeReady(node);
    },

    __getNeedToRunDependencies: function(node) {
      const dependencies = node.getStatus().getDependencies() || [];
      const wb = this.getStudy().getWorkbench();
      const upstreamNodeIds = wb.getUpstreamCompNodes(node, false);
      upstreamNodeIds.forEach(upstreamNodeId => {
        const upstreamNode = wb.getNode(upstreamNodeId);
        if (osparc.data.model.NodeStatus.doesCompNodeNeedRun(upstreamNode)) {
          dependencies.push(upstreamNodeId);
        }
      });
      return dependencies;
    },

    __getNotReadyDependencies: function(node) {
      const dependencies = node.getStatus().getDependencies() || [];
      const wb = this.getStudy().getWorkbench();
      const upstreamNodeIds = wb.getUpstreamCompNodes(node, true);
      upstreamNodeIds.forEach(upstreamNodeId => {
        if (!this.__isNodeReady(upstreamNodeId)) {
          dependencies.push(upstreamNodeId);
        }
      });
      return dependencies;
    },

    __getUpstreamCompDependencies: function(node) {
      const dependencies = node.getStatus().getDependencies() || [];
      const wb = this.getStudy().getWorkbench();
      const upstreamNodeIds = wb.getUpstreamCompNodes(node, true);
      upstreamNodeIds.forEach(upstreamNodeId => {
        if (wb.getNode(upstreamNodeId).isComputational()) {
          dependencies.push(upstreamNodeId);
        }
      });
      return dependencies;
    },

    __moveToNode: function(nodeId) {
      this.nodeSelected(nodeId);
    },

    __connectMaximizeEvents: function(node) {
      if (node.isDynamic()) {
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
        }
      }
    },

    __styleView: function(node, view) {
      view.getContentElement().setStyles({
        "border-radius": "12px"
      });
      view.set({
        maxWidth: node.isDynamic() ? null : 800,
        margin: this.self().CARD_MARGIN
      });
      if (node.isParameter()) {
        view.bind("backgroundColor", view.getChildControl("frame"), "backgroundColor");
        view.set({
          backgroundColor: "navigation_bar_background_color",
          padding: 6
        });
      } else {
        view.getMainView().set({
          backgroundColor: "navigation_bar_background_color",
          padding: 6,
          paddingTop: 0,
          paddingBottom: 0
        });
      }
      if (node.isFilePicker()) {
        view.getMainView().set({
          backgroundColor: "navigation_bar_background_color"
        });
      }
    },

    __getNodeView: function(node) {
      let view;
      if (node.isParameter()) {
        view = osparc.node.slideshow.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
        const renderer = new osparc.node.ParameterEditor(node);
        renderer.buildForm(false);
        view.add(renderer);
      } else {
        if (node.isFilePicker()) {
          view = new osparc.node.slideshow.FilePickerView();
          view.getOutputsButton().hide();
        } else {
          view = new osparc.node.slideshow.NodeView();
        }
        view.setNode(node);
        if (node.isDynamic()) {
          view.getSettingsLayout().setVisibility(this.getPageContext() === "app" ? "excluded" : "visible");
        }
      }
      this.__connectMaximizeEvents(node);
      this.__styleView(node, view);
      return view;
    },

    nodeSelected: function(nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node) {
        const lastCurrentNodeId = this.__currentNodeId;

        // If the user is moving forward do some run checks:
        const studyUI = this.getStudy().getUi();
        const movingForward = studyUI.getSlideshow().isMovingForward(lastCurrentNodeId, nodeId);
        if (movingForward) {
          // check if lastCurrentNodeId has to be run
          if (!this.__isNodeReady(lastCurrentNodeId)) {
            this.fireDataEvent("startPartialPipeline", [lastCurrentNodeId]);
            return;
          }
        }

        this.__currentNodeId = nodeId;
        this.getStudy().getUi().setCurrentNodeId(nodeId);

        // build layout
        const view = this.__getNodeView(node);

        this.__prevNextButtons.setNode(node);

        if (view) {
          if (this.__nodeView && this.__nodeView.getInstructionsWindow()) {
            this.__nodeView.getInstructionsWindow().close();
          }
          if (this.__nodeView && this.__mainView.getChildren().includes(this.__nodeView)) {
            this.__mainView.remove(this.__nodeView);
          }
          this.__mainView.addAt(view, 1, {
            flex: 1
          });
          this.__nodeView = view;

          // Automatically request to start the dynamic service when the user gets to this step
          if (node.isDynamic()) {
            node.requestStartNode();
          }
        }

        const upstreamDependencies = this.__getUpstreamCompDependencies(node);
        this.__nodeView.setUpstreamDependencies(upstreamDependencies);
        if (!this.__nodeView.hasListener("startPartialPipeline")) {
          this.__nodeView.addListener("startPartialPipeline", e => this.fireDataEvent("startPartialPipeline", e.getData()));
        }
        if (!this.__nodeView.hasListener("stopPipeline")) {
          this.__nodeView.addListener("stopPipeline", () => this.fireEvent("stopPipeline"));
        }

        const notReadyDependencies = this.__getNotReadyDependencies(node);
        if (notReadyDependencies && notReadyDependencies.length) {
          this.__nodeView.showPreparingInputs();
        }

        // check if upstream has to be run
        const notStartedDependencies = this.__getNeedToRunDependencies(node);
        if (notStartedDependencies && notStartedDependencies.length) {
          this.fireDataEvent("startPartialPipeline", notStartedDependencies);
        }
      } else if (this.__nodeView) {
        this.__mainView.remove(this.__nodeView);
      }
      this.getStudy().getUi().setCurrentNodeId(nodeId);
    },

    __applyMaximized: function(maximized) {
      [
        this.__slideshowToolbar,
        this.__prevButton,
        this.__nextButton,
        this.__runButton,
        this.__nodeView.getHeaderLayout(),
        this.__nodeView.getLoggerPanel()
      ].forEach(widget => widget.setVisibility(maximized ? "excluded" : "visible"));

      this.__nodeView.set({
        margin: maximized ? 0 : this.self().CARD_MARGIN
      });
    },

    startSlides: function() {
      // If the study is not initialized this will fail
      if (!this.isPropertyInitialized("study")) {
        console.error("study is not initialized");
        return;
      }
      const study = this.getStudy();
      const slideshow = study.getUi().getSlideshow();
      if (slideshow.isEmpty()) {
        const sortedPipeline = study.getWorkbench().getPipelineLinearSorted();
        if (sortedPipeline) {
          sortedPipeline.forEach((nodeId, i) => {
            slideshow.insertNode(nodeId, i);
          });
        }
      }
      this.setPageContext("app");
      this.__slideshowToolbar.populateButtons(true);
      const currentNodeId = this.getStudy().getUi().getCurrentNodeId();
      const isValid = slideshow.getPosition(currentNodeId) !== -1;
      if (isValid && currentNodeId) {
        this.__moveToNode(currentNodeId);
      } else {
        this.__openFirstNode();
      }

      if (this.__nodeView) {
        const node = this.__nodeView.getNode();
        if (node.isDynamic()) {
          // Start it. First wait 2 seconds because the function depends on the node's state which might not be available yet
          setTimeout(() => node.requestStartNode(), 2000);
        }
      }
    },

    _applyStudy: function(study) {
      if (study) {
        this.__slideshowToolbar.setStudy(study);
        this.__prevNextButtons.setStudy(study);
      }
    },

    __openFirstNode: function() {
      const study = this.getStudy();
      if (study) {
        const nodes = study.getUi().getSlideshow().getSortedNodes();
        if (nodes.length) {
          this.__moveToNode(nodes[0].nodeId);
        } else {
          this.__moveToNode(null);
        }
      }
    },

    __requestServiceBetween: function(leftNodeId, rightNodeId) {
      const srvCat = new osparc.workbench.ServiceCatalog();
      srvCat.setContext(leftNodeId, rightNodeId);
      srvCat.addListener("addService", e => {
        const data = e.getData();
        const service = data.service;
        this.__addServiceBetween(service, leftNodeId, rightNodeId);
      }, this);
      srvCat.center();
      srvCat.open();
    },

    __addServiceBetween: async function(service, leftNodeId, rightNodeId) {
      const workbench = this.getStudy().getWorkbench();

      const node = await workbench.addServiceBetween(service, leftNodeId, rightNodeId);
      if (node === null) {
        return;
      }

      // add to the slideshow
      const slideshow = this.getStudy().getUi().getSlideshow();
      slideshow.addNodeToSlideshow(node, leftNodeId, rightNodeId);

      this.__slideshowToolbar.populateButtons();
    },

    __removeNode: function(nodeId) {
      const workbench = this.getStudy().getWorkbench();
      const node = workbench.getNode(nodeId);
      if (!node) {
        return;
      }
      if (nodeId === this.__currentNodeId) {
        return;
      }

      const preferencesSettings = osparc.Preferences.getInstance();
      if (preferencesSettings.getConfirmDeleteNode()) {
        const msg = this.tr("Are you sure you want to delete node?");
        const win = new osparc.ui.window.Confirmation(msg).set({
          caption: this.tr("Delete"),
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
    },

    __doRemoveNode: function(nodeId) {
      // connect next node to previous node
      let leftNodeId = null;
      let rightNodeId = null;
      const nodes = this.getStudy().getUi().getSlideshow()
        .getSortedNodes();
      const idx = nodes.findIndex(node2 => node2.nodeId === nodeId);
      if (idx < 0) {
        return;
      }
      if (idx !== 0) {
        // not first
        leftNodeId = nodes[idx-1].nodeId;
      }
      if (idx < nodes.length-1) {
        // not last
        rightNodeId = nodes[idx+1].nodeId;
      }

      // bypass connection
      const workbench = this.getStudy().getWorkbench();
      workbench.createEdge(null, leftNodeId, rightNodeId, true);

      // remove node
      workbench.removeNode(nodeId);

      this.__slideshowToolbar.populateButtons();
    },

    __showNode: function(nodeId, desiredPos) {
      this.getStudy().getUi().getSlideshow()
        .insertNode(nodeId, desiredPos);

      this.__slideshowToolbar.populateButtons();
    },

    __hideNode: function(nodeId) {
      this.getStudy().getUi().getSlideshow()
        .removeNode(nodeId);

      this.__slideshowToolbar.populateButtons();
    }
  }
});

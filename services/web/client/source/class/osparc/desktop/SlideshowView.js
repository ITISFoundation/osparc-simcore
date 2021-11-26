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
      backgroundColor: "contrasted-background+"
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
    slideshowToolbar.addListener("nodeSelected", e => {
      const nodeId = e.getData();
      this.nodeSelected(nodeId);
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
      this.nodeSelected(nodeId);
    }, this);
    const prevButton = this.__prevButton = prevNextButtons.getPreviousButton().set({
      alignX: "right",
      alignY: "middle"
    });
    const nextButton = this.__nextButton = prevNextButtons.getNextButton().set({
      alignX: "left",
      alignY: "middle"
    });
    mainView.add(prevButton);
    mainView.add(nextButton);
  },

  events: {
    "slidesStop": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Data",
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

    pageContext: {
      check: ["guided", "app"],
      nullable: false,
      init: "guided"
    }
  },

  members: {
    __slideshowToolbar: null,
    __collapseWithUserMenu: null,
    __mainView: null,
    __prevNextButtons: null,
    __prevButton: null,
    __nextButton: null,
    __nodeView: null,
    __currentNodeId: null,

    getSelectedNodeIDs: function() {
      return [this.__currentNodeId];
    },

    getCollapseWithUserMenu: function() {
      return this.__collapseWithUserMenu;
    },

    __isLastCurrentNodeReady: function(lastCurrentNodeId) {
      const node = this.getStudy().getWorkbench().getNode(lastCurrentNodeId);
      if (node && node.isComputational()) {
        // run if last run was not succesful
        let needsRun = node.getStatus().getRunning() !== "SUCCESS";
        // or inputs changed
        needsRun = needsRun || node.getStatus().getOutput() === "out-of-date";
        if (needsRun) {
          this.fireDataEvent("startPartialPipeline", [lastCurrentNodeId]);
        }
        return !needsRun;
      }
      return true;
    },

    __isSelectedNodeReady: function(node, lastCurrentNodeId) {
      const dependencies = node.getStatus().getDependencies();
      if (dependencies && dependencies.length) {
        const msg = this.tr("Do you want to run the required steps?");
        const win = new osparc.ui.window.Confirmation(msg);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.fireDataEvent("startPartialPipeline", dependencies);
          }
          // bring the user back to the old node or to the first dependency
          if (lastCurrentNodeId === this.__currentNodeId) {
            this.nodeSelected(dependencies[0]);
          } else {
            this.nodeSelected(lastCurrentNodeId);
          }
        }, this);
        return false;
      }
      return true;
    },

    nodeSelected: function(nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node) {
        const lastCurrentNodeId = this.__currentNodeId;
        this.__currentNodeId = nodeId;
        this.getStudy().getUi().setCurrentNodeId(nodeId);

        let view;
        if (node.isParameter()) {
          view = osparc.component.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
          view.bind("backgroundColor", view.getChildControl("frame"), "backgroundColor");
          const renderer = new osparc.component.node.ParameterEditor(node);
          renderer.buildForm(false);
          view.add(renderer);
        } else {
          if (node.isFilePicker()) {
            view = new osparc.component.node.FilePickerNodeView();
          } else {
            view = new osparc.component.node.NodeView();
          }
          view.setNode(node);
          if (this.getPageContext() === "app") {
            if (node.isComputational()) {
              view.getHeaderLayout().show();
              view.getSettingsLayout().show();
            } else if (node.isDynamic()) {
              view.getHeaderLayout().show();
              view.getSettingsLayout().exclude();
            } else {
              view.getHeaderLayout().exclude();
              view.getSettingsLayout().exclude();
            }
          }
        }

        if (node.isDynamic()) {
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
          }
        } else {
          view.set({
            maxWidth: 800
          });
        }
        view.getContentElement().setStyles({
          "border-radius": "12px"
        });
        view.set({
          backgroundColor: "background-main-lighter+",
          padding: 10,
          margin: 6
        });

        // If the current node is moving forward do some run checks:
        const studyUI = this.getStudy().getUi();
        let doChecks = false;
        if (lastCurrentNodeId && nodeId) {
          const sortedNodeIds = studyUI.getSlideshow().getSortedNodeIds();
          doChecks = sortedNodeIds.indexOf(lastCurrentNodeId) < sortedNodeIds.indexOf(nodeId);
        }

        if (doChecks) {
          // check if lastCurrentNodeId has to be run
          if (!this.__isLastCurrentNodeReady(lastCurrentNodeId)) {
            this.__currentNodeId = lastCurrentNodeId;
            studyUI.setCurrentNodeId(lastCurrentNodeId);
            return;
          }

          // check if upstream has to be run
          if (!this.__isSelectedNodeReady(node, lastCurrentNodeId)) {
            this.__currentNodeId = lastCurrentNodeId;
            studyUI.setCurrentNodeId(lastCurrentNodeId);
            return;
          }
        }

        if (view) {
          if (this.__nodeView && this.__mainView.getChildren().includes(this.__nodeView)) {
            this.__mainView.remove(this.__nodeView);
          }
          this.__mainView.addAt(view, 1, {
            flex: 1
          });
          this.__nodeView = view;
        }
      } else if (this.__nodeView) {
        this.__mainView.remove(this.__nodeView);
      }
      this.getStudy().getUi().setCurrentNodeId(nodeId);
    },

    __maximizeIframe: function(maximize) {
      [
        this.__slideshowToolbar,
        this.__prevButton,
        this.__nextButton,
        this.__nodeView.getHeaderLayout(),
        this.__nodeView.getLoggerPanel()
      ].forEach(widget => widget.setVisibility(maximize ? "excluded" : "visible"));

      this.__nodeView.set({
        padding: maximize ? 0 : 10,
        margin: maximize ? 0 : 6
      });
    },

    startSlides: function(context = "guided") {
      const study = this.getStudy();
      const slideshow = study.getUi().getSlideshow();
      if (context === "app" && slideshow.isEmpty()) {
        const sortedPipeline = study.getWorkbench().getPipelineLinearSorted();
        if (sortedPipeline) {
          sortedPipeline.forEach((nodeId, i) => {
            slideshow.insertNode(nodeId, i);
          });
        }
      }
      const slideshowData = slideshow.getData();
      this.setPageContext(context);
      this.__slideshowToolbar.populateButtons(true);
      const currentNodeId = this.getStudy().getUi().getCurrentNodeId();
      const isValid = Object.keys(slideshowData).indexOf(currentNodeId) !== -1;
      if (isValid && currentNodeId) {
        this.nodeSelected(currentNodeId);
      } else {
        this.__openFirstNode();
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
          this.nodeSelected(nodes[0].nodeId);
        } else {
          this.nodeSelected(null);
        }
      }
    },

    __requestServiceBetween: function(leftNodeId, rightNodeId) {
      const srvCat = new osparc.component.workbench.ServiceCatalog();
      srvCat.setContext(leftNodeId, rightNodeId);
      srvCat.addListener("addService", e => {
        const data = e.getData();
        const service = data.service;
        this.__addServiceBetween(service, leftNodeId, rightNodeId);
      }, this);
      srvCat.center();
      srvCat.open();
    },

    __addServiceBetween: function(service, leftNodeId, rightNodeId) {
      const workbench = this.getStudy().getWorkbench();

      const node = workbench.addServiceBetween(service, leftNodeId, rightNodeId);
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
      workbench.createEdge(null, leftNodeId, rightNodeId);

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

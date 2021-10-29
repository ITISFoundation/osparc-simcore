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
    this.base(arguments, "horizontal");

    this._setLayout(new qx.ui.layout.VBox());

    const slideshowToolbar = this.__slideshowToolbar = new osparc.desktop.SlideshowToolbar().set({
      backgroundColor: "contrasted-background+"
    });
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
  },

  events: {
    "slidesStop": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Data"
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
    __currentNodeId: null,
    __slideshowToolbar: null,
    __lastView: null,

    getStartStopButtons: function() {
      return this.__slideshowToolbar.getStartStopButtons();
    },

    getSelectedNodeIDs: function() {
      return [this.__currentNodeId];
    },

    __isNodeReady: function(node, oldCurrentNodeId) {
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
          if (oldCurrentNodeId === this.__currentNodeId) {
            this.nodeSelected(dependencies[0]);
          } else {
            this.nodeSelected(oldCurrentNodeId);
          }
        }, this);
        return false;
      }
      return true;
    },

    nodeSelected: function(nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node) {
        const oldCurrentNodeId = this.__currentNodeId;
        this.__currentNodeId = nodeId;
        this.getStudy().getUi().setCurrentNodeId(nodeId);

        let view;
        if (node.isParameter()) {
          view = osparc.component.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
          const renderer = new osparc.component.node.ParameterEditor(node);
          renderer.buildForm();
          renderer.set({
            appearance: "settings-groupbox",
            maxWidth: 800,
            alignX: "center"
          });
          view.add(renderer);
        } else {
          if (node.isContainer()) {
            view = new osparc.component.node.GroupNodeView();
          } else if (node.isFilePicker()) {
            view = new osparc.component.node.FilePickerNodeView();
          } else {
            view = new osparc.component.node.NodeView();
          }
          view.setNode(node);
          view.populateLayout();
          view.getInputsView().exclude();
          view.getOutputsView().exclude();
          if (this.getPageContext() === "app" && !node.isComputational()) {
            view.getHeaderLayout().exclude();
            view.getSettingsLayout().exclude();
          }
        }

        if (view) {
          if (this.__lastView && this._getChildren().includes(this.__lastView)) {
            this._remove(this.__lastView);
          }
          this._add(view, {
            flex: 1
          });
          this.__lastView = view;
        }
        // check if upstream has to be run
        if (!this.__isNodeReady(node, oldCurrentNodeId)) {
          return;
        }
      } else if (this.__lastView) {
        this._remove(this.__lastView);
      }
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      this.getStartStopButtons().nodeSelectionChanged([nodeId]);
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

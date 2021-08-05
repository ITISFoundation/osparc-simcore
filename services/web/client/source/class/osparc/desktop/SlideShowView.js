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

qx.Class.define("osparc.desktop.SlideShowView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, "horizontal");

    this._setLayout(new qx.ui.layout.VBox());

    const slideShowToolbar = this.__slideShowToolbar = new osparc.desktop.SlideShowToolbar();
    slideShowToolbar.addListener("nodeSelected", e => {
      const nodeId = e.getData();
      this.nodeSelected(nodeId);
    }, this);
    slideShowToolbar.addListener("addServiceBetween", e => {
      const {
        leftNodeId,
        rightNodeId
      } = e.getData();
      this.__requestServiceBetween(leftNodeId, rightNodeId);
    }, this);
    slideShowToolbar.addListener("removeService", e => {
      const nodeId = e.getData();
      this.__removeService(nodeId);
    }, this);
    this._add(slideShowToolbar);
  },

  events: {
    "startPartialPipeline": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    },

    pageContext: {
      check: ["slideshow", "fullSlideshow"],
      nullable: false,
      init: "slideshow"
    }
  },

  members: {
    __currentNodeId: null,
    __slideShowToolbar: null,
    __lastView: null,

    getStartStopButtons: function() {
      return this.__slideShowToolbar.getStartStopButtons();
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
        if (node.isContainer()) {
          view = new osparc.component.node.GroupNodeView();
        } else if (node.isFilePicker()) {
          view = new osparc.component.node.FilePickerNodeView();
        } else {
          view = new osparc.component.node.NodeView();
        }
        if (view) {
          if (this.__lastView) {
            this._remove(this.__lastView);
          }
          view.setNode(node);
          view.populateLayout();
          view.getInputsView().exclude();
          view.getOutputsView().exclude();
          if (this.getPageContext() === "fullSlideshow" && !node.isComputational()) {
            view.getHeaderLayout().exclude();
            view.getSettingsLayout().exclude();
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
      }
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      this.getStartStopButtons().nodeSelectionChanged([nodeId]);
    },

    startSlides: function(context = "slideshow") {
      this.setPageContext(context);
      this.__slideShowToolbar.populateButtons();
      const currentNodeId = this.getStudy().getUi().getCurrentNodeId();
      const study = this.getStudy();
      const slideShow = study.getUi().getSlideshow().getData();
      const isValid = Object.keys(slideShow).indexOf(currentNodeId) !== -1;
      if (isValid && currentNodeId) {
        this.nodeSelected(currentNodeId);
      } else {
        this.__openFirstNode();
      }
    },

    _applyStudy: function(study) {
      if (study) {
        this.__slideShowToolbar.setStudy(study);
      }
    },

    __openFirstNode: function() {
      const study = this.getStudy();
      if (study) {
        const nodes = study.getUi().getSlideshow().getSortedNodes();
        if (nodes.length) {
          this.nodeSelected(nodes[0].nodeId);
        }
      }
    },

    __requestServiceBetween: function(leftNodeId, rightNodeId) {
      const srvCat = new osparc.component.workbench.ServiceCatalog();
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

      // create node
      const node = workbench.createNode(service.getKey(), service.getVersion());
      if (!node) {
        return;
      }
      node.setPosition({
        x: 0,
        y: 0
      });

      // break previous connection
      if (rightNodeId) {
        const connectedEdges = workbench.getConnectedEdges(rightNodeId);
        connectedEdges.forEach(connectedEdgeId => {
          workbench.removeEdge(connectedEdgeId);
        });
      }

      // create connections
      if (leftNodeId) {
        workbench.createEdge(null, leftNodeId, node.getNodeId());
      }
      if (rightNodeId) {
        workbench.createEdge(null, node.getNodeId(), rightNodeId);
      }

      // add to the slideshow
      const slideshow = this.getStudy().getUi().getSlideshow();
      const nodeId = node.getNodeId();
      if (leftNodeId) {
        let leftPos = slideshow.getPosition(leftNodeId);
        slideshow.insertNode(nodeId, leftPos+1);
      } else if (rightNodeId) {
        const rightPos = slideshow.getPosition(rightNodeId);
        slideshow.insertNode(nodeId, rightPos);
      } else {
        slideshow.insertNode(nodeId, 0);
      }
      this.__slideShowToolbar.populateButtons();
    },

    __removeService: function(nodeId) {
      const workbench = this.getStudy().getWorkbench();

      const node = workbench.getNode(nodeId);
      if (!node) {
        return;
      }

      // connect next node to previous node
      let leftNodeId = null;
      let rightNodeId = null;
      const nodes = this.getStudy().getUi().getSlideshow()
        .getSortedNodes();
      const idx = nodes.findIndex(nodeId);
      if (idx < 0) {
        return;
      }
      if (idx !== 0) {
        // not first
        leftNodeId = nodes[idx-1];
      }
      if (idx < nodes.length) {
        // not last
        rightNodeId = nodes[idx+1];
      }
      workbench.createEdge(null, leftNodeId, rightNodeId);

      // remove node
      workbench.removeNode(nodeId);
    }
  }
});

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
    this._add(slideShowToolbar);
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
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

    nodeSelected: function(nodeId) {
      this.__currentNodeId = nodeId;
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node) {
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
          this._add(view, {
            flex: 1
          });
          this.__lastView = view;
        }
      }
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      this.getStartStopButtons().nodeSelectionChanged([nodeId]);
    },

    startSlides: function() {
      const currentNodeId = this.getStudy().getUi().getCurrentNodeId();
      const study = this.getStudy();
      const slideShow = study.getUi().getSlideshow();
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
        const nodes = osparc.data.model.StudyUI.getSortedNodes(study);
        if (nodes.length) {
          this.nodeSelected(nodes[0].nodeId);
        }
      }
    }
  }
});

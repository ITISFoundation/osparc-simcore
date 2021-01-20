/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.navigation.PrevNextButtons", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, "horizontal");

    this._setLayout(new qx.ui.layout.VBox());
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    }
  },

  statics: {
    getSortedNodes: function(study) {
      const slideShow = study.getUi().getSlideshow();
      const nodes = [];
      for (let nodeId in slideShow) {
        const node = slideShow[nodeId];
        nodes.push({
          ...node,
          nodeId
        });
      }
      nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
      return nodes;
    }
  },

  members: {
    __controlsBar: null,
    __prvsBtn: null,
    __nextBtn: null,
    __currentNodeId: null,

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
          view.setNode(node);
          view.populateLayout();
          view.getInputsView().exclude();
          view.getOutputsView().exclude();
          this.__showInMainView(view);
          this.__syncButtons();
        }
      }
      this.getStudy().getUi().setCurrentNodeId(nodeId);
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
        this.__initViews();
      }
    },

    __initViews: function() {
      this._removeAll();
      this.__createControlsBar();
    },

    __createControlsBar: function() {
      const controlsBar = this.__controlsBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        minHeight: 40,
        padding: 5
      });

      controlsBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const prvsBtn = this.__prvsBtn = new qx.ui.form.Button(this.tr("Previous")).set({
        allowGrowX: false
      });
      prvsBtn.addListener("execute", () => {
        this.__previous();
      }, this);
      controlsBar.add(prvsBtn);

      const nextBtn = this.__nextBtn = new qx.ui.form.Button(this.tr("Next")).set({
        allowGrowX: false
      });
      nextBtn.addListener("execute", () => {
        this.__next();
      }, this);
      controlsBar.add(nextBtn);

      this._add(controlsBar);
    },

    __showInMainView: function(nodeView) {
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        if (children[i] !== this.__controlsBar) {
          this._removeAt(i);
        }
      }
      this._addAt(nodeView, 0, {
        flex: 1
      });
    },

    __syncButtons: function() {
      const study = this.getStudy();
      if (study) {
        const nodes = this.self().getSortedNodes(study);
        if (nodes.length && nodes[0].nodeId === this.__currentNodeId) {
          this.__prvsBtn.setEnabled(false);
        } else {
          this.__prvsBtn.setEnabled(true);
        }
        if (nodes.length && nodes[nodes.length-1].nodeId === this.__currentNodeId) {
          this.__nextBtn.setEnabled(false);
        } else {
          this.__nextBtn.setEnabled(true);
        }
      }
    },

    __openFirstNode: function() {
      const study = this.getStudy();
      if (study) {
        const nodes = this.self().getSortedNodes(study);
        if (nodes.length) {
          this.nodeSelected(nodes[0].nodeId);
        }
      }
    },

    __next: function() {
      const study = this.getStudy();
      if (study) {
        const nodes = this.self().getSortedNodes(study);
        const idx = nodes.findIndex(node => node.nodeId === this.__currentNodeId);
        if (idx > -1 && idx+1 < nodes.length) {
          this.nodeSelected(nodes[idx+1].nodeId);
        }
      }
    },

    __previous: function() {
      const study = this.getStudy();
      if (study) {
        const nodes = this.self().getSortedNodes(study);
        const idx = nodes.findIndex(node => node.nodeId === this.__currentNodeId);
        if (idx > -1 && idx-1 > -1) {
          this.nodeSelected(nodes[idx-1].nodeId);
        }
      }
    }
  }
});

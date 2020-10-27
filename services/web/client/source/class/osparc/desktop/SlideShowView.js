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

qx.Class.define("osparc.desktop.SlideShowView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, "horizontal");

    this._setLayout(new qx.ui.layout.VBox());
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: false
    }
  },

  members: {
    __nodeView: null,
    __controlsBar: null,
    __prvsBtn: null,
    __nextBtn: null,
    __currentNodeId: null,

    initViews: function() {
      this.__initViews();

      this.__showFirstNode();
    },

    __showFirstNode: function() {
      const study = this.getStudy();
      if (study) {
        const slideShow = study.getUi().getSlideshow();
        const nodes = [];
        for (let nodeId in slideShow) {
          const node = slideShow[nodeId];
          nodes.push({
            ...node,
            nodeId
          });
        }
        if (nodes.length) {
          nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
          this.nodeSelected(nodes[0].nodeId);
        }
      }
    },

    nodeSelected: function(nodeId) {
      this.__currentNodeId = nodeId;
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node) {
        if (node.isFilePicker()) {
          const nodeView = new osparc.component.node.FilePickerNodeView(node);
          nodeView.populateLayout();
          nodeView.getInputsView().exclude();
          nodeView.getOutputsView().exclude();
          this.__showInMainView(nodeView);
        } else {
          this.__nodeView.setNode(node);
          this.__nodeView.populateLayout();
          this.__nodeView.getInputsView().exclude();
          this.__nodeView.getOutputsView().exclude();
          this.__showInMainView(this.__nodeView);
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
        this.__showFirstNode();
      }
    },

    __initViews: function() {
      this._removeAll();
      this.__createNodeView();
      this.__createControlsBar();
    },

    __createNodeView: function() {
      const nodeView = this.__nodeView = new osparc.component.node.NodeView();
      this.__showInMainView(nodeView);
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

    __next: function() {
      const study = this.getStudy();
      if (study) {
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

        const idx = nodes.findIndex(node => node.nodeId === this.__currentNodeId);
        if (idx > -1 && idx+1 < nodes.length) {
          this.nodeSelected(nodes[idx+1].nodeId);
        }
      }
    },

    __previous: function() {
      const study = this.getStudy();
      if (study) {
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

        const idx = nodes.findIndex(node => node.nodeId === this.__currentNodeId);
        if (idx > -1 && idx-1 > -1) {
          this.nodeSelected(nodes[idx-1].nodeId);
        }
      }
    }
  }
});

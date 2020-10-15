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
        nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
        this.nodeSelected(nodes[0].nodeId);
      }
    },

    nodeSelected: function(nodeId) {
      this.__currentNodeId = nodeId;
      this.getStudy().getUi().setCurrentNodeId(nodeId);

      const node = this.getStudy().getWorkbench().getNode(nodeId);
      if (node) {
        this.__nodeView.setNode(node);
        this.__nodeView.populateLayout();
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
      const nodeView = this.__nodeView = new osparc.component.node.NodeView();
      this._add(nodeView, {
        flex: 1
      });

      const controlsBar = this.__controlsBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        padding: 5
      });

      controlsBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const prvsBtn = this.__prvsBtn = new qx.ui.form.Button(this.tr("Previuos")).set({
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

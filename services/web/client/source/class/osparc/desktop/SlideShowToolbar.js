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

qx.Class.define("osparc.desktop.SlideShowToolbar", {
  extend: osparc.desktop.Toolbar,

  members: {
    __prevNextBtns: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "prev-next-btns": {
          control = new osparc.navigation.PrevNextButtons();
          control.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    // overriden
    _buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");
      this.__prevNextBtns = this.getChildControl("prev-next-btns");

      this._add(new qx.ui.core.Spacer(20));

      this._startStopBtns = this.getChildControl("start-stop-btns");
    },

    // overriden
    _populateGuidedNodesLayout: function() {
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
        const nodeIds = [];
        nodes.forEach(node => {
          nodeIds.push(node.nodeId);
        });

        this._navNodes.populateButtons(nodeIds, "arrow");
        this.__prevNextBtns.populateButtons(nodeIds);
      }
    }
  }
});

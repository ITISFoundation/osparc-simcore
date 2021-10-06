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

qx.Class.define("osparc.desktop.WorkbenchToolbar", {
  extend: osparc.desktop.Toolbar,

  construct: function() {
    this.base(arguments);

    this.__attachEventHandlers();
  },

  members: {
    __navNodes: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumb-navigation": {
          const breadcrumbNavigation = this.__navNodes = new osparc.navigation.BreadcrumbsWorkbench();
          breadcrumbNavigation.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
          control = new qx.ui.container.Scroll();
          control.add(breadcrumbNavigation);
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    // overriden
    _buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");

      this._add(new qx.ui.core.Spacer(20));

      const startStopBtns = this._startStopBtns = this.getChildControl("start-stop-btns");
      startStopBtns.exclude();
    },

    // overriden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const nodeIds = study.getWorkbench().getPathIds(study.getUi().getCurrentNodeId());
        this.__navNodes.populateButtons(nodeIds);
      }
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeWorkbenchSelection", e => {
        const selectedNodes = e.getData();
        const selectedNodeIds = [];
        selectedNodes.forEach(selectedNode => {
          selectedNodeIds.push(selectedNode.getNodeId());
        });
        this.getStartStopButtons().nodeSelectionChanged(selectedNodeIds);
      }, this);
    }
  }
});

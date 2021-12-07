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

  events: {
    "startPipeline": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __navNodes: null,
    __startStopBtns: null,

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
        case "start-stop-btns": {
          control = new osparc.desktop.StartStopButtons();
          [
            "startPipeline",
            "startPartialPipeline",
            "stopPipeline"
          ].forEach(signalName => {
            control.addListener(signalName, () => {
              this.fireEvent(signalName);
            }, this);
          });
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");

      const startStopBtns = this.__startStopBtns = this.getChildControl("start-stop-btns");
      startStopBtns.exclude();
    },

    // overridden
    _applyStudy: function(study) {
      this.base(arguments, study);

      if (study) {
        this.__startStopBtns.setStudy(study);
      }
    },

    // overridden
    _populateNodesNavigationLayout: function() {
      const study = this.getStudy();
      if (study) {
        const nodeIds = study.getWorkbench().getPathIds(study.getUi().getCurrentNodeId());
        this.__navNodes.populateButtons(nodeIds);
      }
    },

    getStartStopButtons: function() {
      return this.__startStopBtns;
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

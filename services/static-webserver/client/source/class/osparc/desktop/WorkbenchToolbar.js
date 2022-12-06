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

  events: {
    "zoomIn": "qx.event.type.Event",
    "zoomOut": "qx.event.type.Event",
    "zoomReset": "qx.event.type.Event"
  },

  members: {
    __navNodes: null,
    __startStopBtns: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumbs-navigation": {
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
        case "start-stop-btns":
          control = new osparc.desktop.StartStopButtons();
          this._add(control);
          break;
        case "zoom-btns": {
          control = new osparc.desktop.ZoomButtons();
          [
            "zoomIn",
            "zoomOut",
            "zoomReset"
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
      this._createChildControl("breadcrumbs-navigation");

      const startStopBtns = this.__startStopBtns = this.getChildControl("start-stop-btns");
      startStopBtns.exclude();

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this._createChildControl("zoom-btns");
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
    }
  }
});

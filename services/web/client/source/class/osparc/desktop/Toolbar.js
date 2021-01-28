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

qx.Class.define("osparc.desktop.Toolbar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    }));
    this.setAppearance("sidepanel");

    this.set({
      height: 46
    });

    this._buildLayout();
  },

  events: {
    "nodeSelected": "qx.event.type.Data",
    "startPipeline": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      nullable: false
    }
  },

  members: {
    _navNodes: null,
    _startStopBtns: null,

    getStartStopButtons: function() {
      return this._startStopBtns;
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumb-navigation": {
          control = new qx.ui.container.Scroll();
          const breadcrumbNavigation = this._navNodes = new osparc.navigation.BreadcrumbNavigation();
          breadcrumbNavigation.addListener("nodeSelected", e => {
            this.fireDataEvent("nodeSelected", e.getData());
          }, this);
          control.add(breadcrumbNavigation);
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "start-stop-btns": {
          control = new osparc.desktop.StartStopButtons();
          control.addListener("startPipeline", () => {
            this.fireEvent("startPipeline");
          }, this);
          control.addListener("startPartialPipeline", () => {
            this.fireEvent("startPartialPipeline");
          }, this);
          control.addListener("stopPipeline", () => {
            this.fireEvent("stopPipeline");
          }, this);
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyStudy: function(study) {
      if (study) {
        study.getUi().addListener("changeCurrentNodeId", () => {
          this._populateNodesNavigationLayout();
        });
        this._startStopBtns.setVisibility(study.isReadOnly() ? "excluded" : "visible");

        this._populateNodesNavigationLayout();
      }
    },

    _buildLayout: function() {
      throw new Error("Abstract method called!");
    },

    _populateNodesNavigationLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});

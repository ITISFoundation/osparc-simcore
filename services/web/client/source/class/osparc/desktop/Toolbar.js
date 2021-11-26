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
      paddingLeft: 6,
      paddingRight: 6,
      height: 46
    });

    this._buildLayout();
  },

  events: {
    "nodeSelected": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    }
  },

  members: {
    _buildLayout: function() {
      throw new Error("Abstract method called!");
    },

    _applyStudy: function(study) {
      if (study) {
        this._populateNodesNavigationLayout();
        study.getUi().addListener("changeCurrentNodeId", () => this._populateNodesNavigationLayout(), this);
      }
    },

    _populateNodesNavigationLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});

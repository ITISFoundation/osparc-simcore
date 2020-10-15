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
    initViews: function() {
      this.__initViews();
    },

    nodeSelected: function(nodeId) {
      console.log(nodeId);
    },

    startSlides: function() {
      console.log("startSlides");
    },

    stopSlides: function() {
      console.log("stopSlides");
    },

    __initViews: function() {
      const label = new qx.ui.basic.Label("Hey");
      this._add(label, {
        flex: 1
      });
    }
  }
});

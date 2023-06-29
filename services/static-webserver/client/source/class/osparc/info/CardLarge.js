/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.CardLarge", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this.set({
      minHeight: 350,
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(15));
  },

  events: {
    "openAccessRights": "qx.event.type.Event",
    "openClassifiers": "qx.event.type.Event",
    "openQuality": "qx.event.type.Event",
    "openTags": "qx.event.type.Event"
  },

  properties: {
    openOptions: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  statics: {
    WIDTH: 600,
    HEIGHT: 700,
    PADDING: 5,
    EXTRA_INFO_WIDTH: 250,
    THUMBNAIL_MIN_WIDTH: 150,
    THUMBNAIL_MAX_WIDTH: 230
  },

  members: {
    _attachHandlers: function() {
      this.addListenerOnce("appear", () => this._rebuildLayout(), this);
      // OM: Not so sure about this one
      // this.addListener("resize", () => this._rebuildLayout(), this);
    },

    _rebuildLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});

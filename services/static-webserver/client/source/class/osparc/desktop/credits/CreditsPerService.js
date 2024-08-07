/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsPerService", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.initDaysRange();
  },

  properties: {
    daysRange: {
      check: [1, 7, 30],
      nullable: false,
      init: 1,
      apply: "__populateList"
    }
  },

  members: {
    __populateList: function(nDays) {
      this._removeAll();
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.quickStart.SlideBase", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function(title) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      padding: 5
    });

    if (title) {
      const label = osparc.product.quickStart.Utils.createTitle(title);
      this._add(label);
    }

    this._populateCard();
  },

  members: {
    /**
      * @abstract
      */
    _populateCard: function() {
      throw new Error("Abstract method called!");
    }
  }
});

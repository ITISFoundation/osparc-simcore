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

qx.Class.define("osparc.component.tutorial.ti.Dashboard", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__populateCard();
  },

  members: {
    __populateCard: function() {
      this._add(new qx.ui.basic.Label().set({
        value: "Dashboard",
        font: "title-14"
      }));

      this._add(new qx.ui.basic.Label().set({
        value: "asdf",
        font: "text-14"
      }));
    }
  }
});

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

qx.Class.define("osparc.component.tutorial.ti.S4LPostPro", {
  extend: qx.ui.core.Widget,

  construct: function() {
    const title = this.tr("Sim4Life Post Processing");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      this._add(new qx.ui.basic.Label().set({
        value: "qwer",
        font: "text-14"
      }));
    }
  }
});

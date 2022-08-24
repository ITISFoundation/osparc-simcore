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
  extend: osparc.component.tutorial.ti.SlideBase,

  construct: function() {
    const title = this.tr("Dashboard");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      this._add(new qx.ui.basic.Label().set({
        value: "asdf",
        font: "text-14"
      }));
    }
  }
});

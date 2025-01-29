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

qx.Class.define("osparc.auth.LoginPageOsparc", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox();
    this._setLayout(layout);

    const loginPage = new osparc.auth.LoginWithDecorators();
    loginPage.addListener("done", e => this.fireDataEvent("done", e.getData()));
    const container = new qx.ui.container.Scroll();
    container.add(loginPage);
    this._add(container, {
      flex: 1
    });
  },

  events: {
    "done": "qx.event.type.Data",
  },
});

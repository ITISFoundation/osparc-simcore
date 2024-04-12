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

qx.Class.define("osparc.ui.window.TabbedWindow", {
  extend: osparc.ui.window.SingletonWindow,
  type: "abstract",

  construct: function(id, caption) {
    this.base(arguments, id, caption);

    const width = 900;
    const height = 600;
    this.set({
      layout: new qx.ui.layout.Grow(),
      modal: true,
      width,
      height,
      showMaximize: false,
      showMinimize: false,
      resizable: true,
      appearance: "service-window"
    });
  },

  members: {
    _setTabbedView: function(tabbedView) {
      this.add(tabbedView);
    }
  }
});

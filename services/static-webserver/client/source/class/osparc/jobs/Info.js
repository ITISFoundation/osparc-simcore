/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.jobs.Info", {
  extend: qx.ui.core.Widget,

  construct(info) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    const jsonViewer = new osparc.widget.JsonFormatterWidget(info);
    const scroll = new qx.ui.container.Scroll();
    scroll.add(jsonViewer);
    this._add(scroll, {
      flex: 1
    });
  },

  statics: {
    popUpInWindow: function(jobInfo) {
      const title = qx.locale.Manager.tr("Job Info");
      const win = osparc.ui.window.Window.popUpInWindow(jobInfo, title, 600, 400);
      win.open();
      return win;
    }
  },
})

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


qx.Class.define("osparc.jobs.JobsBrowser", {
  extend: qx.ui.core.Widget,

  construct() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.getChildControl("jobs-table");
  },

  statics: {
    popUpInWindow: function(jobsBrowser) {
      if (!jobsBrowser) {
        jobsBrowser = new osparc.jobs.JobsBrowser();
      }
      const title = qx.locale.Manager.tr("Jobs");
      const win = osparc.ui.window.Window.popUpInWindow(jobsBrowser, title, 1100, 500);
      win.open();
      return win;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "jobs-table":
          control = new osparc.jobs.JobsTable();
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },
  }
})

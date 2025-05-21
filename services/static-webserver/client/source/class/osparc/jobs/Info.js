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

    const htmlEmbed = osparc.wrapper.JsonFormatter.getInstance().createDiv();
    this._add(htmlEmbed, {
      flex: 1
    });
    this.addListener("appear", () => {
      osparc.wrapper.JsonFormatter.getInstance().setData(info);
    });

    return;
    const jobInfoViewer = this.getChildControl("job-info-viewer");
    jobInfoViewer.setJson(info);
  },

  statics: {
    popUpInWindow: function(jobInfo) {
      const title = qx.locale.Manager.tr("Job Info");
      const win = osparc.ui.window.Window.popUpInWindow(jobInfo, title, 600, 400);
      win.open();
      return win;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "job-info-viewer": {
          control = new osparc.ui.basic.JsonTreeViewer();
          const container = new qx.ui.container.Scroll();
          container.add(control);
          this._add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },
  }
})

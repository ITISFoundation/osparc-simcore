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

qx.Class.define("osparc.jobs.ActivityCenterWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "runs", this.tr("Activity Center"));

    this.set({
      layout: new qx.ui.layout.VBox(),
      modal: true,
      width: this.self().WIDTH,
      height: this.self().HEIGHT,
      showMaximize: false,
      showMinimize: false,
    });

    this.__buildLayout();
  },

  statics: {
    WIDTH: 1000,
    HEIGHT: 500,

    openWindow: function() {
      const runsWindow = new osparc.jobs.ActivityCenterWindow();
      runsWindow.center();
      runsWindow.open();
      return runsWindow;
    }
  },

  members: {
    __buildLayout: function() {
      const stack = new qx.ui.container.Stack();
      this.add(stack, {
        flex: 1
      });

      const runsBrowser = new osparc.jobs.RunsBrowser();
      const subRunsBrowser = new osparc.jobs.SubRunsBrowser();
      stack.add(runsBrowser);
      stack.add(subRunsBrowser);

      runsBrowser.addListener("runSelected", e => {
        const data = e.getData();
        const project = data["rowData"];
        subRunsBrowser.setProject(project);
        this.getChildControl("title").setValue(this.tr("Tasks"));
        stack.setSelection([subRunsBrowser]);
      });

      subRunsBrowser.addListener("backToRuns", () => {
        runsBrowser.reloadRuns();
        this.getChildControl("title").setValue(this.tr("Activity Center"));
        stack.setSelection([runsBrowser]);
      });

      this.addListener("close", () => {
        runsBrowser.stopInterval();
        subRunsBrowser.stopInterval();
      });
    },
  }
});

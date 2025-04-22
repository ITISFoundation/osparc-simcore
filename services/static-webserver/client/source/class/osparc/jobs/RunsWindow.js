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

qx.Class.define("osparc.jobs.RunsWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "runs", this.tr("Runs and Clusters"));

    this.set({
      layout: new qx.ui.layout.VBox(),
      modal: true,
      width: 1100,
      height: 500,
      showMaximize: false,
      showMinimize: false,
    });

    this.__buildLayout();
  },

  statics: {
    openWindow: function() {
      const runsWindow = new osparc.jobs.RunsWindow();
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

      const runsAndClusters = new osparc.jobs.RunsAndClusters();
      const subRunsBrowser = new osparc.jobs.SubRunsBrowser();
      stack.add(runsAndClusters);
      stack.add(subRunsBrowser);

      runsAndClusters.addListener("runSelected", e => {
        const projectUuid = e.getData();
        subRunsBrowser.setProjectUuid(projectUuid);
        this.getChildControl("title").setValue(this.tr("Runs asdf"));
        stack.setSelection([subRunsBrowser]);
      });

      subRunsBrowser.addListener("backToRuns", () => {
        this.getChildControl("title").setValue(this.tr("Runs and Clusters"));
        stack.setSelection([runsAndClusters]);
      });
    },
  }
});

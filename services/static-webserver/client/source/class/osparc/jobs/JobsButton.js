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

qx.Class.define("osparc.jobs.JobsButton", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      width: 30,
      alignX: "center",
      cursor: "pointer",
      toolTipText: this.tr("Activity Center"),
    });

    this.addListener("tap", () => osparc.jobs.ActivityCenterWindow.openWindow(), this);

    const jobsStore = osparc.store.Jobs.getInstance();
    jobsStore.addListener("changeJobsActive", () => this.__updateJobsButton(), this);
    this.__updateJobsButton();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Solid/tasks/22");

          const logoContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          logoContainer.add(control);

          this._add(logoContainer, {
            height: "100%"
          });
          break;
        }
        case "number":
          control = new qx.ui.basic.Label().set({
            backgroundColor: "background-main-1",
            font: "text-12"
          });
          control.getContentElement().setStyles({
            "border-radius": "4px"
          });
          this._add(control, {
            bottom: 8,
            right: 4
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __updateJobsButton: function() {
      this.getChildControl("icon");
      const number = this.getChildControl("number");

      const jobsStore = osparc.store.Jobs.getInstance();
      const nJobs = jobsStore.getJobsActive().length > osparc.store.Jobs.SERVER_MAX_LIMIT ? (osparc.store.Jobs.SERVER_MAX_LIMIT + "+") : jobsStore.getJobsActive().length;
      number.setValue(nJobs.toString());
    },
  }
});

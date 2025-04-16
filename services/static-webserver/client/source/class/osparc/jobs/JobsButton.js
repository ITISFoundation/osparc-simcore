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
      visibility: "excluded",
      toolTipText: this.tr("Jobs and Clusters"),
    });

    const jobsStore = osparc.store.Jobs.getInstance();
    jobsStore.addListener("changeJobs", e => this.__updateJobsButton(), this);
    this.addListener("tap", () => osparc.jobs.JobsAndClusters.popUpInWindow(), this);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Solid/cog/22");
          osparc.utils.Utils.addClass(control.getContentElement(), "rotateSlow");

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
      const nJobs = jobsStore.getJobs().length;
      number.setValue(nJobs.toString());
      nJobs ? this.show() : this.exclude();
    },
  }
});

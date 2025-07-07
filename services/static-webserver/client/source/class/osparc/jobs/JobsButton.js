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

    osparc.utils.Utils.setIdToWidget(this, "jobsButton");

    this.set({
      width: 30,
      alignX: "center",
      cursor: "pointer",
      toolTipText: this.tr("Activity Center"),
    });

    this.addListener("tap", () => osparc.jobs.ActivityCenterWindow.openWindow(), this);

    this.fetchNJobs();
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
        case "is-active-icon-outline":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/12").set({
            textColor: osparc.navigation.NavigationBar.BG_COLOR,
          });
          this._add(control, {
            bottom: 10,
            right: 2
          });
          break;
        case "is-active-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/8").set({
            textColor: "strong-main",
          });
          this._add(control, {
            bottom: 12,
            right: 4
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    fetchNJobs: function() {
      const jobsStore = osparc.store.Jobs.getInstance();
      jobsStore.fetchJobsLatest()
        .then(jobs => this.__updateJobsButton(jobs.length))
    },

    __updateJobsButton: function(isActive) {
      isActive = true;
      this.getChildControl("icon");
      [
        this.getChildControl("is-active-icon-outline"),
        this.getChildControl("is-active-icon"),
      ].forEach(control => {
        control.set({
          visibility: isActive ? "visible" : "excluded"
        });
      });
    },
  }
});

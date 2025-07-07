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

    this.addListener("tap", () => {
      osparc.jobs.ActivityCenterWindow.openWindow();
      this.__fetchNJobs();
    }, this);

    this.__fetchNJobs();

    const socket = osparc.wrapper.WebSocket.getInstance();
    if (socket.isConnected()) {
      this.__attachSocketListener();
    } else {
      socket.addListener("connect", () => this.__attachSocketListener());
    }
  },

  members: {
    __fetchNJobs: null,

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

    __fetchNJobs: function() {
      const jobsStore = osparc.store.Jobs.getInstance();
      const runningOnly = true;
      const offset = 0;
      const limit = 1;
      const orderBy = undefined; // use default order
      const filters = undefined; // use default filters
      const resolveWResponse = true;
      jobsStore.fetchJobsLatest(runningOnly, offset, limit, orderBy, filters, resolveWResponse)
        .then(resp => this.__updateJobsButton(Boolean(resp["_meta"]["total"])));
    },

    __attachSocketListener: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      socket.on("projectStateUpdated", content => {
        // for now, we can only access the activity of my user, not the whole project...
        if (osparc.study.Utils.amIRunningTheStudy(content)) {
          this.__updateJobsButton(true);
        }
        // ...in the next iteration: listen to main store's "studyStateChanged", which will cover all users
      }, this);
    },

    __updateJobsButton: function(isActive) {
      this.getChildControl("icon");
      [
        this.getChildControl("is-active-icon-outline"),
        this.getChildControl("is-active-icon"),
      ].forEach(control => {
        control.set({
          visibility: isActive ? "visible" : "excluded"
        });
      });

      // Start or restart timer when isActive is true
      if (isActive) {
        this.__startRefreshTimer();
      }
    },

    __startRefreshTimer: function() {
      // Stop existing timer if running
      if (this.__refreshTimer) {
        this.__refreshTimer.stop();
        this.__refreshTimer.dispose();
      }

      this.__refreshTimer = new qx.event.Timer(20000);
      this.__refreshTimer.addListener("interval", () => this.__fetchNJobs(), this);
      this.__refreshTimer.start();
    },
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CurrentUsage", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);

    const store = osparc.store.Store.getInstance();
    store.addListener("changeCurrentStudy", e => this.__studyChanged(e.getData()));
  },

  properties: {
    currentUsage: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCurrentUsage"
    }
  },

  members: {
    __interval: null,

    __studyChanged: function(currentStudy) {
      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        if (currentStudy) {
          this.__startRequesting();
        } else {
          this.__stopRequesting();
        }
      }
    },

    __startRequesting: function() {
      this.__interval = setInterval(() => this.__fetchUsedCredits(), 20000);
      this.__fetchUsedCredits();
    },

    __stopRequesting: function() {
      if (this.__interval) {
        clearInterval(this.__interval);
      }
    },

    __fetchUsedCredits: function() {
      const params = {
        url: {
          offset: 0,
          limit: 10
        }
      };
      osparc.data.Resources.fetch("resourceUsage", "getPage", params)
        .then(data => {
          const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
          const currentTasks = data.filter(d => (d.project_id === currentStudy.getUuid()) && d.service_run_status === "RUNNING");
          let cost = 0;
          currentTasks.forEach(currentTask => {
            if (currentTask["credit_cost"]) {
              cost += currentTask["credit_cost"];
            }
          });
          this.setCurrentUsage(cost);
        });
    }
  }
});

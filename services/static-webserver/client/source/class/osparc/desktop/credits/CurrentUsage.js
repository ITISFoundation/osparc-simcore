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

    this.initUsedCredits();

    const store = osparc.store.Store.getInstance();
    store.addListener("changeCurrentStudy", e => this.__currentStudyChanged(e.getData()));
  },

  properties: {
    usedCredits: {
      check: "Number",
      init: null,
      nullable: true,
      event: "changeUsedCredits"
    }
  },

  members: {
    __currentStudyChanged: function(currentStudy) {
      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        if (currentStudy) {
          const store = osparc.store.Store.getInstance();
          const contextWallet = store.getContextWallet();
          if (contextWallet) {
            this.__fetchUsedCredits();
            contextWallet.addListener("changeCreditsAvailable", () => this.__fetchUsedCredits());
          }
        } else {
          this.setUsedCredits(null);
        }
      }
    },

    __fetchUsedCredits: function() {
      const store = osparc.store.Store.getInstance();
      const currentStudy = store.getCurrentStudy();
      const contextWallet = store.getContextWallet();
      if (currentStudy && contextWallet) {
        const walletId = contextWallet.getWalletId();
        const params = {
          url: {
            walletId,
            offset: 0,
            limit: 10
          }
        };
        osparc.data.Resources.fetch("resourceUsage", "getWithWallet2", params)
          .then(data => {
            const currentTasks = data.filter(d => (d.project_id === currentStudy.getUuid()) && d.service_run_status === "RUNNING");
            let cost = 0;
            currentTasks.forEach(currentTask => {
              if (currentTask["credit_cost"]) {
                cost += parseFloat(currentTask["credit_cost"]);
              }
            });
            this.setUsedCredits(cost);
          });
      }
    }
  }
});

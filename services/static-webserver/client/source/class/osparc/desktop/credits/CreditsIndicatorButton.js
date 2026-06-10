/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsIndicatorButton", {
  extend: osparc.desktop.credits.CreditsImage,

  construct: function() {
    this.base(arguments);

    osparc.utils.Utils.setIdToWidget(this, "creditsIndicatorButton");

    this.getChildControl("image").set({
      width: 24,
      height: 24
    });

    this.addListener("tap", this.__buttonTapped, this);

    qx.event.message.Bus.getInstance().subscribe("creditsUsed", this.__onCreditsUsed, this);
  },

  statics: {
    // Fetches the resource usage of a finished/stopped service and flashes the credits used.
    // The credits are only shown if a CreditsIndicatorButton is mounted (subscribed to the
    // "creditsUsed" message); otherwise the dispatched message is simply ignored.
    // The backend computes the credits only once the service is fully stopped, so when the
    // final (non-RUNNING) usage is not available yet, it retries a few times before giving up.
    flashCreditsUsed: function(walletId, studyId, nodeId, label, retriesLeft = 5) {
      if (!walletId) {
        return;
      }
      if (!osparc.store.StaticInfo.isBillableProduct()) {
        return;
      }
      const params = {
        url: {
          offset: 0,
          limit: 20,
          walletId,
        }
      };
      osparc.data.Resources.fetch("resourceUsage", "getWithWallet", params)
        .then(usageData => {
          const nodeUsage = usageData.find(entry =>
            entry["project_id"] === studyId &&
            entry["node_id"] === nodeId &&
            entry["service_run_status"] !== "RUNNING"
          );
          if (nodeUsage && nodeUsage["credit_cost"]) {
            const cost = Math.abs(nodeUsage["credit_cost"]).toFixed(2);
            const msg = `${label} used ${cost} credits`;
            qx.event.message.Bus.getInstance().dispatchByName("creditsUsed", msg);
          } else if (retriesLeft > 0) {
            setTimeout(() => osparc.desktop.credits.CreditsIndicatorButton.flashCreditsUsed(walletId, studyId, nodeId, label, retriesLeft - 1), 3000);
          }
        });
    },

    // Like flashCreditsUsed, but for a whole study being closed: sums up the credits used by
    // all the given services and flashes a single "<study> used <X> credits" message.
    // Retries until every service has a finalized (non-RUNNING) usage, then sums what is available.
    flashStudyCreditsUsed: function(walletId, studyId, studyName, nodeIds, retriesLeft = 5) {
      if (!walletId || !nodeIds || !nodeIds.length) {
        return;
      }
      const params = {
        url: {
          offset: 0,
          limit: 20,
          walletId,
        }
      };
      osparc.data.Resources.fetch("resourceUsage", "getWithWallet", params)
        .then(usageData => {
          const nodeCosts = nodeIds.map(nodeId => {
            const nodeUsage = usageData.find(entry =>
              entry["project_id"] === studyId &&
              entry["node_id"] === nodeId &&
              entry["service_run_status"] !== "RUNNING" &&
              entry["credit_cost"]
            );
            return nodeUsage ? Math.abs(nodeUsage["credit_cost"]) : null;
          });
          const allFinalized = nodeCosts.every(cost => cost !== null);
          if (!allFinalized && retriesLeft > 0) {
            setTimeout(() => osparc.desktop.credits.CreditsIndicatorButton.flashStudyCreditsUsed(walletId, studyId, studyName, nodeIds, retriesLeft - 1), 3000);
            return;
          }
          const totalCost = nodeCosts.reduce((sum, cost) => sum + (cost || 0), 0);
          if (totalCost > 0) {
            const msg = `${studyName} used ${totalCost.toFixed(2)} credits`;
            qx.event.message.Bus.getInstance().dispatchByName("creditsUsed", msg);
          }
        });
    },
  },

  members: {
    __creditsContainer: null,
    __tapListener: null,

    __onCreditsUsed: function(msg) {
      osparc.desktop.credits.CreditsFlashMessage.getInstance().addMessage(msg.getData(), this);
      const el = this.getChildControl("image").getContentElement().getDomElement();
      osparc.utils.Utils.makeButtonBlinkInOut(el);
    },

    /**
     * Used by the guided tours via "action": "toggle".
     */
    toggle: function() {
      this.__buttonTapped();
    },

    __buttonTapped: function() {
      if (this.__creditsContainer && this.__creditsContainer.isVisible()) {
        this.__hideCreditsContainer();
      } else {
        this.__showCreditsContainer();
      }
    },

    __showCreditsContainer: function() {
      if (!this.__creditsContainer) {
        this.__creditsContainer = new osparc.desktop.credits.CreditsSummary();
        this.__creditsContainer.exclude();
      }

      this.__positionCreditsContainer();

      // Show the container
      this.__creditsContainer.show();

      // Add listeners for taps outside the container to hide it
      document.addEventListener("mousedown", this.__onTapOutsideMouse.bind(this), true);
    },

    __positionCreditsContainer: function() {
      const bounds = osparc.utils.Utils.getBounds(this);
      const bottom = bounds.top + bounds.height;
      const right = bounds.left + bounds.width;
      this.__creditsContainer.setPosition(right, bottom);
    },

    __onTapOutsideMouse: function(event) {
      this.__handleOutsideEvent(event);
    },

    __handleOutsideEvent: function(event) {
      const onContainer = osparc.utils.Utils.isMouseOnElement(this.__creditsContainer, event);
      const onButton = osparc.utils.Utils.isMouseOnElement(this, event);
      if (!onContainer && !onButton) {
        this.__hideCreditsContainer();
      }
    },

    __hideCreditsContainer: function() {
      if (this.__creditsContainer) {
        this.__creditsContainer.exclude();
      }

      // Remove listeners for outside clicks/taps
      document.removeEventListener("mousedown", this.__onTapOutsideMouse.bind(this), true);
    },
  }
});

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
    // Fetches the resource usage of the given (finished/stopped) services and flashes a single
    // message with the summed up credits used (built by `buildMessage`).
    // The credits are only shown if a CreditsIndicatorButton is mounted (subscribed to the
    // "creditsUsed" message); otherwise the dispatched message is simply ignored.
    // The backend computes the credits only once a service is fully stopped, so while some
    // service still has no finalized (non-RUNNING) usage, it retries a few times before giving up.
    __flashCreditsUsed: function(walletId, studyId, nodeIds, buildMessage, retriesLeft = 5) {
      if (!walletId || !nodeIds || !nodeIds.length) {
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
            setTimeout(() => osparc.desktop.credits.CreditsIndicatorButton.__flashCreditsUsed(walletId, studyId, nodeIds, buildMessage, retriesLeft - 1), 3000);
            return;
          }
          const totalCost = nodeCosts.reduce((sum, cost) => sum + (cost || 0), 0);
          if (totalCost > 0) {
            qx.event.message.Bus.getInstance().dispatchByName("creditsUsed", buildMessage(totalCost));
          }
        });
    },

    // Flashes the credits used by a single finished/stopped service.
    flashNodeCreditsUsed: function(walletId, studyId, nodeId, nodeLabel) {
      this.__flashCreditsUsed(walletId, studyId, [nodeId], totalCost => `${nodeLabel} used ${totalCost.toFixed(2)} credits`);
    },

    // Flashes the summed up credits used by all the given services of a study being closed.
    flashStudyCreditsUsed: function(walletId, studyId, studyName, nodeIds) {
      this.__flashCreditsUsed(walletId, studyId, nodeIds, totalCost => `${studyName} used ${totalCost.toFixed(2)} credits`);
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

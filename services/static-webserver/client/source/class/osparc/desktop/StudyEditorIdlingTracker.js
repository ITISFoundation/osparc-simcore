/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.StudyEditorIdlingTracker", {
  extend: qx.core.Object,

  construct: function(studyUuid) {
    this.base(arguments);
    this.__studyUuid = studyUuid;
    this.__resetIdlingTimeBound = this.__resetIdlingTime.bind(this);
  },

  events: {
    "userIdled": "qx.event.type.Event"
  },

  statics: {
    INACTIVITY_REQUEST_PERIOD_S: 5
  },

  members: {
    __resetIdlingTimeBound: null,
    __idlingTime: null,
    __idleInterval: null,
    __idleFlashMessage: null,
    __idleFlashMessageIsShowing: false,
    __idleFlashMessageTimeoutId: null,

    __updateFlashMessage: function(timeoutSec) {
      if (this.__idleFlashMessage === null) {
        this.__idleFlashMessage = osparc.FlashMessenger.logAs(qx.locale.Manager.tr("Are you still there?"), "WARNING", timeoutSec*1000);
      }

      let msg = qx.locale.Manager.tr("Are you still there?") + "<br>";
      msg += `If not, ${osparc.store.StaticInfo.getInstance().getDisplayName()} will try to close the ${osparc.product.Utils.getStudyAlias()} in:`;
      msg += osparc.utils.Utils.formatSeconds(timeoutSec);
      this.__idleFlashMessage.setMessage(msg);
    },

    __removeIdleFlashMessage: function() {
      // removes a flash message if displaying
      if (this.__idleFlashMessageTimeoutId) {
        osparc.utils.WebWorkerScheduler.getInstance().clearInterval(this.__idleFlashMessageTimeoutId);
        this.__idleFlashMessageTimeoutId = null;
        this.__idleFlashMessageIsShowing = false;
      }
      if (this.__idleFlashMessage) {
        osparc.FlashMessenger.getInstance().removeMessage(this.__idleFlashMessage);
        this.__idleFlashMessage = null;
      }
    },

    __displayFlashMessage: function(displayDurationS) {
      this.__idleFlashMessageIsShowing = true;

      const updateFlashMessage = () => {
        if (displayDurationS <= 0) {
          // close and reset popup
          this.__removeIdleFlashMessage();
          this.__userIdled();
          return;
        }

        this.__updateFlashMessage(displayDurationS);
        displayDurationS--;
      };
      this.__idleFlashMessageTimeoutId = osparc.utils.WebWorkerScheduler.getInstance().setInterval(updateFlashMessage, 1000);
    },

    __userIdled: function() {
      this.stop();
      this.fireEvent("userIdled");
    },

    __startTimer: function() {
      const inactivityThresholdT = osparc.Preferences.getInstance().getUserInactivityThreshold();
      if (inactivityThresholdT === 0) {
        // If 0, "Automatic Shutdown of Idle Instances" is disabled
        return;
      }

      const checkFn = () => {
        const flashMessageDurationS = Math.round(inactivityThresholdT * 0.2);
        this.__idlingTime++;

        if (this.__idlingTime >= (inactivityThresholdT-flashMessageDurationS) && !this.__idleFlashMessageIsShowing) {
          const timeSinceInactivityThreshold = this.__idlingTime - inactivityThresholdT;
          if (timeSinceInactivityThreshold % this.self().INACTIVITY_REQUEST_PERIOD_S == 0) {
            // check if backend reports project as inactive
            const params = {
              url: {
                studyId: this.__studyUuid
              }
            };
            osparc.data.Resources.fetch("studies", "getInactivity", params)
              .then(data => {
                if (data["is_inactive"]) {
                  this.__displayFlashMessage(flashMessageDurationS);
                }
              })
              .catch(err => console.error(err));
          }
        }
      };
      this.__idleInterval = osparc.utils.WebWorkerScheduler.getInstance().setInterval(checkFn, 1000);
    },

    __stopTimer: function() {
      if (this.__idleInterval) {
        osparc.utils.WebWorkerScheduler.getInstance().clearInterval(this.__idleInterval);
        this.__idleInterval = null;
      }
    },

    __resetIdlingTime: function() {
      this.__idlingTime = 0;
      this.__removeIdleFlashMessage();
    },

    start: function() {
      this.__resetIdlingTime()
      const cb = this.__resetIdlingTimeBound;
      window.addEventListener("mousemove", cb);
      window.addEventListener("mousedown", cb);
      window.addEventListener("keydown", cb);

      this.__startTimer();
    },

    stop: function() {
      const cb = this.__resetIdlingTimeBound;
      window.removeEventListener("mousemove", cb);
      window.removeEventListener("mousedown", cb);
      window.removeEventListener("keydown", cb);

      this.__removeIdleFlashMessage();
      this.__stopTimer();
    },

    /**
     * Destructor
     */
    destruct: function() {
      this.stop();
    }
  }
});

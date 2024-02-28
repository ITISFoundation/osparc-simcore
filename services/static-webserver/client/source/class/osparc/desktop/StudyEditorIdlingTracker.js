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
    INACTIVITY_REQUEST_PERIOD: 60000
  },

  members: {
    __resetIdlingTimeBound: null,
    __idlingTime: null,
    __idleInterval: null,
    __idleFlashMessage: null,
    __frontendTimedout: false,
    __inactivityInterval: null,

    __updateFlashMessage: function(timeoutSec) {
      if (this.__idleFlashMessage === null) {
        this.__idleFlashMessage = osparc.FlashMessenger.getInstance().logAs(qx.locale.Manager.tr("Are you still there?"), "WARNING", null, timeoutSec*1000);
      }

      let msg = qx.locale.Manager.tr("Are you still there?") + "<br>";
      msg += qx.locale.Manager.tr("If not, oSPARC will try to close the ") + osparc.product.Utils.getStudyAlias() + qx.locale.Manager.tr(" in: ");
      msg += osparc.utils.Utils.formatSeconds(timeoutSec);
      this.__idleFlashMessage.setMessage(msg);
    },

    __removeIdleFlashMessage: function() {
      if (this.__idleFlashMessage) {
        osparc.FlashMessenger.getInstance().removeMessage(this.__idleFlashMessage);
        this.__idleFlashMessage = null;
      }
    },

    __userIdled: function() {
      this.stop();
      this.fireEvent("userIdled");
    },

    __startTimer: function() {
      const checkFn = () => {
        const timeoutT = osparc.Preferences.getInstance().getUserInactivityThreshold();
        const warningT = Math.round(timeoutT * 0.8);
        this.__idlingTime++;
        if (this.__idlingTime >= timeoutT) {
          if (!this.__frontendTimedout) {
            // User was inactive in oSPARC, we can test services (ask every minute until response is true or we detect activity again)
            this.stop()
            const checkInactivity = () => {
              osparc.data.Resources.fetch("studies", "getInactivity", {
                url: {
                  studyId: this.__studyUuid
                }
              }).then(data => {
                if (data["is_inactive"]) {
                  this.__userIdled();
                } else {
                  this.start()
                }
              }).catch(err => {
                console.error(err);
                this.start()
              });
            };
            checkInactivity();
          }
          this.__frontendTimedout = true;
        } else if (this.__idlingTime >= warningT) {
          this.__updateFlashMessage(timeoutT - this.__idlingTime);
        } else if (this.__idleFlashMessage) {
          this.__removeIdleFlashMessage();
        }
      };
      this.__idleInterval = setInterval(checkFn, 1000);
    },

    __stopTimer: function() {
      if (this.__idleInterval) {
        clearInterval(this.__idleInterval);
        this.__idleInterval = null;
      }
    },

    __resetIdlingTime: function() {
      this.__idlingTime = 0;
      this.__frontendTimedout = false;
      clearTimeout(this.__inactivityInterval);
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

      clearTimeout(this.__inactivityInterval);
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

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

qx.Class.define("osparc.desktop.StudyEditorIdlingTracker2", {
  extend: qx.core.Object,

  events: {
    "userIdled": "qx.event.type.Event"
  },

  statics: {
    // IDLE_TIMEOUT: 30*60, // 30'
    // IDLE_WARNING: 15*60 // 15'
    IDLE_TIMEOUT: 20, // 30'
    IDLE_WARNING: 10 // 15'
  },

  members: {
    __idlingTime: null,
    __idleInteval: null,
    __idleFlashMessage: null,

    __updateFlashMessage: function(timeoutSec) {
      if (this.__idleFlashMessage === null) {
        this.__idleFlashMessage = osparc.component.message.FlashMessenger.getInstance().logAs(qx.locale.Manager.tr("Are you there?"), "WARNING", null, timeoutSec*1000);
      }

      let msg = qx.locale.Manager.tr("Are you there?") + "<br>";
      msg += qx.locale.Manager.tr("The ") + osparc.utils.Utils.getStudyLabel() + qx.locale.Manager.tr(" will be closed in ");
      msg += osparc.utils.Utils.formatSeconds(timeoutSec);
      this.__idleFlashMessage.setMessage(msg);
    },

    __removeIdleFlashMessage: function() {
      if (this.__idleFlashMessage) {
        osparc.component.message.FlashMessenger.getInstance().removeMessage(this.__idleFlashMessage);
        this.__idleFlashMessage = null;
      }
    },

    __userIdled: function() {
      this.stop();
      this.fireEvent("userIdled");
    },

    __startTimer: function() {
      this.__idleInteval = setInterval(() => {
        this.__idlingTime++;
        console.log("idling", this.__idlingTime);
        if (this.__idlingTime > this.self().IDLE_TIMEOUT) {
          this.__userIdled();
        } else if (this.__idlingTime > this.self().IDLE_WARNING) {
          this.__updateFlashMessage(this.self().IDLE_TIMEOUT - this.__idlingTime);
        } else if (this.__idleFlashMessage) {
          this.__removeIdleFlashMessage();
        }
      }, 1000);
    },

    __stopTimer: function() {
      if (this.__idleInteval) {
        clearInterval(this.__idleInteval);
        this.__idleInteval = null;
      }
    },

    __resetIdlingTime: function() {
      console.log("__resetIdlingTime");
      this.__idlingTime = 0;
    },

    start: function() {
      this.__idlingTime = 0;
      window.addEventListener("mousemove", this.__resetIdlingTime.bind(this));
      window.addEventListener("keydown", this.__resetIdlingTime.bind(this));

      this.__startTimer();
    },

    stop: function() {
      window.removeEventListener("mousemove", this.__resetIdlingTime.bind(this));
      window.removeEventListener("keydown", this.__resetIdlingTime.bind(this));

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

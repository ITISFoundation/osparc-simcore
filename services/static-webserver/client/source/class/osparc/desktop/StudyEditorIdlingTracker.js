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

  events: {
    "userIdled": "qx.event.type.Event"
  },

  statics: {
    // IDLE_TIMEOUT: 30*60*1000, // 30'
    // IDLE_WARNING: 15*60*1000 // 15'
    IDLE_TIMEOUT: 20*1000, // 30'
    IDLE_WARNING: 10*1000 // 15'
  },

  members: {
    __idleTimer: null,
    __idleInteval: null,
    __idleFlashMessage: null,
    __countdown: null,

    __updateFlashMessage: function() {
      if (this.__idleFlashMessage) {
        let msg = qx.locale.Manager.tr("Are you there?") + "<br>";
        msg += qx.locale.Manager.tr("The ") + osparc.utils.Utils.getStudyLabel() + qx.locale.Manager.tr(" will be closed in ");
        msg += osparc.utils.Utils.formatSeconds(this.__countdown/1000);
        this.__idleFlashMessage.setMessage(msg);
        this.__countdown -= 1000;
      }
    },

    __startCountdown: function() {
      const idleWarning = this.self().IDLE_WARNING;
      const idlingTimeout = this.self().IDLE_TIMEOUT;

      this.__idleTimer = setTimeout(() => this.__userIdled(), idlingTimeout - idleWarning);

      this.__idleFlashMessage = osparc.component.message.FlashMessenger.getInstance().logAs(qx.locale.Manager.tr("Are you there?"), "WARNING", null, idlingTimeout - idleWarning);
      this.__countdown = idlingTimeout - idleWarning;
      this.__updateFlashMessage();
      this.__idleInteval = setInterval(() => this.__updateFlashMessage(), 1000);
    },

    __resetTimer: function() {
      const warningAfter = this.self().IDLE_WARNING;

      console.log("reset timer");
      this.__removeTimers();
      this.__idleTimer = setTimeout(() => this.__startCountdown(), warningAfter);
    },

    __removeIdleInterval: function() {
      if (this.__idleInteval) {
        clearInterval(this.__idleInteval);
        this.__idleInteval = null;
      }
    },

    __removeIdleFlashMessage: function() {
      if (this.__idleFlashMessage) {
        osparc.component.message.FlashMessenger.getInstance().removeMessage(this.__idleFlashMessage);
        this.__idleFlashMessage = null;
      }
    },

    __removeIdleTimer: function() {
      if (this.__idleTimer) {
        clearTimeout(this.__idleTimer);
        this.__idleTimer = null;
      }
    },

    __removeTimers: function() {
      this.__removeIdleInterval();
      this.__removeIdleFlashMessage();
      this.__removeIdleTimer();
    },

    __userIdled: function() {
      this.stop();
      this.fireEvent("userIdled");
    },

    start: function() {
      this.__resetTimer();

      window.addEventListener("mousemove", this.__resetTimer.bind(this));
      window.addEventListener("keydown", this.__resetTimer.bind(this));
    },

    stop: function() {
      this.__removeTimers();

      window.removeEventListener("mousemove", this.__resetTimer.bind(this));
      window.removeEventListener("keydown", this.__resetTimer.bind(this));
    },

    /**
     * Destructor
     */
    destruct: function() {
      this.stop();
    }
  }
});

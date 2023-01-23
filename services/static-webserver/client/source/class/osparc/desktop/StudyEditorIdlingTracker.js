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

  construct: function() {
    this.base(arguments);
  },

  events: {
    "userIdled": "qx.event.type.Event"
  },

  statics: {
    IDLE_TIMEOUT: 30*60*1000, // 30'
    IDLE_WARNING: 15*60*1000 // 15'
  },

  members: {
    __idleTimer: null,
    __idleInteval: null,
    __idleFlashMessage: null,
    __countdown: null,

    __updateFlashMessage: function() {
      if (this.__idleFlashMessage) {
        let msg = this.tr("Are you there?") + "<br>";
        msg += this.tr("The ") + osparc.utils.Utils.getStudyLabel() + this.tr(" will be closed out in ");
        msg += osparc.utils.Utils.formatSeconds(this.__countdown/1000);
        this.__idleFlashMessage.setMessage(msg);
        this.__countdown -= 1000;
      }
    },

    __startCountdown: function() {
      const idleWarning = this.self().IDLE_WARNING;
      const idlingTimeout = this.self().IDLE_TIMEOUT;

      this.__idleFlashMessage = osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Are you there?"), "WARNING", null, idlingTimeout-idleWarning);
      this.__countdown = idlingTimeout - idleWarning;
      this.__updateFlashMessage();
      this.__idleInteval = setInterval(this.__updateFlashMessage, 1000);

      this.__idleTimer = setTimeout(this.__userIdled, idlingTimeout);
    },

    __resetTimer: function() {
      const warningAfter = this.self().IDLE_WARNING;
      console.log("reset timer");
      this.stop();
      this.__idleTimer = setTimeout(this.__startCountdown, warningAfter);
    },

    start: function() {
      this.__resetTimer();

      // OM dettach this
      window.onmousemove = this.__resetTimer;
      window.onkeydown = this.__resetTimer;
    },

    stop: function() {
      this.__removeIdleInterval();
      this.__removeIdleFlashMessage();
      this.__removeIdleTimer();
    },

    __removeIdleTimer: function() {
      if (this.__idleTimer) {
        clearTimeout(this.__idleTimer);
        this.__idleTimer = null;
      }
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

    __userIdled: function() {
      this.stop();
      this.fireEvent("userIdled");
    },

    /**
     * Destructor
     */
    destruct: function() {
      this.stop();
    }
  }
});

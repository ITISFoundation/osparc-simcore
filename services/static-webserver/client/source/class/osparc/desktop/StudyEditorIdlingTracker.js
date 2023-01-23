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
    IDLE_CLOSE_AFTER: 30*60*1000, // 30'
    IDLE_WARNING_AFTER: 20*60*1000 // 20'
  },

  members: {
    __idleTimer: null,
    __idleInteval: null,
    __idleFlashMessage: null,

    start: function() {
      const studyEditorIdlingTracker = this.__studyEditorIdlingTracker = new osparc.desktop.StudyEditorIdlingTracker();
      studyEditorIdlingTracker.start();

      const warningAfter = this.self().IDLE_WARNING_AFTER;
      const outAfter = this.self().IDLE_CLOSE_AFTER;

      const startCountdown = () => {
        let countdown = outAfter - warningAfter;
        this.__idleFlashMessage = osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Are you there?"), "WARNING", null, outAfter-warningAfter);
        const updateFlashMessage = () => {
          if (this.__idleFlashMessage) {
            let msg = this.tr("Are you there?") + "<br>";
            msg += this.tr("The ") + osparc.utils.Utils.getStudyLabel() + this.tr(" will be closed out in ");
            msg += osparc.utils.Utils.formatSeconds(countdown/1000);
            this.__idleFlashMessage.setMessage(msg);
            countdown -= 1000;
          }
        };
        updateFlashMessage();
        this.__idleInteval = setInterval(updateFlashMessage, 1000);

        this.__idleTimer = setTimeout(this.__userIdled, countdown);
      };

      const resetTimer = () => {
        console.log("reset timer");
        this.stop();
        this.__idleTimer = setTimeout(startCountdown, warningAfter);
      };
      resetTimer();

      // OM dettach this
      window.onmousemove = resetTimer;
      window.onkeydown = resetTimer;
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

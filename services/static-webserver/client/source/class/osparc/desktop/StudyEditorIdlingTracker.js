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

    this.__resetIdlingTimeBound = this.__resetIdlingTime.bind(this);
  },

  events: {
    "userIdled": "qx.event.type.Event"
  },

  statics: {
    IDLE_TIMEOUT: 30*60, // 30'
    IDLE_WARNING: 15*60 // 15'
  },

  members: {
    __resetIdlingTimeBound: null,
    __idlingTime: null,
    __idleInteval: null,
    __idleFlashMessage: null,

    __updateFlashMessage: function(timeoutSec) {
      if (this.__idleFlashMessage === null) {
        this.__idleFlashMessage = osparc.FlashMessenger.getInstance().logAs(qx.locale.Manager.tr("Are you still there?"), "WARNING", null, timeoutSec*1000);
      }

      let msg = qx.locale.Manager.tr("Are you still there?") + "<br>";
      msg += qx.locale.Manager.tr("If not, the ") + osparc.product.Utils.getStudyAlias() + qx.locale.Manager.tr(" will be closed in: ");
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
      this.__idleInteval = setInterval(() => {
        this.__idlingTime++;
        if (this.__idlingTime >= this.self().IDLE_TIMEOUT) {
          this.__userIdled();
        } else if (this.__idlingTime >= this.self().IDLE_WARNING) {
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
      this.__idlingTime = 0;
    },

    start: function() {
      this.__idlingTime = 0;

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

/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 *   Singleton class that pops up a window showing a log message. The time the window is visible depends
 * on the length of the message. Also if a second message is added will be stacked to the previous one.
 *
 *   Depending on the log level ("DEBUG", "INFO", "WARNING", "ERROR") the background color of the window
 * will be different.
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *   qxapp.component.message.FlashMessenger.getInstance().log(log);
 * </pre>
 */

qx.Class.define("qxapp.component.message.FlashMessenger", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__messages = new qx.data.Array();
    this.__attachEventHandlers();
  },

  members: {
    __messages: null,

    logAs: function(message, level="INFO", logger=null) {
      this.log({
        message: message,
        level: level.toUpperCase(),
        logger: logger
      });
    },

    log: function(logMessage) {
      let message = logMessage.message;
      const level = logMessage.level.toUpperCase(); // "DEBUG", "INFO", "WARNING", "ERROR"
      let logger = logMessage.logger;
      if (logger) {
        message = logger + ": " + message;
      }

      const flash = new qxapp.ui.message.FlashMessage(message, level);
      flash.addListener("closeMessage", () => this.__messages.remove(flash), this);
      this.__messages.push(flash);
    },

    showMessage: function(message) {
      const msgWidth = message.getSizeHint().width;
      const root = qx.core.Init.getApplication().getRoot();
      const left = Math.round((root.getBounds().width - msgWidth) / 2);
      root.add(message, {
        top: 10,
        left
      });

      qx.event.Timer.once(e => {
        this.__messages.remove(message);
      }, this, 5000);
    },

    removeMessage: function(message) {
      const root = qx.core.Init.getApplication().getRoot();
      root.remove(message);
    },

    __attachEventHandlers: function() {
      this.__messages.addListener("change", e => {
        const data = e.getData();
        if (data.type === "add") {
          if (this.__messages.length === 1) {
            // First in the queue
            this.showMessage(data.added[0]);
          }
        } else if (data.type === "remove") {
          this.removeMessage(data.removed[0]);
          qx.event.Timer.once(() => {
            if (this.__messages.length) {
              // There are still messages to show
              this.showMessage(this.__messages.getItem(0));
            }
          }, this, 200);
        }
      }, this);
    }
  }
});

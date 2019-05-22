/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

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

  members: {
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

      let label = new qxapp.ui.message.FlashMessage(message, level);

      // switch (level) {
      //   case "DEBUG":
      //     label.setBackgroundColor("blue");
      //     label.setTextColor("white");
      //     break;
      //   case "INFO":
      //     label.setBackgroundColor("blue");
      //     label.setTextColor("white");
      //     break;
      //   case "WARNING":
      //     label.setBackgroundColor("yellow");
      //     label.setTextColor("black");
      //     break;
      //   case "ERROR":
      //     label.setBackgroundColor("red");
      //     label.setTextColor("black");
      //     break;
      // }

      qx.core.Init.getApplication()
        .getRoot()
        .add(label);

      const time = Math.max(4000, message.length*100);
      qx.event.Timer.once(e => {
        qx.core.Init.getApplication()
          .getRoot()
          .remove(label);
      }, this, time);
    }
  }
});

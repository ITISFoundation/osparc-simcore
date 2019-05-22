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

    this.__messageContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    const root = qx.core.Init.getApplication().getRoot();
    root.add(this.__messageContainer, {
      top: 10
    });

    this.__displayedMessagesCount = 0;

    this.__attachEventHandlers();
  },

  statics: {
    MAX_DISPLAYED: 3
  },

  members: {
    __messages: null,
    __messageContainer: null,
    __displayedMessagesCount: null,

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
      flash.addListener("closeMessage", () => this.__removeMessage(flash), this);
      this.__messages.push(flash);
    },

    __showMessage: function(message) {
      this.__messages.remove(message);
      this.__messageContainer.add(message);
      const {width} = message.getSizeHint();
      if (this.__displayedMessagesCount === 0 || width > this.__messageContainer.getWidth()) {
        this.__updateContainerPosition(width);
      }
      this.__displayedMessagesCount++;
      qx.event.Timer.once(() => this.__removeMessage(message), this, 5000);
    },

    __removeMessage: function(message) {
      if (this.__messageContainer.indexOf(message) > -1) {
        this.__displayedMessagesCount--;
        this.__messageContainer.remove(message);
        qx.event.Timer.once(() => {
          if (this.__messages.length) {
            // There are still messages to show
            this.__showMessage(this.__messages.getItem(0));
          }
        }, this, 200);
      }
    },

    __updateContainerPosition: function(messageWidth) {
      const width = messageWidth || this.__messageContainer.getSizeHint().width;
      const root = qx.core.Init.getApplication().getRoot();
      this.__messageContainer.setLayoutProperties({
        left: Math.round((root.getBounds().width - width) / 2)
      });
    },

    __attachEventHandlers: function() {
      this.__messages.addListener("change", e => {
        const data = e.getData();
        if (data.type === "add") {
          if (this.__displayedMessagesCount < this.self().MAX_DISPLAYED) {
            this.__showMessage(data.added[0]);
          }
        }
      }, this);
    }
  }
});

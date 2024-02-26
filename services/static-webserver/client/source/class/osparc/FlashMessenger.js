/* ************************************************************************

   osparc - the simcore frontend

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
 *   osparc.FlashMessenger.getInstance().log(log);
 * </pre>
 */

qx.Class.define("osparc.FlashMessenger", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__messages = new qx.data.Array();

    this.__messageContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      zIndex: 110000
    });
    const root = qx.core.Init.getApplication().getRoot();
    root.add(this.__messageContainer, {
      top: 10
    });

    this.__displayedMessagesCount = 0;

    this.__attachEventHandlers();
  },

  statics: {
    MAX_DISPLAYED: 3,
    logAs: function(message, level, logger, duration) {
      return this.getInstance().logAs(message, level, logger, duration);
    }
  },

  members: {
    __messages: null,
    __messageContainer: null,
    __displayedMessagesCount: null,

    /**
     * Public function to log a FlashMessage to the user.
     *
     * @param {String} message Message that the message will show.
     * @param {String="INFO","DEBUG","WARNING","ERROR"} level Level of the warning. The color of the badge will change accordingly.
     * @param {*} logger IDK
     * @param {Number} duration
     */
    logAs: function(message, level="INFO", logger=null, duration=null) {
      return this.log({
        message,
        level: level.toUpperCase(),
        logger,
        duration
      });
    },

    log: function(logMessage) {
      // TODO: This doesn't look cool
      let message = osparc.utils.Utils.isObject(logMessage.message) && "message" in logMessage.message ?
        logMessage.message.message :
        logMessage.message;
      let logger = logMessage.logger;
      if (logger) {
        message = logger + ": " + message;
      }
      const level = logMessage.level.toUpperCase(); // "DEBUG", "INFO", "WARNING", "ERROR"

      const flashMessage = new osparc.ui.message.FlashMessage(message, level, logMessage.duration);
      flashMessage.addListener("closeMessage", () => this.removeMessage(flashMessage), this);
      this.__messages.push(flashMessage);

      return flashMessage;
    },

    /**
     * Private method to show a message to the user. It will stack it on the previous ones.
     *
     * @param {osparc.ui.message.FlashMessage} flashMessage FlassMessage element to show.
     */
    __showMessage: function(flashMessage) {
      this.__messages.remove(flashMessage);
      this.__messageContainer.resetDecorator();
      this.__messageContainer.add(flashMessage);
      const {
        width
      } = flashMessage.getSizeHint();
      if (this.__displayedMessagesCount === 0 || width > this.__messageContainer.getWidth()) {
        this.__updateContainerPosition(width);
      }
      this.__displayedMessagesCount++;

      let duration = flashMessage.getDuration();
      if (duration === null) {
        const wordCount = flashMessage.getMessage().split(" ").length;
        duration = Math.max(5500, wordCount*500); // An average reader takes 300ms to read a word
      }
      qx.event.Timer.once(() => this.removeMessage(flashMessage), this, duration);
    },

    /**
     * Private method to remove a message. If there are still messages in the queue, it will show the next available one.
     *
     * @param {osparc.ui.message.FlashMessage} flashMessage FlassMessage element to remove.
     */
    removeMessage: function(flashMessage) {
      if (this.__messageContainer.indexOf(flashMessage) > -1) {
        this.__displayedMessagesCount--;
        this.__messageContainer.setDecorator("flash-container-transitioned");
        this.__messageContainer.remove(flashMessage);
        qx.event.Timer.once(() => {
          if (this.__messages.length) {
            // There are still messages to show
            this.__showMessage(this.__messages.getItem(0));
          }
        }, this, 200);
      }
    },

    /**
     * Function to re-position the message container according to the next message size, or its own size, if the previous is missing.
     *
     * @param {Integer} messageWidth Size of the next message to add in pixels.
     */
    __updateContainerPosition: function(messageWidth) {
      const width = messageWidth || this.__messageContainer.getSizeHint().width;
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        this.__messageContainer.setLayoutProperties({
          left: Math.round((root.getBounds().width - width) / 2)
        });
      }
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

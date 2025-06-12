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
 *   osparc.FlashMessenger.logAs(log);
 * </pre>
 */

qx.Class.define("osparc.FlashMessenger", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__messages = new qx.data.Array();

    this.__messageContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      zIndex: osparc.utils.Utils.FLOATING_Z_INDEX
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

    extractMessage: function(input, defaultMessage = "") {
      const isValidString = val => {
        return (
          typeof val === "string" ||
          (osparc.utils.Utils.isObject(val) && ("basename" in val) && (val.basename === "LocalizedString"))
        );
      }
      if (input) {
        if (isValidString(input)) {
          return input;
        } else if (osparc.utils.Utils.isObject(input) && "message" in input) {
          if (isValidString(input["message"])) {
            return input["message"];
          } else if (osparc.utils.Utils.isObject(input["message"]) && "message" in input["message"] && isValidString(input["message"]["message"])) {
            return input["message"]["message"];
          }
        }
      }
      return defaultMessage;
    },

    logAs: function(message, level, duration) {
      return this.getInstance().logAs(message, level, duration);
    },

    logError: function(error, defaultMessage = qx.locale.Manager.tr("Oops... something went wrong"), duration = null) {
      if (error) {
        console.error(error);
      }
      const msg = this.extractMessage(error, defaultMessage);
      const flashMessage = this.getInstance().logAs(msg, "ERROR", duration);
      if (error && error["supportId"]) {
        flashMessage.addWidget(this.__createCopyOECWidget(msg, error["supportId"]));
        flashMessage.setDuration(flashMessage.getDuration()*2);
      }
      return flashMessage;
    },

    __createCopyOECWidget: function(message, supportId) {
      const errorLabel = new qx.ui.basic.Atom().set({
        label: supportId,
        icon: "@FontAwesome5Solid/copy/10",
        iconPosition: "right",
        gap: 8,
        cursor: "pointer",
        alignX: "center",
        allowGrowX: false,
      });
      errorLabel.addListener("tap", () => {
        const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
        const dataToClipboard = {
          message,
          supportId,
          timestamp: new Date().toString(),
          url: window.location.href,
          releaseTag: osparc.utils.Utils.getReleaseTag(),
          studyId: currentStudy ? currentStudy.getUuid() : "",
        }
        osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(dataToClipboard));
      });
      return errorLabel;
    },
  },

  members: {
    __messages: null,
    __messageContainer: null,
    __displayedMessagesCount: null,

    /**
     * Public function to log a FlashMessage to the user.
     *
     * @param {String || Object} message Message (or Object containing the message) that the message will show.
     * @param {String="INFO","DEBUG","WARNING","ERROR"} level Level of the warning. The color of the badge will change accordingly.
     * @param {Number} duration
     */
    logAs: function(message, level="INFO", duration=null) {
      return this.log({
        message,
        level: level.toUpperCase(),
        duration
      });
    },

    log: function(logMessage) {
      const message = this.self().extractMessage(logMessage);

      const level = logMessage.level.toUpperCase(); // "DEBUG", "INFO", "WARNING", "ERROR"

      const flashMessage = new osparc.ui.message.FlashMessage(message, level, logMessage.duration);
      flashMessage.addListener("closeMessage", () => this.removeMessage(flashMessage), this);
      this.__messages.push(flashMessage);

      return flashMessage;
    },

    /**
     * Private method to show a message to the user. It will stack it on the previous ones.
     *
     * @param {osparc.ui.message.FlashMessage} flashMessage FlashMessage element to show.
     */
    __showMessage: function(flashMessage) {
      if (!flashMessage.getMessage()) {
        flashMessage.setMessage(qx.locale.Manager.tr("No message"));
      }

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

      const duration = flashMessage.getDuration();
      if (duration !== 0) {
        flashMessage.timer = setTimeout(() => this.removeMessage(flashMessage), duration);
      }
    },

    /**
     * Private method to remove a message. If there are still messages in the queue, it will show the next available one.
     *
     * @param {osparc.ui.message.FlashMessage} flashMessage FlashMessage element to remove.
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

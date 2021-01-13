/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.study.Exporter", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__exports = new qx.data.Array();

    this.__exportContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      zIndex: 110000
    });
    const root = qx.core.Init.getApplication().getRoot();
    root.add(this.__exportContainer, {
      bottom: 10,
      left: 10
    });

    this.__displayedMessagesCount = 0;

    this.__attachEventHandlers();
  },

  statics: {
    MAX_DISPLAYED: 5
  },

  members: {
    __exports: null,
    __exportContainer: null,
    __displayedMessagesCount: null,

    /**
     * Public function to log a FlashMessage to the user.
     *
     * @param {Object} exportObj Constructed message to log.
     */
    addExport: function(exportObj) {
      const exportMsg = this.__createExportEntry(exportObj);
      this.__exports.push(exportMsg);
    },

    __createExportEntry: function(exportObj) {
      const exportMsg = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      })).set({
        height: 30
      });

      const icon = new osparc.ui.form.FetchButton().set({
        fetching: true
      });
      exportMsg.add(icon);

      const label = new qx.ui.basic.Label(exportObj.study.name);
      exportMsg.add(label);

      const closeBtn = new qx.ui.basic.Image("@MaterialIcons/close/16").set({
        cursor: "pointer"
      });
      closeBtn.addListener("tap", () => {
        this.__stopExport(exportMsg);
      }, this);
      exportMsg.add(closeBtn);

      exportMsg.exportObj = exportObj;

      return exportMsg;
    },

    /**
     * Private method to show a message to the user. It will stack it on the previous ones.
     *
     * @param {osparc.ui.message.FlashMessage} message FlassMessage element to show.
     */
    __showMessage: function(message) {
      this.__exports.remove(message);
      this.__exportContainer.resetDecorator();
      this.__exportContainer.add(message);
      const {
        width
      } = message.getSizeHint();
      if (this.__displayedMessagesCount === 0 || width > this.__exportContainer.getWidth()) {
        this.__updateContainerPosition(width);
      }
      this.__displayedMessagesCount++;
    },

    /**
     * Private method to remove a message. If there are still messages in the queue, it will show the next available one.
     *
     * @param {osparc.ui.message.FlashMessage} message FlassMessage element to remove.
     */
    __stopExport: function(exportMsg) {
      if (this.__exportContainer.indexOf(exportMsg) > -1) {
        this.__displayedMessagesCount--;
        this.__exportContainer.setDecorator("flash-container-transitioned");
        this.__exportContainer.remove(exportMsg);
        qx.event.Timer.once(() => {
          if (this.__exports.length) {
            // There are still messages to show
            this.__showMessage(this.__exports.getItem(0));
          }
        }, this, 200);
      }
    },

    /**
     * Function to re-position the message container according to the next message size, or its own size, if the previous is missing.
     *
     * @param {Integer} messageWidth Size of the next message to add in pixels.
     */
    __updateContainerPosition: function() {
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        this.__exportContainer.setLayoutProperties({
          bottom: 10,
          left: 10
        });
      }
    },

    __attachEventHandlers: function() {
      this.__exports.addListener("change", e => {
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

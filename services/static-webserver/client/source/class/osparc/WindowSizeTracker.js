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

qx.Class.define("osparc.WindowSizeTracker", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    tooSmall: {
      check: [null, "shortText", "longText"], // display short message, long one or none
      init: null,
      nullable: true,
      apply: "__applyTooSmall"
    }
  },

  statics: {
    MIN_WIDTH: 1240,
    MIN_HEIGHT: 700
  },

  members: {
    __lastRibbonMessage: null,

    startTracker: function() {
      // onload, load, DOMContentLoaded, appear... didn't work
      // bit of a hack
      setTimeout(() => this.__checkScreenSize(), 100);
      window.addEventListener("resize", () => this.__checkScreenSize());
    },

    __checkScreenSize: function() {
      const width = document.documentElement.clientWidth;
      const height = document.documentElement.clientHeight;
      if (width < this.self().MIN_WIDTH || height < this.self().MIN_HEIGHT) {
        this.setTooSmall(width < 1000 ? "shortText" : "longText");
      } else {
        this.setTooSmall(null);
      }
    },

    __applyTooSmall: function(tooSmall) {
      this.__removeRibbonMessage();

      if (tooSmall === null) {
        return;
      }

      let notification = null;
      if (tooSmall === "shortText") {
        notification = new osparc.component.notification.Notification(null, "smallWindow", true);
      } else if (tooSmall === "longText") {
        const text = this.__getLongText(true);
        notification = new osparc.component.notification.Notification(text, "smallWindow", true);
      }
      osparc.component.notification.NotificationsRibbon.getInstance().addNotification(notification);
      this.__lastRibbonMessage = notification;
    },

    __getLongText: function() {
      let text = qx.locale.Manager.tr("This app performs better for at least ");
      text += this.self().MIN_WIDTH + "x" + this.self().MIN_HEIGHT;
      text += qx.locale.Manager.tr(" window size. Touchscreen devices are not supported yet.");
      return text;
    },

    __removeRibbonMessage: function() {
      if (this.__lastRibbonMessage) {
        osparc.component.notification.NotificationsRibbon.getInstance().removeNotification(this.__lastRibbonMessage);
        this.__lastRibbonMessage = null;
      }
    }
  }
});

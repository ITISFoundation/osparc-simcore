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
      check: "Boolean",
      init: false,
      nullable: false,
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
        this.setTooSmall(true);
      } else {
        this.setTooSmall(false);
      }
    },

    __applyTooSmall: function(tooSmall) {
      this.__removeRibbonMessage();

      if (tooSmall) {
        const width = document.documentElement.clientWidth;
        const text = this.__getText(width > 400);
        const notification = new osparc.component.notification.Notification(text, "smallWindow", true);
        osparc.component.notification.NotificationsRibbon.getInstance().addNotification(notification);
        this.__lastRibbonMessage = notification;
      }
    },

    __getText: function(longVersion = true) {
      let text = "";
      if (longVersion) {
        text += qx.locale.Manager.tr("This app performs better for at least ");
        text += this.self().MIN_WIDTH + "x" + this.self().MIN_HEIGHT;
        text += qx.locale.Manager.tr(" window size. Touchscreen devices are not supported yet.");
      }
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

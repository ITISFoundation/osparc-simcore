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
      if (tooSmall) {
        const width = document.documentElement.clientWidth;
        const text = this.__getText(width > 400);
        this.setText(text);
      } else {
        this.setText();
      }
    },

    __getText: function(longVersion = true) {
      let text = this.tr("Oops, your window is a bit small!");
      if (longVersion) {
        text += this.tr(" This app performs better for minimum ");
        text += this.self().MIN_WIDTH + "x" + this.self().MIN_HEIGHT;
        text += this.tr(" window size.");
        text += this.tr(" Touchscreen devices are not supported yet.");
      }
      return text;
    },

    __scheduleRibbonMessage: function() {
      this.__removeRibbonMessage();

      const now = new Date();
      const diffClosable = this.getStart().getTime() - now.getTime() - this.self().CLOSABLE_WARN_IN_ADVANCE;
      const diffPermanent = this.getStart().getTime() - now.getTime() - this.self().PERMANENT_WARN_IN_ADVANCE;

      const messageToRibbon = closable => {
        this.__removeRibbonMessage();
        const text = this.__getText();
        const notification = new osparc.component.notification.Notification(text, "maintenance", closable);
        osparc.component.notification.NotificationsRibbon.getInstance().addNotification(notification);
        this.__lastRibbonMessage = notification;
      };
      if (diffClosable < 0) {
        messageToRibbon(true);
      } else {
        setTimeout(() => messageToRibbon(true), diffClosable);
      }
      if (diffPermanent < 0) {
        messageToRibbon(false);
      } else {
        setTimeout(() => messageToRibbon(false), diffPermanent);
      }
    },

    __removeRibbonMessage: function() {
      if (this.__lastRibbonMessage) {
        osparc.component.notification.NotificationsRibbon.getInstance().removeNotification(this.__lastRibbonMessage);
        this.__lastRibbonMessage = null;
      }
    }
  }
});

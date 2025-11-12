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
    windowWidth: {
      check: "Integer",
      init: null,
      nullable: false
    },

    windowHeight: {
      check: "Integer",
      init: null,
      nullable: false
    },

    compactVersion: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeCompactVersion"
    },

    tooSmall: {
      check: [null, "logout", "shortText", "longText"],
      init: null,
      nullable: true,
      apply: "__applyTooSmall"
    }
  },

  statics: {
    WIDTH_LOGOUT_BREAKPOINT: 600,
    WIDTH_COMPACT_BREAKPOINT: 1100,
    WIDTH_BREAKPOINT: 1180, // - iPad Pro 11" 1194x834 inclusion
    HEIGHT_BREAKPOINT: 720, // - iPad Pro 11" 1194x834 inclusion
  },

  members: {
    __tooSmallDialog: null,
    __lastRibbonMessage: null,

    startTracker: function() {
      // onload, load, DOMContentLoaded, appear... didn't work
      // bit of a hack
      setTimeout(() => this.__resized(), 100);
      window.addEventListener("resize", () => this.__resized());
    },

    __resized: function() {
      const width = document.documentElement.clientWidth;
      const height = document.documentElement.clientHeight;

      this.setCompactVersion(width < this.self().WIDTH_COMPACT_BREAKPOINT);

      if (width < this.self().WIDTH_LOGOUT_BREAKPOINT) {
        this.setTooSmall("logout");
      } else if (width < this.self().WIDTH_COMPACT_BREAKPOINT) {
        this.setTooSmall("shortText");
      } else if (width < this.self().WIDTH_BREAKPOINT || height < this.self().HEIGHT_BREAKPOINT) {
        this.setTooSmall("longText");
      } else {
        this.setTooSmall(null);
      }

      this.set({
        windowWidth: width,
        windowHeight: height
      });
    },

    __applyTooSmall: function(tooSmall) {
      this.__removeRibbonMessage();

      if (tooSmall === null) {
        return;
      }

      let notification = null;
      if (tooSmall === "logout" || tooSmall === "shortText") {
        notification = new osparc.notification.RibbonNotification(null, "smallWindow", true);
      } else if (tooSmall === "longText") {
        const text = this.__getLongText(true);
        notification = new osparc.notification.RibbonNotification(text, "smallWindow", true);
      }
      osparc.notification.RibbonNotifications.getInstance().addNotification(notification);
      this.__lastRibbonMessage = notification;

      this.evaluateTooSmallDialog();
    },

    __getLongText: function() {
      let text = qx.locale.Manager.tr("This app performs better for larger window size: ");
      text += " " + this.self().WIDTH_BREAKPOINT + "x" + this.self().HEIGHT_BREAKPOINT + (".");
      text += " " + qx.locale.Manager.tr("Touchscreen devices are not supported yet.");
      return text;
    },

    __removeRibbonMessage: function() {
      if (this.__lastRibbonMessage) {
        osparc.notification.RibbonNotifications.getInstance().removeNotification(this.__lastRibbonMessage);
        this.__lastRibbonMessage = null;
      }
    },

    evaluateTooSmallDialog: function() {
      const tooSmall = this.getTooSmall();
      if (tooSmall === "logout") {
        if (this.__tooSmallDialog) {
          this.__tooSmallDialog.center();
          this.__tooSmallDialog.open();
        } else {
          this.__tooSmallDialog = osparc.TooSmallDialog.openWindow();
          this.__tooSmallDialog.addListener("close", () => this.__tooSmallDialog = null, this);
        }
      } else if (this.__tooSmallDialog) {
        this.__tooSmallDialog.close();
      }
    }
  }
});

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

qx.Class.define("osparc.component.notification.RibbonNotifications", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this.__notifications = new qx.data.Array();

    this.set({
      alignX: "center",
      alignY: "middle",
      visibility: "excluded"
    });

    this.__updateRibbon();
  },

  members: {
    __notifications: null,

    /**
     * @param {osparc.component.notification.Notification} notification
     */
    addNotification: function(notification) {
      this.__notifications.push(notification);
      this.__updateRibbon();
    },

    createNotificationUI: function(notification) {
      const notificationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5, "center")).set({
        backgroundColor: notification.getType() === "announcement" ? "strong-main" : "warning-yellow-s4l",
        allowGrowX: true
      });

      const notificationAtom = new qx.ui.basic.Atom().set({
        label: notification.getFullText(),
        icon: notification.getType() === "announcement" ? null : "@FontAwesome5Solid/exclamation-triangle/14",
        center: true,
        padding: 2,
        gap: 10,
        height: 20
      });
      notificationAtom.getChildControl("label").set({
        textColor: notification.getType() === "announcement" ? "white" : "black",
        font: "text-14",
        rich: true,
        wrap: true,
        selectable: true
      });
      notificationAtom.getChildControl("icon").set({
        textColor: "black"
      });
      notificationLayout.add(notificationAtom);

      if (notification.getClosable()) {
        const closeButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/times/12").set({
          backgroundColor: "transparent",
          textColor: notification.getType() === "announcement" ? "white" : "black"
        });
        closeButton.addListener("tap", () => this.removeNotification(notification), this);
        notificationLayout.add(closeButton);
      }
      return notificationLayout;
    },

    /**
     * @param {osparc.component.notification.Notification} notification
     */
    removeNotification: function(notification) {
      if (this.__notifications.indexOf(notification) > -1) {
        this.__notifications.remove(notification);
      }
      this.__updateRibbon();
    },

    __updateRibbon: function() {
      this._removeAll();
      const notifications = this.__notifications;
      if (notifications.length) {
        this.show();
        notifications.forEach(notification => {
          const notificationUI = this.createNotificationUI(notification);
          this._add(notificationUI);
        });
      } else {
        this.exclude();
      }
    }
  }
});

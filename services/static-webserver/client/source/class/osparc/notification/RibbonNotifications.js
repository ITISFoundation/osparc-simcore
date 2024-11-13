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

qx.Class.define("osparc.notification.RibbonNotifications", {
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
     * @param {osparc.notification.RibbonNotification} notification
     */
    addNotification: function(notification) {
      this.__notifications.push(notification);
      this.__updateRibbon();
    },

    /**
     * @param {osparc.notification.RibbonNotification} notification
     */
    removeNotification: function(notification) {
      if (this.__notifications.indexOf(notification) > -1) {
        this.__notifications.remove(notification);
      }
      this.__updateRibbon();
    },

    /**
     * @param {osparc.notification.RibbonNotification} notification
     */
    __createNotificationUI: function(notification) {
      const notificationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5, "center")).set({
        backgroundColor: notification.getType() === "announcement" ? "strong-main" : "warning-yellow",
        allowGrowX: true
      });

      const notificationAtom = new qx.ui.basic.Atom().set({
        label: notification.getFullText(),
        icon: notification.getType() === "announcement" ? null : "@FontAwesome5Solid/exclamation-triangle/14",
        padding: notification.getType() === "announcement" ? 6 : 2,
        height: notification.getType() === "announcement" ? 30 : 20,
        center: true,
        gap: 10
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
          textColor: notification.getType() === "announcement" ? "white" : "black",
          alignY: "middle"
        });
        closeButton.addListener("tap", () => this.removeNotification(notification), this);
        notificationLayout.add(closeButton);
      }

      if (notification.getType() === "announcement") {
        const dontShowButton = new qx.ui.form.Button(this.tr("Don't show again")).set({
          appearance: "strong-button",
          alignY: "middle",
          padding: 4,
          allowGrowX: false,
          allowGrowY: false,
          marginLeft: 15
        });
        osparc.utils.Utils.addBorder(dontShowButton, 1, qx.theme.manager.Color.getInstance().resolve("text"));
        dontShowButton.addListener("tap", () => {
          this.removeNotification(notification);
          osparc.utils.Utils.localCache.setDontShowAnnouncement(notification.announcementId);
        });
        notificationLayout.add(dontShowButton);
      }

      return notificationLayout;
    },

    __updateRibbon: function() {
      this._removeAll();
      const notifications = this.__notifications;
      // sort notifications
      notifications.sort((a, _) => (a.getType() === "announcement" ? 1 : -1));
      if (notifications.length) {
        this.show();
        notifications.forEach(notification => {
          const notificationUI = this.__createNotificationUI(notification);
          this._add(notificationUI);
        });
      } else {
        this.exclude();
      }
    }
  }
});

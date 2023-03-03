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

qx.Class.define("osparc.component.notification.NotificationsContainer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(1));

    this.set({
      zIndex: 110000
    });

    const root = qx.core.Init.getApplication().getRoot();
    root.add(this, {
      top: 0,
      right: 0
    });

    const notifications = osparc.component.notification.Notifications.getInstance();
    notifications.getNotifications().addListener("change", () => this.__updateNotificationsContainer(), this);
    this.__updateNotificationsContainer();
  },

  members: {
    __updateNotificationsContainer: function() {
      this._removeAll();
      const notifications = osparc.component.notification.Notifications.getInstance().getNotifications();
      notifications.forEach(notification => {
        const notificationUI = new osparc.component.notification.NotificationUI();
        notificationUI.set({
          id: notification.id,
          category: notification.category,
          actionablePath: notification.actionable_path,
          title: notification.title,
          text: notification.text,
          date: new Date(notification.date),
          read: notification.read
        });
        this._add(notificationUI);
      });
    },

    setPosition: function(x, y) {
      this.setLayoutProperties({
        left: x - osparc.component.notification.NotificationUI.MAX_WIDTH,
        top: y
      });
    }
  }
});

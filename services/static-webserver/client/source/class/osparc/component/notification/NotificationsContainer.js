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
    notifications.getNotifications().addListener("change", () => this.__updateContainer(), this);
    this.__updateContainer();
  },

  members: {
    __updateContainer: function() {
      this._removeAll();
      const notifications = osparc.component.notification.Notifications.getInstance().getNotifications();
      notifications.forEach(notification => {
        const notificationUI = new osparc.component.notification.NotificationUI(notification);
        notificationUI.addListener("notificationTapped", () => this.exclude());
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

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

qx.Class.define("osparc.notification.NotificationsContainer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      zIndex: 110000,
      backgroundColor: "background-main-2",
      maxWidth: osparc.notification.NotificationUI.MAX_WIDTH,
      maxHeight: 250
    });

    const root = qx.core.Init.getApplication().getRoot();
    root.add(this, {
      top: 0,
      right: 0
    });

    const notificationsContainer = this.__container = new qx.ui.container.Composite(new qx.ui.layout.VBox(1));
    const scrollContainer = new qx.ui.container.Scroll();
    scrollContainer.add(notificationsContainer);
    this._add(scrollContainer, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    const notifications = osparc.notification.Notifications.getInstance();
    notifications.getNotifications().addListener("change", () => this.__updateContainer(), this);
    this.__updateContainer();
  },

  members: {
    __container: null,

    __updateContainer: function() {
      this.__container.removeAll();
      const notifications = osparc.notification.Notifications.getInstance().getNotifications();
      notifications.forEach(notification => {
        const notificationUI = new osparc.notification.NotificationUI(notification);
        notificationUI.addListener("notificationTapped", () => this.exclude());
        this.__container.add(notificationUI);
      });
    },

    setPosition: function(x, y) {
      this.setLayoutProperties({
        left: x - osparc.notification.NotificationUI.MAX_WIDTH,
        top: y
      });
    }
  }
});

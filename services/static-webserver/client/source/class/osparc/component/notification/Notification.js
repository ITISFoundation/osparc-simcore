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

qx.Class.define("osparc.component.notification.Notification", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);
    this.__notifications = new qx.data.Array();

    const notificationsContainer = this.__notificationsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(3)).set({
      zIndex: 110000,
      visibility: "excluded"
    });
    osparc.utils.Utils.setIdToWidget(notificationsContainer, "notifications");
    const root = qx.core.Init.getApplication().getRoot();
    root.add(notificationsContainer, {
      top: 0,
      right: 0
    });
  },

  statics: {
    MAX_WIDTH: 300
  },

  members: {
    __notifications: null,
    __notificationsContainer: null,

    addNotification: function(notification) {
      this.__notifications.push(notification);
      this.__notificationsContainer.addAt(notification, 0);
    },

    getNotifications: function() {
      return this.__notifications;
    },

    getNotificationsContainer: function() {
      return this.__notificationsContainer;
    },

    setNotificationsContainerPosition: function(x, y) {
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        this.__notificationsContainer.setLayoutProperties({
          left: x - this.self().MAX_WIDTH,
          top: y
        });
      }
    }
  }
});

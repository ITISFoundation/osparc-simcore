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

qx.Class.define("osparc.component.notification.Notifications", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__notifications = new qx.data.Array();
  },

  members: {
    __notifications: null,

    addNotification: function(notification) {
      this.__notifications.push(JSON.parse(notification));
      this.__notifications.sort((a, b) => new Date(b.date) - new Date(a.date));
    },

    addNotifications: function(notifications) {
      notifications.forEach(notification => this.addNotification(notification));
    },

    removeNotification: function(notification) {
      this.__notifications.remove(notification);
    },

    getNotifications: function() {
      return this.__notifications;
    }
  }
});

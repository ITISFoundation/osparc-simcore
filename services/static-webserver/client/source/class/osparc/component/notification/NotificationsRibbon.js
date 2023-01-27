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

qx.Class.define("osparc.component.notification.NotificationsRibbon", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__notifications = new qx.data.Array();

    this.set({
      backgroundColor: "warning-yellow",
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

    removeNotification: function(notification) {
      this.__notifications.push(notification);
      this.__updateRibbon();
    },

    __updateRibbon: function() {
      const notifications = this.__notifications;
      console.log("notifications", notifications);
      if (notifications.length) {
        this.show();
        this._removeAll();
        notifications.forEach(notificationUI => {
          const text = notificationUI.getFullText();
          const notification = new qx.ui.basic.Atom().set({
            label: text,
            icon: "@FontAwesome5Solid/exclamation-triangle/16",
            center: true,
            padding: 2,
            gap: 15,
            height: 20
          });
          notification.getChildControl("label").set({
            textColor: "black",
            font: "text-14",
            rich: true,
            wrap: true
          });
          notification.getChildControl("icon").set({
            textColor: "black"
          });
          this._add(notification);
        });
      } else {
        this.exclude();
      }
    }
  }
});

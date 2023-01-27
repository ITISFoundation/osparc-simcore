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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      backgroundColor: "warning-yellow",
      alignX: "center",
      alignY: "middle",
      visibility: "excluded"
    });

    const notifications = osparc.component.notification.Notifications.getInstance();
    notifications.getNotifications().addListener("change", () => this.__updateNotificationsButton(), this);
    this.__updateNotificationsButton();
  },

  members: {
    __updateNotificationsButton: function() {
      const notifications = osparc.component.notification.Notifications.getInstance().getNotifications();
      if (notifications.length) {
        this.show();
        this._removeAll();
        notifications.forEach(notificationUI => {
          let text = notificationUI.getText();
          text = text.replaceAll("<br>", ". ");
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

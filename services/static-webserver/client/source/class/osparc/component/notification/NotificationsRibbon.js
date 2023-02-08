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

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this.__notifications = new qx.data.Array();

    this.set({
      backgroundColor: "warning-yellow-s4l",
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
          const text = notification.getFullText();
          const notificationAtom = new qx.ui.basic.Atom().set({
            label: text,
            icon: "@FontAwesome5Solid/exclamation-triangle/14",
            center: true,
            padding: 2,
            gap: 10,
            height: 20
          });
          notificationAtom.getChildControl("label").set({
            textColor: "black",
            font: "text-14",
            rich: true,
            wrap: true,
            selectable: true
          });
          notificationAtom.getChildControl("icon").set({
            textColor: "black"
          });
          if (notification.getClosable()) {
            const closableLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5, "center"));
            closableLayout.add(notificationAtom);
            const closeButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/times/12").set({
              backgroundColor: "transparent",
              textColor: "black"
            });
            closeButton.addListener("tap", () => this.removeNotification(notification), this);
            closableLayout.add(closeButton);
            this._add(closableLayout);
          } else {
            this._add(notificationAtom);
          }
        });
      } else {
        this.exclude();
      }
    }
  }
});

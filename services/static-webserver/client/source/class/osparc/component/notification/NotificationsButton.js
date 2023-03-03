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

qx.Class.define("osparc.component.notification.NotificationsButton", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      width: 30,
      alignX: "center",
      cursor: "pointer",
      visibility: "excluded"
    });

    this._createChildControlImpl("icon");
    this._createChildControlImpl("number");

    const notifications = osparc.component.notification.Notifications.getInstance();
    notifications.getNotifications().addListener("change", () => this.__updateNotificationsButton(), this);
    this.addListener("tap", () => this.__showNotifications(), this);
    this.__updateNotificationsButton();

    this.__notificationsContainer = new osparc.component.notification.NotificationsContainer();
    this.__notificationsContainer.exclude();
  },

  members: {
    __notificationsContainer: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Solid/bell/22");
          const iconContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          iconContainer.add(control);
          this._add(iconContainer, {
            height: "100%"
          });
          break;
        }
        case "number":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          control.bind("value", control, "visibility", {
            converter: value => value === "0" ? "excluded" : "visible"
          });
          this._add(control, {
            bottom: 8,
            right: 4
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __updateNotificationsButton: function() {
      const notifications = osparc.component.notification.Notifications.getInstance().getNotifications();
      notifications.length ? this.show() : this.exclude();

      const number = this.getChildControl("number");
      const unreadNotifications = notifications.filter(notification => notification["read"] === false).length;
      number.setValue(unreadNotifications.toString());
    },

    __showNotifications: function() {
      const that = this;
      const tapListener = event => {
        const notificationsContainer = this.__notificationsContainer;
        if (osparc.utils.Utils.isMouseOnElement(notificationsContainer, event)) {
          return;
        }
        // eslint-disable-next-line no-underscore-dangle
        that.__hideNotifications();
        document.removeEventListener("mousedown", tapListener);
      };

      const bounds = this.getBounds();
      const cel = this.getContentElement();
      if (cel) {
        const domeEle = cel.getDomElement();
        if (domeEle) {
          const rect = domeEle.getBoundingClientRect();
          bounds.left = parseInt(rect.x);
          bounds.top = parseInt(rect.y);
        }
      }
      this.__notificationsContainer.setPosition(bounds.left+bounds.width, osparc.navigation.NavigationBar.HEIGHT+3);
      this.__notificationsContainer.show();

      document.addEventListener("mousedown", tapListener);
    },

    __hideNotifications: function() {
      this.__notificationsContainer.exclude();
    }
  }
});

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

qx.Class.define("osparc.notification.NotificationsButton", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    osparc.utils.Utils.setIdToWidget(this, "notificationsButton");

    this.set({
      width: 30,
      alignX: "center",
      cursor: "pointer"
    });

    this._createChildControlImpl("icon");
    this._createChildControlImpl("number");

    const notifications = osparc.notification.Notifications.getInstance();
    notifications.getNotifications().addListener("change", () => this.__updateButton(), this);
    this.__updateButton();

    this.__notificationsContainer = new osparc.notification.NotificationsContainer();
    this.__notificationsContainer.exclude();

    this.addListener("tap", this.__buttonTapped, this);
  },

  members: {
    __notificationsContainer: null,
    __tappedOut: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image();
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
            backgroundColor: "error",
            textColor: "white",
            font: "text-12",
            padding: [0, 4],
            visibility: this.value > 0 ? "visible" : "hidden"
          });
          control.getContentElement().setStyles({
            "border-radius": "8px"
          });
          this._add(control, {
            bottom: 8,
            right: 4
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __updateButton: function() {
      const notifications = osparc.notification.Notifications.getInstance().getNotifications();
      notifications.forEach(notification => notification.addListener("changeRead", () => this.__updateButton(), this));

      const nUnreadNotifications = notifications.filter(notification => notification.getRead() === false).length;
      const icon = this.getChildControl("icon");
      icon.set({
        source: nUnreadNotifications > 0 ? "@FontAwesome5Solid/bell/22" : "@FontAwesome5Regular/bell/22",
        textColor: nUnreadNotifications > 0 ? "strong-main" : "text"
      });
      const number = this.getChildControl("number");
      number.set({
        value: nUnreadNotifications.toString(),
        visibility: nUnreadNotifications > 0 ? "visible" : "excluded"
      });
    },

    __buttonTapped: function() {
      if (this.__tappedOut) {
        this.__tappedOut = false;
        return;
      }
      this.__showNotifications();
    },

    __showNotifications: function() {
      const tapListener = event => {
        // In case a notification was tapped propagate the event so it can be handled by the NotificationUI
        if (osparc.utils.Utils.isMouseOnElement(this.__notificationsContainer, event)) {
          return;
        }
        // I somehow can't stop the propagation of the event so workaround:
        // If the user tapped on the bell we don't want to show it again
        if (osparc.utils.Utils.isMouseOnElement(this, event)) {
          this.__tappedOut = true;
        }
        this.__hideNotifications();
        document.removeEventListener("mousedown", tapListener, this);
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
      this.__notificationsContainer.setPosition(bounds.left+bounds.width-2, bounds.top+bounds.height-2);
      this.__notificationsContainer.show();

      document.addEventListener("mousedown", tapListener, this);
    },

    __hideNotifications: function() {
      this.__notificationsContainer.exclude();
    }
  }
});

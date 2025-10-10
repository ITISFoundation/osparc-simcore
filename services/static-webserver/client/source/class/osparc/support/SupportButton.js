/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.support.SupportButton", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    osparc.utils.Utils.setIdToWidget(this, "helpNavigationBtn");

    this._createChildControlImpl("icon");
    this._createChildControlImpl("number");

    // this should be support conversations
    const notifications = osparc.notification.Notifications.getInstance();
    notifications.getNotifications().addListener("change", () => this.__updateButton(), this);
    this.__updateButton();

    this.addListener("tap", () => osparc.support.SupportCenter.openWindow());
  },

  members: {
    __notificationsContainer: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Regular/question-circle/24");
          const iconContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle",
          })).set({
            paddingLeft: 5,
          });
          iconContainer.add(control);
          this._add(iconContainer, {
            height: "100%"
          });
          break;
        }
        case "is-active-icon-outline":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/12").set({
            textColor: osparc.navigation.NavigationBar.BG_COLOR,
          });
          this._add(control, {
            bottom: -4,
            right: -4,
          });
          break;
        case "is-active-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/8").set({
            textColor: "strong-main",
          });
          this._add(control, {
            bottom: -2,
            right: -2,
          });
          break;
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
      const notificationManager = osparc.notification.Notifications.getInstance();
      const notifications = notificationManager.getNotifications();
      notifications.forEach(notification => notification.addListener("changeRead", () => this.__updateButton(), this));

      let nUnreadNotifications = notifications.filter(notification => notification.getRead() === false).length;
      [
        this.getChildControl("is-active-icon-outline"),
        this.getChildControl("is-active-icon"),
      ].forEach(control => {
        control.set({
          visibility: nUnreadNotifications > 0 ? "visible" : "excluded"
        });
      });
    },

    __buttonTapped: function() {
      if (this.__notificationsContainer && this.__notificationsContainer.isVisible()) {
        this.__hideNotificationsContainer();
      } else {
        this.__showNotificationsContainer();
      }
    },
  }
});

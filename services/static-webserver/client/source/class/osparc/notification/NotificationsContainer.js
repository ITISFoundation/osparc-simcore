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
      zIndex: osparc.utils.Utils.FLOATING_Z_INDEX,
      maxWidth: osparc.notification.NotificationUI.MAX_WIDTH,
      maxHeight: 250,
      backgroundColor: "background-main",
      decorator: "rounded",
    });
    let color = qx.theme.manager.Color.getInstance().resolve("text");
    color = qx.util.ColorUtil.stringToRgb(color);
    color.push(0.3); // add transparency
    color = qx.util.ColorUtil.rgbToRgbString(color);
    osparc.utils.Utils.addBorder(this, 1, color);
    osparc.utils.Utils.setIdToWidget(this, "notificationsContainer");

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
      if (notifications.length) {
        notifications.forEach(notification => {
          const notificationUI = new osparc.notification.NotificationUI(notification);
          notificationUI.addListener("notificationTapped", () => this.exclude());
          this.__container.add(notificationUI);
        });
      } else {
        const aboutLabel = new qx.ui.basic.Label().set({
          value: "If something is shared with you, it will appear here",
          font: "text-14",
          padding: osparc.notification.NotificationUI.PADDING,
          rich: true,
          wrap: true
        });
        this.__container.add(aboutLabel);
      }
    },

    setPosition: function(x, y) {
      this.setLayoutProperties({
        left: x - osparc.notification.NotificationUI.MAX_WIDTH,
        top: y
      });
    }
  }
});

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

    this.set({
      toolTipText: this.tr("Help & Support"),
    });

    osparc.utils.Utils.setIdToWidget(this, "helpNavigationBtn");

    this.__listenToStore();
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
            paddingLeft: 4,
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
      }
      return control || this.base(arguments, id);
    },

    __listenToStore: function() {
      const conversationsStore = osparc.store.ConversationsSupport.getInstance();
      conversationsStore.getConversations().forEach(conversation => conversation.addListener("changeUnread", () => this.__updateButton(), this));
      conversationsStore.addListener("conversationAdded", () => this.__updateButton(), this);
      conversationsStore.addListener("conversationDeleted", () => this.__updateButton(), this);
    },

    __updateButton: function() {
      const notificationManager = osparc.notification.Notifications.getInstance();
      const notifications = notificationManager.getNotifications();
      notifications.forEach(notification => notification.addListener("changeRead", () => this.__updateButton(), this));

      this.getChildControl("icon");
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
  }
});

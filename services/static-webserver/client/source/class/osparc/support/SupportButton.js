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

    osparc.utils.Utils.setIdToWidget(this, "helpNavigationBtn"); // "action": "toggle" in the guided tours

    this.getChildControl("icon");

    this.__listenToStore();
    this.__updateButton();

    this.addListener("tap", () => {
      const supportCenter = osparc.support.SupportCenter.openWindow();
      if (this.isUnreadMessages()) {
        supportCenter.showConversations();
      }
    });
  },

  properties: {
    unreadMessages: {
      check: "Boolean",
      init: null,
      nullable: false,
      event: "changeUnreadMessages",
      apply: "__applyUnreadMessages",
    },
  },

  members: {
    __notificationsContainer: null,

    /**
     * Public method to open the support center.
     * Used by the guided tours via "action": "toggle".
     */
    toggle: function() {
      osparc.support.SupportCenter.openWindow();
    },

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
      const eventName = osparc.store.Groups.getInstance().amIASupportUser() ? "changeReadBySupport" : "changeReadByUser";
      const conversationsStore = osparc.store.ConversationsSupport.getInstance();
      const cachedConversations = conversationsStore.getConversations();
      cachedConversations.forEach(conversation => conversation.addListener(eventName, () => this.__updateButton(), this));
      conversationsStore.addListener("conversationAdded", e => {
        const conversation = e.getData();
        conversation.addListener(eventName, e => {
          this.__updateButton();
        }, this);
        this.__updateButton();
      }, this);
    },

    __updateButton: function() {
      const propName = osparc.store.Groups.getInstance().amIASupportUser() ? "readBySupport" : "readByUser";
      const conversationsStore = osparc.store.ConversationsSupport.getInstance();
      const cachedConversations = conversationsStore.getConversations();
      const unread = cachedConversations.some(conversation => Boolean(conversation.get(propName) === false));
      this.setUnreadMessages(unread);
    },

    __applyUnreadMessages: function(unread) {
      [
        this.getChildControl("is-active-icon-outline"),
        this.getChildControl("is-active-icon"),
      ].forEach(control => {
        control.set({
          visibility: unread ? "visible" : "excluded"
        });
      });
    },
  }
});

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

qx.Class.define("osparc.support.ConversationListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(10);
    layout.setSpacingY(0);

    // decorate
    this.getChildControl("thumbnail").setDecorator("circled");
    this.getChildControl("title").set({
      rich: false, // let ellipsis work
    });
    this.getChildControl("subtitle").set({
      rich: false, // let ellipsis work
    });
    this.getChildControl("sub-subtitle").set({
      textColor: "text-disabled",
    });
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: false,
      event: "changeConversation",
      apply: "__applyConversation",
    },

    subSubtitle: {
      check : "String",
      apply : "__applySubSubtitle",
      nullable : true
    },
  },

  members: {
    _createChildControlImpl: function(id, hash) {
      let control;
      switch(id) {
        case "sub-subtitle":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            selectable: true,
            rich: true,
          });
          this._add(control, {
            row: 2,
            column: 1
          });
          break;
        case "unread-badge":
          control = new osparc.ui.basic.Chip(this.tr("Unread")).set({
            statusColor: "success",
            font: "text-12",
            allowGrowY: false,
            alignX: "right",
          });
          this.getChildControl("third-column-layout").addAt(control, 1, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyConversation: function(conversation) {
      conversation.bind("nameAlias", this, "title");

      this.__lastMessageChanged();
      conversation.addListener("changeLastMessage", this.__lastMessageChanged, this);

      this.__firstMessageChanged();
      conversation.addListener("changeFirstMessage", this.__firstMessageChanged, this);

      conversation.bind("lastMessageCreatedAt", this, "role", {
        converter: val => {
          return val ? osparc.utils.Utils.formatDateAndTime(val) : "";
        },
      });

      const unreadBadge = this.getChildControl("unread-badge");
      const propName = osparc.store.Groups.getInstance().amIASupportUser() ? "readBySupport" : "readByUser";
      conversation.bind(propName, unreadBadge, "visibility", {
        converter: val => val === false ? "visible" : "excluded"
      });
    },

    __lastMessageChanged: function() {
      const conversation = this.getConversation();
      const lastMessage = conversation.getLastMessage();
      if (lastMessage) {
        const userGroupId = lastMessage.getUserGroupId();
        osparc.store.Users.getInstance().getUser(userGroupId)
          .then(user => {
            if (user) {
              this.set({
                thumbnail: user.getThumbnail(),
                subtitle: user.getLabel() + ": " + lastMessage.getContent(),
              });
            }
          });
      }
    },

    __firstMessageChanged: function() {
      const conversation = this.getConversation();
      const firstMessage = conversation.getFirstMessage();
      if (firstMessage) {
        const userGroupId = firstMessage.getUserGroupId();
        osparc.store.Users.getInstance().getUser(userGroupId)
          .then(user => {
            if (user) {
              const amISupporter = osparc.store.Groups.getInstance().amIASupportUser();
              let subSubtitle = "Started";
              if (amISupporter) {
                subSubtitle += " by " + user.getLabel();
              }
              const date = osparc.utils.Utils.formatDateAndTime(firstMessage.getCreated());
              subSubtitle += " on " + date;
              this.set({
                subSubtitle,
              });
            }
          });
      }
    },

    __applySubSubtitle: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("sub-subtitle");
      label.setValue(value);
    },
  },
});

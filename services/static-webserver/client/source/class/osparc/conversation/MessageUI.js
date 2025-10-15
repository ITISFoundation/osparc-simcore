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


qx.Class.define("osparc.conversation.MessageUI", {
  extend: qx.ui.core.Widget,

  /**
    * @param message {osparc.data.model.Message} message
    * @param studyData {Object?null} serialized Study Data
    */
  construct: function(message, studyData = null) {
    this.base(arguments);

    this.__studyData = studyData;

    this._setLayout(new qx.ui.layout.HBox(10));
    this.setPadding(5);

    this.set({
      message,
    });
  },

  events: {
    "messageUpdated": "qx.event.type.Data",
    "messageDeleted": "qx.event.type.Data",
  },

  properties: {
    message: {
      check: "osparc.data.model.Message",
      init: null,
      nullable: false,
      apply: "_applyMessage",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      const isMyMessage = osparc.data.model.Message.isMyMessage(this.getMessage());
      let control;
      switch (id) {
        case "avatar":
          control = new osparc.ui.basic.UserThumbnail(32).set({
            marginTop: 4,
            alignY: "top",
          });
          this._addAt(control, isMyMessage ? 1 : 0);
          break;
        case "main-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(2).set({
            alignX: isMyMessage ? "right" : "left"
          }));
          this._addAt(control, isMyMessage ? 0 : 1, { flex: 1});
          break;
        case "header-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: isMyMessage ? "right" : "left"
          }));
          control.addAt(new qx.ui.basic.Label("-"), 1);
          this.getChildControl("main-layout").addAt(control, 0);
          break;
        case "user-name":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            textColor: "text-disabled",
          });
          this.getChildControl("header-layout").addAt(control, isMyMessage ? 2 : 0);
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            textColor: "text-disabled",
          });
          this.getChildControl("header-layout").addAt(control, isMyMessage ? 0 : 2);
          break;
        case "message-bubble":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
            alignX: isMyMessage ? "right" : "left"
          })).set({
            decorator: "chat-bubble",
            allowGrowX: false,
            padding: 8,
          });
          const bubbleStyle = isMyMessage ? { "border-top-right-radius": "0px" } : { "border-top-left-radius": "0px" };
          control.getContentElement().setStyles(bubbleStyle);
          this.getChildControl("main-layout").addAt(control, 1);
          break;
        case "message-content":
          control = new osparc.ui.markdown.MarkdownChat();
          this.getChildControl("message-bubble").add(control);
          break;
        case "menu-button": {
          const buttonSize = 22;
          control = new qx.ui.form.MenuButton().set({
            width: buttonSize,
            height: buttonSize,
            allowGrowX: false,
            allowGrowY: false,
            marginTop: 4,
            alignY: "top",
            icon: "@FontAwesome5Solid/ellipsis-v/12",
            focusable: false
          });
          this._addAt(control, 2);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    _applyMessage: function(message) {
      const updateLastUpdate = () => {
        const createdDate = osparc.utils.Utils.formatDateAndTime(message.getCreated());
        let value = "";
        if (message.getCreated().getTime() === message.getModified().getTime()) {
          value = createdDate;
        } else {
          const updatedDate = osparc.utils.Utils.formatDateAndTime(message.getModified());
          value = createdDate + " (" + this.tr("edited") + " "+ updatedDate + ")";
        }
        this.getChildControl("last-updated").setValue(value);
      };
      updateLastUpdate();
      message.addListener("changeModified", () => updateLastUpdate());

      const messageContent = this.getChildControl("message-content");
      message.bind("content", messageContent, "value");

      const avatar = this.getChildControl("avatar");
      const userName = this.getChildControl("user-name");
      if (osparc.data.model.Message.isSupportMessage(message)) {
        userName.setValue("Support");
      } else {
        osparc.store.Users.getInstance().getUser(message.getUserGroupId())
          .then(user => {
            avatar.setUser(user);
            userName.setValue(user ? user.getLabel() : "Unknown user");
          })
          .catch(() => {
            avatar.setSource(osparc.utils.Avatar.emailToThumbnail());
            userName.setValue("Unknown user");
          });
      }

      if (osparc.data.model.Message.isMyMessage(message)) {
        const menuButton = this.getChildControl("menu-button");

        const menu = new qx.ui.menu.Menu().set({
          position: "bottom-right",
        });
        menuButton.setMenu(menu);

        const editButton = new qx.ui.menu.Button(this.tr("Edit..."));
        editButton.addListener("execute", () => this.__editMessage(), this);
        menu.add(editButton);

        const deleteButton = new qx.ui.menu.Button(this.tr("Delete..."));
        deleteButton.addListener("execute", () => this.__deleteMessage(), this);
        menu.add(deleteButton);
      }
    },

    __editMessage: function() {
      const message = this.getMessage();

      const addMessage = new osparc.conversation.AddMessage().set({
        studyData: this.__studyData,
        conversationId: message.getConversationId(),
        message,
      });
      addMessage.getChildControl("notify-user-button").exclude();
      const title = this.tr("Edit message");
      const win = osparc.ui.window.Window.popUpInWindow(addMessage, title, 570, 120).set({
        clickAwayClose: false,
        resizable: true,
        showClose: true,
      });
      addMessage.addListener("updateMessage", e => {
        const content = e.getData();
        if (this.__studyData) {
          promise = osparc.store.ConversationsProject.getInstance().editMessage(message, content, this.__studyData["uuid"]);
        } else {
          promise = osparc.store.ConversationsSupport.getInstance().editMessage(message, content);
        }
        promise.then(data => {
          win.close();
          this.fireDataEvent("messageUpdated", data);
        });
      });
    },

    __deleteMessage: function() {
      const message = this.getMessage();

      const win = new osparc.ui.window.Confirmation(this.tr("Delete message?")).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete",
      });
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          let promise = null;
          if (this.__studyData) {
            promise = osparc.store.ConversationsProject.getInstance().deleteMessage(message, this.__studyData["uuid"]);
          } else {
            promise = osparc.store.ConversationsSupport.getInstance().deleteMessage(message);
          }
          promise
            .then(() => this.fireDataEvent("messageDeleted", message))
            .catch(err => osparc.FlashMessenger.logError(err));
        }
      });
    },
  }
});

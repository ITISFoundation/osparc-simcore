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
    * @param message {Object} message data
    * @param studyData {Object?null} serialized Study Data
    */
  construct: function(message, studyData = null) {
    this.base(arguments);

    this.__studyData = studyData;

    const layout = new qx.ui.layout.Grid(12, 2);
    layout.setColumnFlex(1, 1); // content
    this._setLayout(layout);
    this.setPadding(5);

    this.set({
      message,
    });
  },

  statics: {
    isMyMessage: function(message) {
      return message && osparc.auth.Data.getInstance().getGroupId() === message["userGroupId"];
    }
  },

  events: {
    "messageUpdated": "qx.event.type.Data",
    "messageDeleted": "qx.event.type.Data",
  },

  properties: {
    message: {
      check: "Object",
      init: null,
      nullable: false,
      apply: "__applyMessage",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      const isMyMessage = this.self().isMyMessage(this.getMessage());
      let control;
      switch (id) {
        case "thumbnail":
          control = osparc.utils.Utils.createThumbnail(32).set({
            marginTop: 4,
          });
          this._add(control, {
            row: 0,
            column: isMyMessage ? 2 : 0,
            rowSpan: 2,
          });
          break;
        case "header-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: isMyMessage ? "right" : "left"
          }));
          control.addAt(new qx.ui.basic.Label("-"), 1);
          this._add(control, {
            row: 0,
            column: 1
          });
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
        case "message-content":
          control = new osparc.ui.markdown.Markdown().set({
            noMargin: true,
            allowGrowX: true,
          });
          control.getContentElement().setStyles({
            "text-align": isMyMessage ? "right" : "left",
          });
          this._add(control, {
            row: 1,
            column: 1,
          });
          break;
        case "spacer":
          control = new qx.ui.core.Spacer();
          this._add(control, {
            row: 1,
            column: isMyMessage ? 0 : 2,
          });
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
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          this._add(control, {
            row: 0,
            column: 3,
            rowSpan: 2,
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __applyMessage: function(message) {
      const isMyMessage = this.self().isMyMessage(message);
      this._getLayout().setColumnFlex(isMyMessage ? 0 : 2, 3); // spacer

      const thumbnail = this.getChildControl("thumbnail");

      const userName = this.getChildControl("user-name");

      const createdDateData = new Date(message["created"]);
      const createdDate = osparc.utils.Utils.formatDateAndTime(createdDateData);
      const lastUpdate = this.getChildControl("last-updated");
      if (message["created"] === message["modified"]) {
        lastUpdate.setValue(createdDate);
      } else {
        const updatedDateData = new Date(message["modified"]);
        const updatedDate = osparc.utils.Utils.formatDateAndTime(updatedDateData);
        lastUpdate.setValue(createdDate + " (" + this.tr("edited") + " "+ updatedDate + ")");
      }

      const messageContent = this.getChildControl("message-content");
      messageContent.setValue(message["content"]);

      osparc.store.Users.getInstance().getUser(message["userGroupId"])
        .then(user => {
          if (user) {
            thumbnail.setSource(user.getThumbnail());
            userName.setValue(user.getLabel());
          } else {
            thumbnail.setSource(osparc.utils.Avatar.emailToThumbnail());
            userName.setValue("Unknown user");
          }
        })
        .catch(() => {
            thumbnail.setSource(osparc.utils.Avatar.emailToThumbnail());
            userName.setValue("Unknown user");
        });

      this.getChildControl("spacer");

      if (this.self().isMyMessage(message)) {
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
        conversationId: message["conversationId"],
        message,
      });
      const title = this.tr("Edit message");
      const win = osparc.ui.window.Window.popUpInWindow(addMessage, title, 570, 135).set({
        clickAwayClose: false,
        resizable: true,
        showClose: true,
      });
      addMessage.addListener("messageUpdated", e => {
        win.close();
        this.fireDataEvent("messageUpdated", e.getData());
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
            promise = osparc.store.ConversationsProject.getInstance().deleteMessage(message);
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

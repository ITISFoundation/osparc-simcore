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

    this.addListener("resize", this.__updateMessageMaxWidth, this);
  },

  events: {
    "messageUpdated": "qx.event.type.Data",
    "messageDeleted": "qx.event.type.Data",
    "resized": "qx.event.type.Event",
  },

  properties: {
    message: {
      check: "osparc.data.model.Message",
      init: null,
      nullable: false,
      apply: "_applyMessage",
    },

    groupedWithPrevious: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "__applyGroupedWithPrevious",
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
        case "bubble-row":
          // holds the bubble and, for my messages, the hover menu to its left
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(4).set({
            alignX: isMyMessage ? "right" : "left",
            alignY: "top",
          }));
          this.getChildControl("main-layout").addAt(control, 1);
          break;
        case "message-bubble": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
            alignX: isMyMessage ? "right" : "left"
          })).set({
            decorator: isMyMessage ? "chat-bubble-mine" : "chat-bubble",
            allowGrowX: false,
            padding: 8,
          });
          const bubbleStyle = isMyMessage ? { "border-top-right-radius": "0px" } : { "border-top-left-radius": "0px" };
          control.getContentElement().setStyles(bubbleStyle);
          this.getChildControl("bubble-row").add(control);
          break;
        }
        case "message-content":
          control = new osparc.ui.markdown.MarkdownChat();
          if (isMyMessage) {
            control.setTextColor("white");
          }
          control.addListener("resized", () => this.fireEvent("resized"));
          this.getChildControl("message-bubble").add(control);
          break;
        case "menu-button": {
          const buttonSize = 20;
          control = new qx.ui.form.MenuButton().set({
            width: buttonSize,
            height: buttonSize,
            allowGrowX: false,
            allowGrowY: false,
            marginTop: 4,
            alignY: "top",
            backgroundColor: "transparent",
            textColor: "text",
            center: true,
            icon: "@FontAwesomeSolid/ellipsis-v/12",
            focusable: false
          });
          // hidden until the message is hovered (see __applyMessage)
          control.setOpacity(0);
          control.getContentElement().setStyles({ "transition": "opacity 0.12s ease" });
          // sit just left of the bubble, in the empty gutter (revealed on hover)
          this.getChildControl("bubble-row").addAt(control, 0);
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
        userName.setValue(this.tr("Support"));
      } else {
        osparc.store.Users.getInstance().getUser(message.getUserGroupId())
          .then(user => {
            avatar.setUser(user);
            userName.setValue(user ? user.getLabel() : this.tr("Unknown user"));
          })
          .catch(() => {
            avatar.setSource(osparc.utils.Avatar.emailToThumbnail());
            userName.setValue(this.tr("Unknown user"));
          });
      }

      if (osparc.data.model.Message.isMyMessage(message)) {
        const menuButton = this.getChildControl("menu-button");

        // reveal the menu button only while hovering this message
        this.addListener("pointerover", () => menuButton.setOpacity(1), this);
        this.addListener("pointerout", e => {
          if (!this.__isInside(e.getRelatedTarget())) {
            menuButton.setOpacity(0);
          }
        }, this);

        const menu = new qx.ui.menu.Menu().set({
          position: "bottom-right",
          appearance: "menu-wider",
        });
        menuButton.setMenu(menu);

        const editButton = new qx.ui.menu.Button(this.tr("Edit..."), "@FontAwesomeSolid/pencil-alt/12");
        editButton.addListener("execute", () => this.__editMessage(), this);
        menu.add(editButton);

        const deleteButton = new qx.ui.menu.Button(this.tr("Delete..."), "@FontAwesomeSolid/trash/12");
        deleteButton.addListener("execute", () => this.__deleteMessage(), this);
        menu.add(deleteButton);
      }
    },

    // true when the given widget is this message or one of its descendants
    __isInside: function(widget) {
      while (widget) {
        if (widget === this) {
          return true;
        }
        widget = widget.getLayoutParent();
      }
      return false;
    },

    __applyGroupedWithPrevious: function(grouped) {
      // consecutive messages from the same sender are visually grouped:
      // hide the repeated avatar/name/timestamp and tighten the spacing
      const isMyMessage = osparc.data.model.Message.isMyMessage(this.getMessage());
      this.getChildControl("avatar").setVisibility(grouped ? "hidden" : "visible");
      this.getChildControl("header-layout").setVisibility(grouped ? "excluded" : "visible");
      this.setPaddingTop(grouped ? 0 : 5);
      // only the first bubble in a group keeps the "tail" corner
      const bubble = this.getChildControl("message-bubble");
      const corner = isMyMessage ? "border-top-right-radius" : "border-top-left-radius";
      const styles = {};
      styles[corner] = grouped ? "" : "0px";
      bubble.getContentElement().setStyles(styles);
    },

    __updateMessageMaxWidth: function() {
      const bounds = this.getBounds();
      if (bounds) {
        // ~70% of available width, minus avatar+padding (~60px)
        const maxWidth = Math.round((bounds.width - 60) * 0.7);
        const messageContent = this.getChildControl("message-content");
        messageContent.setMeasurerMaxWidth(Math.max(maxWidth, 150));
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
      // check if support center is open to decide where to open the edit message window
      const width = this.__studyData ? 570 : osparc.support.SupportCenter.WINDOW_WIDTH - 10;
      const win = osparc.ui.window.Window.popUpInWindow(addMessage, title, width, 120).set({
        clickAwayClose: false,
        resizable: true,
        showClose: true,
      });
      if (!this.__studyData) {
        // only if the message belong to the support center
        const supportCenter = osparc.ui.window.SingletonWindow.getWindowById("support-center");
        win.setCenterOnElement(supportCenter);
        win.center();
      }
      addMessage.addListener("updateMessage", e => {
        const content = e.getData();
        let promise = null;
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

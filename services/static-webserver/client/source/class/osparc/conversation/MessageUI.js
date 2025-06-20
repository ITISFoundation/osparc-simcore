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
    * @param message {Object} message
    */
  construct: function(message) {
    this.base(arguments);

    this.__message = message;

    const isMyMessage = this.self().isMyMessage(this.__message);
    const layout = new qx.ui.layout.Grid(12, 4);
    layout.setColumnFlex(1, 1); // content
    layout.setColumnFlex(isMyMessage ? 0 : 2, 3); // spacer
    this._setLayout(layout);
    this.setPadding(5);

    this.__buildLayout();
  },

  statics: {
    isMyMessage: function(message) {
      return message && osparc.auth.Data.getInstance().getGroupId() === message["userGroupId"];
    }
  },

  members: {
    __message: null,

    _createChildControlImpl: function(id) {
      const isMyMessage = this.self().isMyMessage(this.__message);
      let control;
      switch (id) {
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            scale: true,
            maxWidth: 32,
            maxHeight: 32,
            decorator: "rounded",
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
            font: "text-12"
          });
          this.getChildControl("header-layout").addAt(control, isMyMessage ? 2 : 0);
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this.getChildControl("header-layout").addAt(control, isMyMessage ? 0 : 2);
          break;
        case "message-content":
          control = new osparc.ui.markdown.Markdown().set({
            decorator: "rounded",
            noMargin: true,
            paddingLeft: 8,
            paddingRight: 8,
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
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const thumbnail = this.getChildControl("thumbnail");

      const userName = this.getChildControl("user-name");

      const date = new Date(this.__message["modified"]);
      const date2 = osparc.utils.Utils.formatDateAndTime(date);
      const lastUpdate = this.getChildControl("last-updated");
      lastUpdate.setValue(date2);

      const messageContent = this.getChildControl("message-content");
      if (this.__message["type"] === "NOTIFICATION") {
        const userGroupId = parseInt(this.__message["content"]);
        messageContent.setValue("🔔 " + this.tr("Notified") + ": ");
        osparc.store.Users.getInstance().getUser(userGroupId)
          .then(user => {
            if (user) {
              messageContent.setValue(messageContent.getValue() + user.getLabel());
            } else {
              messageContent.setValue(messageContent.getValue() + userGroupId);
            }
          })
          .catch(() => {
            messageContent.setValue(messageContent.getValue() + userGroupId);
          });
      } else if (this.__message["type"] === "MESSAGE") {
        messageContent.setValue(this.__message["content"]);
      }

      osparc.store.Users.getInstance().getUser(this.__message["userGroupId"])
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
    }
  }
});

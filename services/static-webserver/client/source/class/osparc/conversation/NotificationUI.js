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


qx.Class.define("osparc.conversation.NotificationUI", {
  extend: qx.ui.core.Widget,

  /**
    * @param message {Object} message
    */
  construct: function(message) {
    this.base(arguments);

    const isMyMessage = osparc.conversation.MessageUI.isMyMessage(message);
    const layout = new qx.ui.layout.Grid(4, 4);
    layout.setColumnFlex(isMyMessage ? 0 : 3, 3); // spacer
    layout.setRowAlign(0, "center", "middle");
    this._setLayout(layout);
    this.setPadding(5);

    this.set({
      message,
    });
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
    // spacer - date - content - (thumbnail-spacer)
    // (thumbnail-spacer) - content - date - spacer
    _createChildControlImpl: function(id) {
      const isMyMessage = osparc.conversation.MessageUI.isMyMessage(this.getMessage());
      let control;
      switch (id) {
        case "thumbnail-spacer":
          control = new qx.ui.core.Spacer().set({
            width: 32,
          });
          this._add(control, {
            row: 0,
            column: isMyMessage ? 3 : 0,
          });
          break;
        case "message-content":
          control = new qx.ui.basic.Label().set({
          });
          control.getContentElement().setStyles({
            "text-align": isMyMessage ? "right" : "left",
          });
          this._add(control, {
            row: 0,
            column: isMyMessage ? 2 : 1,
          });
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this._add(control, {
            row: 0,
            column: isMyMessage ? 1 : 2,
          });
          break;
        case "spacer":
          control = new qx.ui.core.Spacer();
          this._add(control, {
            row: 0,
            column: isMyMessage ? 0 : 3,
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyMessage: function(message) {
      this._removeAll();

      this.getChildControl("thumbnail-spacer");

      const isMyMessage = osparc.conversation.MessageUI.isMyMessage(message);

      const modifiedDate = new Date(message["modified"]);
      const date = osparc.utils.Utils.formatDateAndTime(modifiedDate);
      const lastUpdate = this.getChildControl("last-updated");
      lastUpdate.setValue(isMyMessage ? date + " -" : " - " + date);

      const messageContent = this.getChildControl("message-content");
      const notifierUserGroupId = parseInt(message["userGroupId"]);
      const notifiedUserGroupId = parseInt(message["content"]);
      let msgContent = "🔔 ";
      Promise.all([
        osparc.store.Users.getInstance().getUser(notifierUserGroupId),
        osparc.store.Users.getInstance().getUser(notifiedUserGroupId),
      ])
        .then(values => {
          const notifierUser = values[0];
          if (isMyMessage) {
            msgContent += "You";
          } else if (notifierUser) {
            msgContent += notifierUser.getLabel();
          } else {
            msgContent += "unknown user";
          }

          msgContent += " notified ";

          const notifiedUser = values[1];
          if (osparc.auth.Data.getInstance().getGroupId() === notifiedUserGroupId) {
            msgContent += "You";
          } else if (notifiedUser) {
            msgContent += notifiedUser.getLabel();
          } else {
            msgContent += "unknown user";
          }
        })
        .catch(() => {
          msgContent += "unknown user notified";
        })
        .finally(() => {
          messageContent.setValue(msgContent);
        });

      this.getChildControl("spacer");
    }
  }
});

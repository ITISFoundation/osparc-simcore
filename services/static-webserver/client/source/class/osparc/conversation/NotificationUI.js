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

    this.__message = message;

    const isMyMessage = osparc.conversation.MessageUI.isMyMessage(this.__message);
    const layout = new qx.ui.layout.Grid(12, 4);
    layout.setColumnFlex(1, 1); // content
    layout.setColumnFlex(isMyMessage ? 0 : 3, 3); // spacer
    this._setLayout(layout);
    this.setPadding(5);

    this.__buildLayout();
  },

  members: {
    __message: null,

    // spacer - content - date - (thumbnail-spacer)
    // (thumbnail-spacer) - content - date - spacer
    _createChildControlImpl: function(id) {
      const isMyMessage = osparc.conversation.MessageUI.isMyMessage(this.__message);
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
          control = new osparc.ui.markdown.Markdown().set({
            decorator: "rounded",
            noMargin: true,
            paddingLeft: 8,
            paddingRight: 8,
            minWidth: 200,
            width: 200,
          });
          control.getContentElement().setStyles({
            "text-align": isMyMessage ? "right" : "left",
          });
          this._add(control, {
            row: 0,
            column: 1,
          });
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this._add(control, {
            row: 0,
            column: 2,
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

    __buildLayout: function() {
      this.getChildControl("thumbnail-spacer");

      const date = new Date(this.__message["modified"]);
      const date2 = osparc.utils.Utils.formatDateAndTime(date);
      const lastUpdate = this.getChildControl("last-updated");
      lastUpdate.setValue(date2);

      const messageContent = this.getChildControl("message-content");
      const notifiedUserGroupId = parseInt(this.__message["content"]);
      let msgContent = "🔔 ";
      Promise.all([
        osparc.store.Users.getInstance().getUser(this.__message["userGroupId"]),
        osparc.store.Users.getInstance().getUser(notifiedUserGroupId),
      ])
        .then(values => {
          const notifierUser = values[0];
          const notifiedUser = values[1];
          if (notifierUser) {
            msgContent += notifierUser.getLabel();
          } else {
            msgContent += "unknown user";
          }
          msgContent += " notified ";
          if (notifiedUser) {
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

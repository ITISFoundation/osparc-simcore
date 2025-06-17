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


qx.Class.define("osparc.info.CommentUI", {
  extend: qx.ui.core.Widget,

  /**
    * @param comment {Object} comment
    */
  construct: function(comment) {
    this.base(arguments);

    this.__comment = comment;

    const isMyComment = this.__isMyComment();
    const layout = new qx.ui.layout.Grid(12, 4);
    layout.setColumnFlex(1, 1); // comment
    layout.setColumnFlex(isMyComment ? 0 : 2, 3); // spacer
    this._setLayout(layout);
    this.setPadding(5);

    this.__buildLayout();
  },

  members: {
    __comment: null,

    __isMyComment: function() {
      return this.__comment && osparc.auth.Data.getInstance().getGroupId() === this.__comment["userGroupId"];
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            scale: true,
            maxWidth: 32,
            maxHeight: 32,
            decorator: "rounded",
            marginTop: 2,
          });
          this._add(control, {
            row: 0,
            column: this.__isMyComment() ? 2 : 0,
            rowSpan: 2,
          });
          break;
        case "header-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: this.__isMyComment() ? "right" : "left"
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
          this.getChildControl("header-layout").addAt(control, this.__isMyComment() ? 2 : 0);
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this.getChildControl("header-layout").addAt(control, this.__isMyComment() ? 0 : 2);
          break;
        case "comment-content":
          control = new osparc.ui.markdown.Markdown().set({
            decorator: "rounded",
            noMargin: true,
            paddingLeft: 8,
            paddingRight: 8,
            allowGrowX: true,
          });
          control.getContentElement().setStyles({
            "text-align": this.__isMyComment() ? "right" : "left",
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
            column: this.__isMyComment() ? 0 : 2,
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const thumbnail = this.getChildControl("thumbnail");

      const userName = this.getChildControl("user-name");

      const date = new Date(this.__comment["modified"]);
      const date2 = osparc.utils.Utils.formatDateAndTime(date);
      const lastUpdate = this.getChildControl("last-updated");
      lastUpdate.setValue(date2);

      const commentContent = this.getChildControl("comment-content");
      if (this.__comment["type"] === "NOTIFICATION") {
        commentContent.setValue("🔔 " + this.tr("Notified") + ": ");
        osparc.store.Users.getInstance().getUser(parseInt(this.__comment["content"]))
          .then(user => {
            if (user) {
              commentContent.setValue(commentContent.getValue() + user.getLabel());
            } else {
              commentContent.setValue(commentContent.getValue() + parseInt(this.__comment["content"]));
            }
          })
          .catch(() => {
            commentContent.setValue(commentContent.getValue() + parseInt(this.__comment["content"]));
          });
      } else if (this.__comment["type"] === "MESSAGE") {
        commentContent.setValue(this.__comment["content"]);
      }

      osparc.store.Users.getInstance().getUser(this.__comment["userGroupId"])
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

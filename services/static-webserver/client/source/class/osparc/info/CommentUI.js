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
    const layout = new qx.ui.layout.Grid(12, 5);
    layout.setColumnFlex(isMyComment ? 0 : 1, 1); // message content
    this._setLayout(layout);
    this.setPadding(5);

    this.__buildLayout();
  },

  members: {
    __comment: null,

    __isMyComment: function() {
      return this.__comment && osparc.auth.Data.getInstance().getUserId() === this.__comment["user_id"];
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "meta-data-grid": {
          const layout = new qx.ui.layout.Grid(12, 5)
          layout.setColumnWidth(this.__isMyComment() ? 1 : 0, 32); // thumbnail
          control = new qx.ui.container.Composite(layout);
          this._add(control, {
            row: 0,
            column: this.__isMyComment() ? 1 : 0
          });
          break;
        }
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            scale: true,
            maxWidth: 32,
            maxHeight: 32,
            decorator: "rounded",
          });
          this.getChildControl("meta-data-grid").add(control, {
            row: 0,
            column: this.__isMyComment() ? 1 : 0,
            rowSpan: 2
          });
          break;
        case "user-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this.getChildControl("meta-data-grid").add(control, {
            row: 0,
            column: this.__isMyComment() ? 0 : 1
          });
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this.getChildControl("meta-data-grid").add(control, {
            row: 1,
            column: this.__isMyComment() ? 0 : 1
          });
          break;
        case "comment-content":
          control = new osparc.ui.markdown.Markdown();
          control.getContentElement().setStyles({
            "text-align": this.__isMyComment() ? "right" : "left"
          });
          this._add(control, {
            row: 0,
            column: this.__isMyComment() ? 0 : 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const thumbnail = this.getChildControl("thumbnail");
      thumbnail.setSource(osparc.utils.Avatar.getUrl("", 32));

      const userName = this.getChildControl("user-name");
      userName.setValue("Unknown");

      const date = new Date(this.__comment["modified"]);
      const date2 = osparc.utils.Utils.formatDateAndTime(date);
      const lastUpdate = this.getChildControl("last-updated");
      lastUpdate.setValue(date2);

      const commentContent = this.getChildControl("comment-content");
      commentContent.setValue(this.__comment["contents"]);

      const user = osparc.store.Groups.getInstance().getUserByUserId(this.__comment["user_id"])
      if (user) {
        thumbnail.setSource(user.getThumbnail());
        userName.setValue(user.getLabel());
      }
    }
  }
});

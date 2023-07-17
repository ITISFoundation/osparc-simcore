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

    const layout = new qx.ui.layout.Grid(8, 5);
    layout.setColumnWidth(0, 32);
    layout.setColumnFlex(1, 1);
    this._setLayout(layout);
    this.setPadding(5);

    this.__comment = comment;

    this.__buildLayout();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            scale: true,
            allowGrowX: true,
            allowGrowY: true,
            allowShrinkX: true,
            allowShrinkY: true,
            maxWidth: 32,
            maxHeight: 32
          });
          control.getContentElement().setStyles({
            "border-radius": "8px"
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 2
          });
          break;
        case "user-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        case "last-updated":
          control = new qx.ui.basic.Label().set({
            font: "text-13"
          });
          this._add(control, {
            row: 0,
            column: 2
          });
          break;
        case "comment-content":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true,
            wrap: true
          });
          this._add(control, {
            row: 1,
            column: 1,
            colSpan: 2
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

      osparc.store.Store.getInstance().getUser(this.__comment["user_id"])
        .then(user => {
          if (user) {
            const userSource = osparc.utils.Avatar.getUrl(user["login"], 32);
            thumbnail.setSource(userSource);
            userName.setValue(user["label"]);
          }
        });
    }
  }
});

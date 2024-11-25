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


qx.Class.define("osparc.info.CommentAdd", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyId {String} Study Id
    */
  construct: function(studyId) {
    this.base(arguments);

    this.__studyId = studyId;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  events: {
    "commentAdded": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "add-comment-label":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Add comment")
          });
          this._add(control);
          break;
        case "add-comment-layout": {
          const grid = new qx.ui.layout.Grid(8, 5);
          grid.setColumnWidth(0, 32);
          grid.setColumnFlex(1, 1);
          control = new qx.ui.container.Composite(grid);
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "thumbnail": {
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            scale: true,
            allowGrowX: true,
            allowGrowY: true,
            allowShrinkX: true,
            allowShrinkY: true,
            maxWidth: 32,
            maxHeight: 32,
            decorator: "rounded",
          });
          const myEmail = osparc.auth.Data.getInstance().getEmail();
          control.set({
            source: osparc.utils.Avatar.getUrl(myEmail, 32)
          });
          const layout = this.getChildControl("add-comment-layout");
          layout.add(control, {
            row: 0,
            column: 0
          });
          break;
        }
        case "comment-field": {
          control = new osparc.editor.MarkdownEditor();
          control.getChildControl("buttons").exclude();
          const layout = this.getChildControl("add-comment-layout");
          layout.add(control, {
            row: 0,
            column: 1
          });
          break;
        }
        case "add-comment-button": {
          control = new qx.ui.form.Button(this.tr("Add")).set({
            appearance: "form-button",
            allowGrowX: false,
            alignX: "right"
          });
          this._add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("thumbnail");
      const commentField = this.getChildControl("comment-field");
      const addButton = this.getChildControl("add-comment-button");
      addButton.addListener("execute", () => {
        const commentText = commentField.getChildControl("text-area").getValue();
        if (commentText) {
          const params = {
            url: {
              studyId: this.__studyId
            },
            data: {
              "contents": commentText
            }
          };
          osparc.data.Resources.fetch("studyComments", "addComment", params)
            .then(() => {
              this.fireEvent("commentAdded");
              commentField.getChildControl("text-area").setValue("");
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            });
        }
      });
    }
  }
});

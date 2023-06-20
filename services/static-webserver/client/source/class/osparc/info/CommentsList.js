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


qx.Class.define("osparc.info.CommentsList", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyId {String} Study Id
    */
  construct: function(studyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__studyId = studyId;

    this.__buildLayout();

    this.fetchComments();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("0 Comments")
          });
          this._add(control);
          break;
        case "comments-list":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            alignY: "middle"
          });
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("title");
      this.getChildControl("comments-list");
    },

    fetchComments: function() {
      this.getChildControl("comments-list").removeAll();

      const comments = [{
        "comment_id": 1,
        "project_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "user_id": 1,
        "content": "One comment from user 1",
        "created_at": "2023-06-20T08:42:13.805Z",
        "updated_at": "2023-06-20T08:42:13.805Z"
      }, {
        "comment_id": 2,
        "project_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "user_id": 2,
        "content": "Another comment from user 2",
        "created_at": "2023-06-20T09:42:13.805Z",
        "updated_at": "2023-06-20T09:42:13.805Z"
      }, {
        "comment_id": 3,
        "project_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "user_id": 3,
        "content": "One more comment from user 3",
        "created_at": "2023-06-20T10:42:13.805Z",
        "updated_at": "2023-06-20T10:42:13.805Z"
      }];
      this.__addComments(comments);
      return;

      const params = {
        url: {
          offset: 0,
          limit: 20
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      osparc.data.Resources.fetch("studyComments", "getPage", params, undefined, options)
        .then(comments => this.__addComments(comments));
    },

    __getNextRequestParams: function() {
      return null;
    },

    __addComments: function(comments) {
      const commentsTitle = this.getChildControl("title");
      if (comments.length === 1) {
        commentsTitle.setValue(this.tr("1 Comment"));
      } else if (comments.length > 1) {
        commentsTitle.setValue(comments.length + this.tr(" Comments"));
      }

      const commentsList = this.getChildControl("comments-list");
      comments.forEach(comment => {
        const commentUi = new osparc.info.CommentUI(comment);
        commentsList.add(commentUi);
      });
    }
  }
});

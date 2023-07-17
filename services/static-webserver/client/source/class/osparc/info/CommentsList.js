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

    this.__studyId = studyId;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();

    this.fetchComments();
  },

  members: {
    __nextRequestParams: null,

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
        case "load-more-button":
          control = new osparc.ui.form.FetchButton(this.tr("Load more comments..."));
          control.addListener("execute", () => this.fetchComments(false));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("title");
      this.getChildControl("comments-list");
      this.getChildControl("load-more-button");
    },

    fetchComments: function(removeComments = true) {
      const loadMoreButton = this.getChildControl("load-more-button");
      loadMoreButton.show();
      loadMoreButton.setFetching(true);

      if (removeComments) {
        this.getChildControl("comments-list").removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const comments = resp["data"];
          this.__addComments(comments);
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null) {
            loadMoreButton.exclude();
          }
        })
        .finally(() => loadMoreButton.setFetching(false));
    },

    __getNextRequest: function() {
      const params = {
        url: {
          studyId: this.__studyId,
          offset: 0,
          limit: 20
        }
      };
      const nextRequestParams = this.__nextRequestParams;
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("studyComments", "getPage", params, undefined, options);
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

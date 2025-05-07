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


qx.Class.define("osparc.info.Conversation", {
  extend: qx.ui.tabview.Page,

  /**
    * @param studyData {String} Study Data
    * @param conversationId {int} Conversation Id
    */
  construct: function(studyData, conversationId = null) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__conversationId = conversationId;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      padding: 10,
      showCloseButton: false,
    });

    this.__buildLayout();

    this.fetchComments();
  },

  members: {
    __studyData: null,
    __conversationId: null,
    __nextRequestParams: null,
    __commentsTitle: null,
    __commentsList: null,
    __loadMoreComments: null,

    __buildLayout: function() {
      this.__commentsTitle = new qx.ui.basic.Label();
      this._add(this.__commentsTitle);

      this.__commentsList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        alignY: "middle"
      });
      this._add(this.__commentsList, {
        flex: 1
      });

      this.__loadMoreComments = new osparc.ui.form.FetchButton(this.tr("Load more comments..."));
      this.__loadMoreComments.addListener("execute", () => this.fetchComments(false));
      this._add(this.__loadMoreComments);

      if (osparc.data.model.Study.canIWrite(this.__studyData["accessRights"])) {
        const addComments = new osparc.info.CommentAdd(this.__studyData["uuid"]);
        addComments.setPaddingLeft(10);
        addComments.addListener("commentAdded", () => this.fetchComments());
        this._add(addComments);
      }
    },

    fetchComments: function(removeComments = true) {
      if (this.__conversationId === null) {
        this.__commentsList.hide();
        this.__loadMoreComments.hide();
        return;
      }

      this.__loadMoreComments.show();
      this.__loadMoreComments.setFetching(true);

      if (removeComments) {
        this.__commentsList.removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const comments = resp["data"];
          this.__addComments(comments);
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null) {
            this.__loadMoreComments.exclude();
          }
        })
        .finally(() => this.__loadMoreComments.setFetching(false));
    },

    __getNextRequest: function() {
      const params = {
        url: {
          studyId: this.__studyData["uuid"],
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
      return osparc.data.Resources.fetch("studyComments", "getPage", params, options);
    },

    __addComments: function(comments) {
      if (comments.length === 1) {
        this.__commentsTitle.setValue(this.tr("1 Comment"));
      } else if (comments.length > 1) {
        this.__commentsTitle.setValue(comments.length + this.tr(" Comments"));
      }

      comments.forEach(comment => {
        const commentUi = new osparc.info.CommentUI(comment);
        this.__commentsList.add(commentUi);
      });
    }
  }
});

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

    this.fetchMessages();
  },

  members: {
    __studyData: null,
    __conversationId: null,
    __nextRequestParams: null,
    __messagesTitle: null,
    __messagesList: null,
    __loadMoreMessages: null,

    __buildLayout: function() {
      this.__messagesTitle = new qx.ui.basic.Label();
      this._add(this.__messagesTitle);

      this.__messagesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        alignY: "middle"
      });
      this._add(this.__messagesList, {
        flex: 1
      });

      this.__loadMoreMessages = new osparc.ui.form.FetchButton(this.tr("Load more messages..."));
      this.__loadMoreMessages.addListener("execute", () => this.fetchMessages(false));
      this._add(this.__loadMoreMessages);

      if (osparc.data.model.Study.canIWrite(this.__studyData["accessRights"])) {
        const addMessages = new osparc.info.CommentAdd(this.__studyData["uuid"], this.__conversationId);
        addMessages.setPaddingLeft(10);
        addMessages.addListener("commentAdded", e => {
          const data = e.getData();
          if (this.__conversationId === null) {
            this.__conversationId = data["conversationId"];
          }
          this.fetchMessages();
        });
        this._add(addMessages);
      }
    },

    fetchMessages: function(removeMessages = true) {
      if (this.__conversationId === null) {
        this.__messagesList.hide();
        this.__loadMoreMessages.hide();
        return;
      }

      this.__loadMoreMessages.show();
      this.__loadMoreMessages.setFetching(true);

      if (removeMessages) {
        this.__messagesList.removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const messages = resp["data"];
          this.__addMessages(messages);
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null) {
            this.__loadMoreMessages.exclude();
          }
        })
        .finally(() => this.__loadMoreMessages.setFetching(false));
    },

    __getNextRequest: function() {
      const params = {
        url: {
          studyId: this.__studyData["uuid"],
          conversationId: this.__conversationId,
          offset: 0,
          limit: 42
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
      return osparc.data.Resources.fetch("conversations", "getMessagesPage", params, options);
    },

    __addMessages: function(messages) {
      if (messages.length === 1) {
        this.__messagesTitle.setValue(this.tr("1 Message"));
      } else if (messages.length > 1) {
        this.__messagesTitle.setValue(messages.length + this.tr(" Messages"));
      }

      messages.forEach(message => {
        const messageUi = new osparc.info.CommentUI(message);
        this.__messagesList.add(messageUi);
      });
    }
  }
});

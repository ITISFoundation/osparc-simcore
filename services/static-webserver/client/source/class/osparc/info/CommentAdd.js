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
    * @param studyData {Object} serialized Study Data
    * @param conversationId {String} Conversation Id
    */
  construct: function(studyData, conversationId = null) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__conversationId = conversationId;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  events: {
    "commentAdded": "qx.event.type.Event"
  },

  members: {
    __studyData: null,
    __conversationId: null,

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
          const authData = osparc.auth.Data.getInstance();
          const myUsername = authData.getUsername();
          const myEmail = authData.getEmail();
          control.set({
            source: osparc.utils.Avatar.emailToThumbnail(myEmail, myUsername, 32)
          });
          const layout = this.getChildControl("add-comment-layout");
          layout.add(control, {
            row: 0,
            column: 0
          });
          break;
        }
        case "comment-field":
          control = new osparc.editor.MarkdownEditor();
          control.getChildControl("buttons").exclude();
          const layout = this.getChildControl("add-comment-layout");
          layout.add(control, {
            row: 0,
            column: 1
          });
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "notify-user-button":
          control = new qx.ui.form.Button(this.tr("Notify user")).set({
            appearance: "form-button",
            allowGrowX: false,
          });
          this.getChildControl("buttons-layout").add(control);
          break;
        case "add-comment-button":
          control = new qx.ui.form.Button(this.tr("Add message")).set({
            appearance: "form-button",
            allowGrowX: false,
          });
          this.getChildControl("buttons-layout").add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("thumbnail");
      this.getChildControl("comment-field");

      const notifyUserButton = this.getChildControl("notify-user-button");
      notifyUserButton.addListener("execute", () => this.__notifyUserTapped());

      const addMessageButton = this.getChildControl("add-comment-button");
      addMessageButton.addListener("execute", () => this.__addComment());
    },

    __notifyUserTapped: function() {
      const showOrganizations = false;
      const showAccessRights = false;
      const recipientsManager = new osparc.share.NewCollaboratorsManager(this.__studyData, showOrganizations, showAccessRights).set({
        acceptOnlyOne: true,
      });
      recipientsManager.setCaption(this.tr("Notify user"));
      recipientsManager.getActionButton().setLabel(this.tr("Notify"));
      recipientsManager.addListener("addCollaborators", e => {
        const data = e.getData();
        const userGids = data["selectedGids"];
        if (userGids && userGids.length) {
          const userGid = parseInt(userGids[0]);
          if (this.__conversationId) {
            this.__postNotify(userGid);
          } else {
            // create new conversation first
            osparc.study.Conversations.addConversation(this.__studyData["uuid"])
              .then(data => {
                this.__conversationId = data["conversationId"];
                this.__postNotify(userGid);
              });
          }
        }
      });
    },

    __addComment: function() {
      if (this.__conversationId) {
        this.__postMessage();
      } else {
        // create new conversation first
        osparc.study.Conversations.addConversation(this.__studyData["uuid"])
          .then(data => {
            this.__conversationId = data["conversationId"];
            this.__postMessage();
          })
      }
    },

    __postMessage: function() {
      const commentField = this.getChildControl("comment-field");
      const comment = commentField.getChildControl("text-area").getValue();
      if (comment) {
        osparc.study.Conversations.addMessage(this.__studyData["uuid"], this.__conversationId, comment)
          .then(data => {
            this.fireDataEvent("commentAdded", data);
            commentField.getChildControl("text-area").setValue("");
          });
      }
    },

    __postNotify: function(userGroupId = 10) {
      if (userGroupId) {
        osparc.study.Conversations.notifyUser(this.__studyData["uuid"], this.__conversationId, userGroupId)
          .then(data => {
            console.log(data);
          });
      }
    },
  }
});

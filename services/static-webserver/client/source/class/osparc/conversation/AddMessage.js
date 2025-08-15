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


qx.Class.define("osparc.conversation.AddMessage", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object} serialized Study Data
    * @param conversationId {String} Conversation Id
    */
  construct: function(studyData, conversationId = null, message = null) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__conversationId = conversationId;
    this.__message = message;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  events: {
    "messageAdded": "qx.event.type.Data",
    "messageUpdated": "qx.event.type.Data",
  },

  members: {
    __studyData: null,
    __conversationId: null,
    __message: null,

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
          control.addListener("keydown", e => {
            if (e.isCtrlPressed() && e.getKeyIdentifier() === "Enter") {
              this.__addComment();
              e.stopPropagation();
              e.preventDefault();
            }
          }, this);
          control.getChildControl("buttons").exclude();
          const layout = this.getChildControl("add-comment-layout");
          layout.add(control, {
            row: 0,
            column: 1
          });
          break;
        case "add-comment-button":
          control = new qx.ui.form.Button(this.tr("Add message")).set({
            appearance: "form-button",
            allowGrowX: false,
            alignX: "right"
          });
          control.setEnabled(osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]));
          this._add(control);
          break;
        case "notify-user-button":
          control = new qx.ui.form.Button("🔔 " + this.tr("Notify user")).set({
            appearance: "form-button",
            allowGrowX: false,
            alignX: "right"
          });
          control.setEnabled(osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("thumbnail");
      const commentField = this.getChildControl("comment-field");

      const addMessageButton = this.getChildControl("add-comment-button");
      if (this.__message) {
        // edit mode
        addMessageButton.setLabel(this.tr("Edit message"));
        addMessageButton.addListener("execute", () => this.__editComment());

        commentField.setText(this.__message["content"]);
      } else {
        // new message
        addMessageButton.addListener("execute", () => this.__addComment());

        const notifyUserButton = this.getChildControl("notify-user-button");
        notifyUserButton.addListener("execute", () => this.__notifyUserTapped());
      }
    },

    __addComment: function() {
      if (this.__conversationId) {
        this.__postMessage();
      } else {
        // create new conversation first
        osparc.store.ConversationsProject.getInstance().addConversation(this.__studyData["uuid"])
          .then(data => {
            this.__conversationId = data["conversationId"];
            this.__postMessage();
          })
      }
    },

    __notifyUserTapped: function() {
      const showOrganizations = false;
      const showAccessRights = false;
      const userManager = new osparc.share.NewCollaboratorsManager(this.__studyData, showOrganizations, showAccessRights).set({
        acceptOnlyOne: true,
      });
      userManager.setCaption(this.tr("Notify user"));
      userManager.getActionButton().setLabel(this.tr("Notify"));
      userManager.addListener("addCollaborators", e => {
        userManager.close();
        const data = e.getData();
        const userGids = data["selectedGids"];
        if (userGids && userGids.length) {
          const userGid = parseInt(userGids[0]);
          this.__notifyUser(userGid);
        }
      });
    },

    __notifyUser: function(userGid) {
      // Note!
      // This check only works if the project is directly shared with the user.
      // If it's shared through a group, it might be a bit confusing
      if (userGid in this.__studyData["accessRights"]) {
        this.__addNotify(userGid);
      } else {
        const msg = this.tr("This user has no access to the project. Do you want to share it?");
        const win = new osparc.ui.window.Confirmation(msg).set({
          caption: this.tr("Share"),
          confirmText: this.tr("Share"),
          confirmAction: "create"
        });
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            const newCollaborators = {
              [userGid]: osparc.data.Roles.STUDY["write"].accessRights
            };
            osparc.store.Study.getInstance().addCollaborators(this.__studyData, newCollaborators)
              .then(() => {
                this.__addNotify(userGid);
                const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators()
                if (userGid in potentialCollaborators && "getUserId" in potentialCollaborators[userGid]) {
                  const uid = potentialCollaborators[userGid].getUserId();
                  osparc.notification.Notifications.pushStudyShared(uid, this.__studyData["uuid"]);
                }
              })
              .catch(err => osparc.FlashMessenger.logError(err));
          }
        }, this);
      }
    },

    __addNotify: function(userGid) {
      if (this.__conversationId) {
        this.__postNotify(userGid);
      } else {
        // create new conversation first
        osparc.store.ConversationsProject.getInstance().addConversation(this.__studyData["uuid"])
          .then(data => {
            this.__conversationId = data["conversationId"];
            this.__postNotify(userGid);
          });
      }
    },

    __postMessage: function() {
      const commentField = this.getChildControl("comment-field");
      const content = commentField.getChildControl("text-area").getValue();
      if (content) {
        osparc.store.ConversationsProject.getInstance().addMessage(this.__studyData["uuid"], this.__conversationId, content)
          .then(data => {
            this.fireDataEvent("messageAdded", data);
            commentField.getChildControl("text-area").setValue("");
          });
      }
    },

    __editComment: function() {
      const commentField = this.getChildControl("comment-field");
      const content = commentField.getChildControl("text-area").getValue();
      if (content) {
        osparc.store.ConversationsProject.getInstance().editMessage(this.__studyData["uuid"], this.__conversationId, this.__message["messageId"], content)
          .then(data => {
            this.fireDataEvent("messageUpdated", data);
            commentField.getChildControl("text-area").setValue("");
          });
      }
    },

    __postNotify: function(userGid) {
      if (userGid) {
        osparc.store.ConversationsProject.getInstance().notifyUser(this.__studyData["uuid"], this.__conversationId, userGid)
          .then(data => {
            this.fireDataEvent("messageAdded", data);
            const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators();
            if (userGid in potentialCollaborators) {
              if ("getUserId" in potentialCollaborators[userGid]) {
                const uid = potentialCollaborators[userGid].getUserId();
                osparc.notification.Notifications.pushConversationNotification(uid, this.__studyData["uuid"]);
              }
              const msg = "getLabel" in potentialCollaborators[userGid] ? potentialCollaborators[userGid].getLabel() + this.tr(" was notified") : this.tr("Notification sent");
              osparc.FlashMessenger.logAs(msg, "INFO");
            }
          });
      }
    },
  }
});

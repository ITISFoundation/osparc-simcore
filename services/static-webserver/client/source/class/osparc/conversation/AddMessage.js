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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  properties: {
    conversationId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeConversationId",
    },

    studyData: {
      check: "Object",
      init: null,
      nullable: true,
      event: "changeStudyData",
      apply: "__applyStudyData",
    },

    message: {
      check: "Object",
      init: null,
      nullable: true,
      event: "changeMessage",
      apply: "__applyMessage",
    }
  },

  events: {
    "messageAdded": "qx.event.type.Data",
    "messageUpdated": "qx.event.type.Data",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
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
          control = osparc.utils.Utils.createThumbnail(32);
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
          control.addListener("execute", this.__addCommentPressed, this);
          this._add(control);
          break;
        case "notify-user-button":
          control = new qx.ui.form.Button("🔔 " + this.tr("Notify user")).set({
            appearance: "form-button",
            allowGrowX: false,
            alignX: "right"
          });
          control.addListener("execute", () => this.__notifyUserTapped());
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("thumbnail");
      this.getChildControl("comment-field");
      this.getChildControl("add-comment-button");
    },

    __applyStudyData: function(studyData) {
      const notifyUserButton = this.getChildControl("notify-user-button");
      if (studyData) {
        const canIWrite = osparc.data.model.Study.canIWrite(studyData["accessRights"])
        this.getChildControl("add-comment-button").setEnabled(canIWrite);
        notifyUserButton.show();
        notifyUserButton.setEnabled(canIWrite);
      } else {
        notifyUserButton.exclude();
      }
    },

    __applyMessage: function(message) {
      if (message) {
        // edit mode
        const commentField = this.getChildControl("comment-field");
        commentField.setText(message["content"]);

        const addMessageButton = this.getChildControl("add-comment-button");
        addMessageButton.setLabel(this.tr("Edit message"));
      }
    },

    __addCommentPressed: function() {
      this.getMessage() ? this.__editComment() : this.__addComment();
    },

    __addComment: function() {
      const conversationId = this.getConversationId();
      if (conversationId) {
        this.__postMessage();
      } else {
        const studyData = this.getStudyData();
        let promise = null;
        if (studyData) {
          // create new project conversation first
          promise = osparc.store.ConversationsProject.getInstance().postConversation(studyData["uuid"])
        } else {
          // support conversation
          const extraContext = {};
          const currentStudy = osparc.store.Store.getInstance().getCurrentStudy()
          if (currentStudy) {
            extraContext["projectId"] = currentStudy.getUuid();
          }
          promise = osparc.store.ConversationsSupport.getInstance().postConversation(extraContext);
        }
        promise
          .then(data => {
            this.setConversationId(data["conversationId"]);
            this.__postMessage();
          });
      }
    },

    __postMessage: function() {
      const commentField = this.getChildControl("comment-field");
      const content = commentField.getChildControl("text-area").getValue();
      let promise = null;
      if (content) {
        const studyData = this.getStudyData();
        const conversationId = this.getConversationId();
        if (studyData) {
          promise = osparc.store.ConversationsProject.getInstance().postMessage(studyData["uuid"], conversationId, content);
        } else {
          promise = osparc.store.ConversationsSupport.getInstance().postMessage(conversationId, content);
        }
        promise
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
        const studyData = this.getStudyData();
        const conversationId = this.getConversationId();
        const message = this.getMessage();
        if (studyData) {
          promise = osparc.store.ConversationsProject.getInstance().editMessage(studyData["uuid"], conversationId, message["messageId"], content);
        } else {
          promise = osparc.store.ConversationsSupport.getInstance().editMessage(conversationId, message["messageId"], content);
        }
        promise.then(data => {
          this.fireDataEvent("messageUpdated", data);
          commentField.getChildControl("text-area").setValue("");
        });
      }
    },

    /* NOTIFY USERS */
    __notifyUserTapped: function() {
      const studyData = this.getStudyData();
      if (!studyData) {
        return;
      }

      const showOrganizations = false;
      const showAccessRights = false;
      const userManager = new osparc.share.NewCollaboratorsManager(studyData, showOrganizations, showAccessRights).set({
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
      const studyData = this.getStudyData();
      if (!studyData) {
        return;
      }

      // Note!
      // This check only works if the project is directly shared with the user.
      // If it's shared through a group, it might be a bit confusing
      if (userGid in studyData["accessRights"]) {
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
            osparc.store.Study.getInstance().addCollaborators(studyData, newCollaborators)
              .then(() => {
                this.__addNotify(userGid);
                const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators()
                if (userGid in potentialCollaborators && "getUserId" in potentialCollaborators[userGid]) {
                  const uid = potentialCollaborators[userGid].getUserId();
                  osparc.notification.Notifications.pushStudyShared(uid, studyData["uuid"]);
                }
              })
              .catch(err => osparc.FlashMessenger.logError(err));
          }
        }, this);
      }
    },

    __addNotify: function(userGid) {
      const studyData = this.getStudyData();
      if (!studyData) {
        return;
      }

      const conversationId = this.getConversationId();
      if (conversationId) {
        this.__postNotify(userGid);
      } else {
        // create new conversation first
        osparc.store.ConversationsProject.getInstance().postConversation(studyData["uuid"])
          .then(data => {
            this.setConversationId(data["conversationId"]);
            this.__postNotify(userGid);
          });
      }
    },

    __postNotify: function(userGid) {
      const studyData = this.getStudyData();
      if (!studyData) {
        return;
      }

      if (userGid) {
        const conversationId = this.getConversationId();
        osparc.store.ConversationsProject.getInstance().notifyUser(studyData["uuid"], conversationId, userGid)
          .then(data => {
            this.fireDataEvent("messageAdded", data);
            const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators();
            if (userGid in potentialCollaborators) {
              if ("getUserId" in potentialCollaborators[userGid]) {
                const uid = potentialCollaborators[userGid].getUserId();
                osparc.notification.Notifications.pushConversationNotification(uid, studyData["uuid"]);
              }
              const msg = "getLabel" in potentialCollaborators[userGid] ? potentialCollaborators[userGid].getLabel() + this.tr(" was notified") : this.tr("Notification sent");
              osparc.FlashMessenger.logAs(msg, "INFO");
            }
          });
      }
    },
    /* NOTIFY USERS */
  }
});

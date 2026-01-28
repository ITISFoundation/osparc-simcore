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
      check: "osparc.data.model.Message",
      init: null,
      nullable: true,
      event: "changeMessage",
      apply: "__applyMessage",
    },

    typing: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeTyping",
    },
  },

  events: {
    "addMessage": "qx.event.type.Data",
    "updateMessage": "qx.event.type.Data",
    "notifyUser": "qx.event.type.Data",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "add-comment-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(0));
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "avatar": {
          control = osparc.utils.Utils.createThumbnail(32);
          const authStore = osparc.auth.Data.getInstance();
          control.set({
            source: authStore.getAvatar(32),
            alignX: "center",
            alignY: "middle",
            marginRight: 8,
          });
          this.getChildControl("add-comment-layout").add(control);
          break;
        }
        case "comment-field": {
          control = new osparc.editor.MarkdownEditor();
          control.addListener("textChanged", () => this.__addCommentPressed(), this);
          control.setCompact(true);
          const textArea = control.getChildControl("text-area");
          textArea.set({
            maxLength: osparc.data.model.Conversation.MAX_CONTENT_LENGTH,
          });
          textArea.addListener("appear", () => {
            textArea.focus();
            textArea.activate();
          });
          [
            "input",
            "changeValue",
          ].forEach(evtName => textArea.addListener(evtName, () => this.setTyping(textArea.getValue().length > 0), this));
          // make it visually connected to the button
          textArea.getContentElement().setStyles({
            "border-top-right-radius": "0px", // no roundness there to match the arrow button
          });
          // make it more compact
          this.getChildControl("add-comment-layout").add(control, {
            flex: 1
          });
          break;
        }
        case "add-comment-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/16").set({
            toolTipText: this.tr("Ctrl+Enter"),
            backgroundColor: "input-background",
            allowGrowX: false,
            alignX: "right",
            alignY: "middle",
          });
          control.getContentElement().setStyles({
            "border-bottom": "1px solid " + qx.theme.manager.Color.getInstance().resolve("default-button-active"),
            "border-top-left-radius": "0px", // no roundness there to match the message field
            "border-bottom-left-radius": "0px", // no roundness there to match the message field
            "border-bottom-right-radius": "0px", // no roundness there to match the message field
          });
          const commentField = this.getChildControl("comment-field").getChildControl("text-area");
          commentField.addListener("focus", () => {
            control.getContentElement().setStyles({
              "border-bottom": "1px solid " + qx.theme.manager.Color.getInstance().resolve("product-color"),
            });
          }, this);
          commentField.addListener("focusout", () => {
            control.getContentElement().setStyles({
              "border-bottom": "1px solid " + qx.theme.manager.Color.getInstance().resolve("default-button-active"),
            });
          }, this);
          control.addListener("execute", this.__addCommentPressed, this);
          this.getChildControl("add-comment-layout").add(control);
          break;
        case "footer-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "no-permission-label":
          control = new qx.ui.basic.Label(this.tr("Only users with write access can add comments.")).set({
            allowGrowX: true,
          });
          this.getChildControl("footer-layout").addAt(control, 0, {
            flex: 1
          });
          break;
        case "notify-user-button":
          control = new qx.ui.form.Button("🔔 " + this.tr("Notify user")).set({
            appearance: "form-button",
            allowGrowX: false,
            alignX: "right",
          });
          control.addListener("execute", () => this.__notifyUserTapped());
          this.getChildControl("footer-layout").addAt(control, 1);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("avatar");
      this.getChildControl("comment-field");
      this.getChildControl("add-comment-button");
    },

    __applyStudyData: function(studyData) {
      const noPermissionLabel = this.getChildControl("no-permission-label");
      const notifyUserButton = this.getChildControl("notify-user-button");
      if (studyData) {
        const canIWrite = osparc.data.model.Study.canIWrite(studyData["accessRights"])
        this.getChildControl("add-comment-button").setEnabled(canIWrite);
        noPermissionLabel.setVisibility(canIWrite ? "hidden" : "visible");
        notifyUserButton.show();
        notifyUserButton.setEnabled(canIWrite);
      } else {
        noPermissionLabel.hide();
        notifyUserButton.exclude();
      }
    },

    __applyMessage: function(message) {
      if (message) {
        // edit mode
        const commentField = this.getChildControl("comment-field");
        commentField.setText(message.getContent());
      }
    },

    __addCommentPressed: function() {
      this.getMessage() ? this.__editComment() : this.addComment();
    },

    addComment: function() {
      const commentField = this.getChildControl("comment-field");
      const content = commentField.getChildControl("text-area").getValue();
      if (content) {
        this.fireDataEvent("addMessage", content);
        commentField.getChildControl("text-area").setValue("");
      }
    },

    __editComment: function() {
      const commentField = this.getChildControl("comment-field");
      const content = commentField.getChildControl("text-area").getValue();
      if (content) {
        this.fireDataEvent("updateMessage", content);
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
        this.__doNotifyUser(userGid);
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
                this.__doNotifyUser(userGid);
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

    __doNotifyUser: function(userGid) {
      const studyData = this.getStudyData();
      if (!studyData) {
        return;
      }

      this.fireDataEvent("notifyUser", userGid);
    },
    /* NOTIFY USERS */
  }
});

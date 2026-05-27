/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.support.ConversationOptionsMenu", {
  extend: qx.ui.menu.Menu,

  construct: function() {
    this.base(arguments);

    this.set({
      appearance: "menu-wider",
      position: "bottom-left",
    });
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: true,
      event: "changeConversation",
      apply: "__applyConversation",
    },
  },

  members: {
    __archivedListenerId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "rename-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/i-cursor/12",
            label: this.tr("Rename..."),
          });
          control.addListener("execute", () => this.__renameConversation());
          this.add(control);
          break;
        case "open-project-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/external-link-alt/12",
            label: this.tr("Project details"),
          });
          control.addListener("execute", () => this.__openProjectDetails());
          this.add(control);
          break;
        case "copy-ticket-id-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/copy/12",
            label: this.tr("Copy Ticket ID"),
          });
          control.addListener("execute", () => this.__copyTicketId());
          this.add(control);
          break;
        case "archive-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/archive/12",
            label: this.tr("Archive"),
          });
          control.addListener("execute", () => this.__toggleArchive());
          this.add(control);
          break;
        case "delete-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/trash-alt/12",
            label: this.tr("Delete"),
          });
          control.addListener("execute", () => this.__deleteConversation());
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyConversation: function(conversation, oldConversation) {
      if (oldConversation && this.__archivedListenerId) {
        oldConversation.removeListenerById(this.__archivedListenerId);
        this.__archivedListenerId = null;
      }

      if (!conversation) {
        return;
      }

      this.getChildControl("rename-button");

      const openProjectButton = this.getChildControl("open-project-button");
      const projectId = conversation.getContextProjectId();
      openProjectButton.setVisibility(projectId ? "visible" : "excluded");
      if (projectId) {
        osparc.store.Study.getInstance().getOne(projectId)
          .then(() => openProjectButton.setEnabled(true))
          .catch(() => openProjectButton.setEnabled(false));
      }

      this.getChildControl("copy-ticket-id-button");

      const amISupporter = osparc.store.Groups.getInstance().amIASupportUser();
      if (amISupporter) {
        const archiveButton = this.getChildControl("archive-button");
        this.__updateArchiveButton(archiveButton, conversation.getArchived());
        this.__archivedListenerId = conversation.addListener("changeArchived", e => {
          this.__updateArchiveButton(archiveButton, e.getData());
        });
      }

      const amIOwner = conversation.amIOwner();
      if (amIOwner) {
        this.getChildControl("delete-button");
      }
    },

    __updateArchiveButton: function(button, isArchived) {
      if (isArchived) {
        button.set({
          icon: "@FontAwesome5Solid/box-open/12",
          label: this.tr("Unarchive"),
        });
      } else {
        button.set({
          icon: "@FontAwesome5Solid/archive/12",
          label: this.tr("Archive"),
        });
      }
    },

    __renameConversation: function() {
      const conversation = this.getConversation();
      let oldName = conversation.getName() || "";
      const title = this.tr("Rename Conversation");
      const supportCenter = osparc.ui.window.SingletonWindow.getWindowById("support-center");
      const renamer = new osparc.widget.Renamer(oldName, null, title, supportCenter).set({
        maxChars: osparc.data.model.Conversation.MAX_TITLE_LENGTH,
      });
      renamer.addListener("labelChanged", e => {
        renamer.close();
        const newLabel = e.getData()["newLabel"];
        conversation.renameConversation(newLabel);
      }, this);
      renamer.center();
      renamer.open();
    },

    __openProjectDetails: function() {
      const projectId = this.getConversation().getContextProjectId();
      if (projectId) {
        osparc.store.Study.getInstance().getOne(projectId)
          .then(studyData => {
            if (studyData) {
              const studyDataCopy = osparc.data.model.Study.deepCloneStudyObject(studyData);
              studyDataCopy["resourceType"] = "study";
              osparc.dashboard.ResourceDetails.popUpInWindow(studyDataCopy);
            }
          })
          .catch(err => console.warn(err));
      }
    },

    __copyTicketId: function() {
      const conversation = this.getConversation();
      if (conversation) {
        osparc.utils.Utils.copyTextToClipboard(conversation.getConversationId());
      }
    },

    __toggleArchive: function() {
      const conversation = this.getConversation();
      conversation.archiveConversation(!conversation.getArchived());
    },

    __deleteConversation: function() {
      const conversation = this.getConversation();
      const win = new osparc.ui.window.Confirmation(this.tr("Delete conversation?")).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete",
      });
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          osparc.store.ConversationsSupport.getInstance().deleteConversation(conversation.getConversationId())
            .catch(err => osparc.FlashMessenger.logError(err));
        }
      });
    },
  },
});

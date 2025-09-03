/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.support.ConversationPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-button");

    const conversation = this.getChildControl("conversation-content");
    this.bind("conversation", conversation, "conversation");
    conversation.bind("conversation", this, "conversation");
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

  events: {
    "showConversations": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversation-header-layout": {
          const headerLayout = new qx.ui.layout.HBox(5).set({
            alignY: "middle",
          })
          control = new qx.ui.container.Composite(headerLayout).set({
            padding: 5,
          });
          this._add(control);
          break;
        }
        case "back-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Return to Messages"),
            icon: "@FontAwesome5Solid/arrow-left/16",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.fireEvent("showConversations"));
          this.getChildControl("conversation-header-layout").addAt(control, 0);
          break;
        case "conversation-header-center-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("conversation-header-layout").addAt(control, 1, {
            flex: 1,
          });
          break;
        case "conversation-title":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
            allowGrowX: true,
            });
          this.getChildControl("conversation-header-center-layout").addAt(control, 0);
          break;
        case "conversation-extra-content":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            textColor: "text-disabled",
            rich: true,
            allowGrowX: true,
            selectable: true,
          });
          this.getChildControl("conversation-header-center-layout").addAt(control, 1);
          break;
        case "open-project-button":
          control = new qx.ui.form.Button().set({
            maxWidth: 26,
            maxHeight: 24,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/external-link-alt/12",
          });
          control.addListener("execute", () => this.__openProjectDetails());
          this.getChildControl("conversation-header-layout").addAt(control, 2);
          break;
        case "conversation-options": {
          control = new qx.ui.form.MenuButton().set({
            maxWidth: 24,
            maxHeight: 24,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/12",
          });
          const menu = new qx.ui.menu.Menu().set({
            position: "bottom-right",
          });
          control.setMenu(menu);
          const renameButton = new qx.ui.menu.Button().set({
            label: this.tr("Rename"),
            icon: "@FontAwesome5Solid/i-cursor/10"
          });
          renameButton.addListener("execute", () => this.__renameConversation());
          menu.add(renameButton);
          this.getChildControl("conversation-header-layout").addAt(control, 3);
          break;
        }
        case "conversation-content":
          control = new osparc.support.Conversation();
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this._add(scroll, {
            flex: 1,
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyConversation: function(conversation) {
      const title = this.getChildControl("conversation-title");
      if (conversation) {
        conversation.bind("nameAlias", title, "value");
      } else {
        title.setValue(this.tr("Ask a Question"));
      }

      const extraContextLabel = this.getChildControl("conversation-extra-content");
      if (conversation) {
        const amISupporter = osparc.store.Products.getInstance().amIASupportUser();
        conversation.bind("extraContext", extraContextLabel, "value", {
          converter: extraContext => {
            let extraContextText = "";
            if (extraContext && Object.keys(extraContext).length) {
              extraContextText = `Ticket ID: ${conversation.getConversationId()}`;
              const contextProjectId = conversation.getContextProjectId();
              if (contextProjectId && amISupporter) {
                extraContextText += `<br>Project ID: ${contextProjectId}`;
              }
              const appointment = conversation.getAppointment();
              if (appointment) {
                extraContextText += "<br>Appointment: ";
                if (appointment === "requested") {
                  // still pending
                  extraContextText += appointment;
                } else {
                  // already set
                  extraContextText += osparc.utils.Utils.formatDateAndTime(appointment);
                }
              }
            }
            return extraContextText;
          }
        });
        extraContextLabel.bind("value", extraContextLabel, "visibility", {
          converter: extraContext => {
            return extraContext ? "visible" : "excluded";
          }
        });
      } else {
        extraContextLabel.exclude();
      }

      const openButton = this.getChildControl("open-project-button");
      if (conversation && conversation.getContextProjectId()) {
        openButton.show();
      } else {
        openButton.exclude();
      }

      const options = this.getChildControl("conversation-options");
      if (conversation && conversation.amIOwner()) {
        options.show();
      } else {
        options.exclude();
      }
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

    __renameConversation: function() {
      let oldName = this.getConversation().getName();
      if (oldName === "null") {
        oldName = "";
      }
      const renamer = new osparc.widget.Renamer(oldName);
      renamer.addListener("labelChanged", e => {
        renamer.close();
        const newLabel = e.getData()["newLabel"];
        this.getConversation().renameConversation(newLabel);
      }, this);
      renamer.center();
      renamer.open();
    },

    __getAddMessageField: function() {
      return this.getChildControl("conversation-content") &&
        this.getChildControl("conversation-content").getChildControl("add-message");
    },

    postMessage: function(message) {
      const addMessage = this.__getAddMessageField();
      if (addMessage && addMessage.getChildControl("comment-field")) {
        addMessage.getChildControl("comment-field").setText(message);
        return addMessage.addComment();
      }
      return Promise.reject();
    },
  }
});

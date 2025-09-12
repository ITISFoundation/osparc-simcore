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
        case "conversation-extra-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));
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
        case "set-appointment-button": {
          control = new qx.ui.form.Button().set({
            maxWidth: 26,
            maxHeight: 24,
            padding: [0, 6],
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/clock/12",
          });
          control.addListener("execute", () => this.__openAppointmentDetails());
          this.getChildControl("conversation-header-layout").addAt(control, 3);
          break;
        }
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
          this.getChildControl("conversation-header-layout").addAt(control, 4);
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

    // type can be "askAQuestion", "bookACall" or "reportOEC"
    proposeConversation: function(type) {
      type = type || "askAQuestion";
      this.setConversation(null);
      this.clearAllMessages();

      const title = this.getChildControl("conversation-title");
      const conversationContent = this.getChildControl("conversation-content");
      let msg = "Hi " + osparc.auth.Data.getInstance().getUserName() + ",";
      switch(type) {
        case "askAQuestion":
          title.setValue(this.tr("Ask a Question"));
          msg += "\nHave a question or feedback?\nWe are happy to assist!";
          break;
        case "bookACall":
          title.setValue(this.tr("Book a Call"));
          msg += "\nLet us know what your availability is and we will get back to you shortly to schedule a meeting.";
          break;
        case "reportOEC":
          title.setValue(this.tr("Report an Error"));
          msg = null;
          break;
      }
      if (msg) {
        conversationContent.addSystemMessage(msg);
      }
    },

    __applyConversation: function(conversation) {
      const title = this.getChildControl("conversation-title");
      if (conversation) {
        conversation.bind("nameAlias", title, "value");
      }

      const extraContextLayout = this.getChildControl("conversation-extra-layout");
      extraContextLayout.removeAll();
      if (conversation) {
        const amISupporter = osparc.store.Groups.getInstance().amIASupportUser();

        const createExtraContextLabel = text => {
          return new qx.ui.basic.Label(text).set({
            font: "text-12",
            textColor: "text-disabled",
            rich: true,
            allowGrowX: true,
            selectable: true,
          });
        };
        const updateExtraContext = () => {
          extraContextLayout.removeAll();
          const extraContext = conversation.getExtraContext();
          if (extraContext && Object.keys(extraContext).length) {
            const ticketIdLabel = createExtraContextLabel(`Ticket ID: ${conversation.getConversationId()}`);
            extraContextLayout.add(ticketIdLabel);
            const contextProjectId = conversation.getContextProjectId();
            if (contextProjectId && amISupporter) {
              const projectIdLabel = createExtraContextLabel(`Project ID: ${contextProjectId}`);
              extraContextLayout.add(projectIdLabel);
            }
            /*
            const appointment = conversation.getAppointment();
            if (appointment) {
              const appointmentLabel = createExtraContextLabel();
              let appointmentText = "Appointment: ";
              if (appointment === "requested") {
                // still pending
                appointmentText += appointment;
              } else {
                // already set
                appointmentText += osparc.utils.Utils.formatDateAndTime(new Date(appointment));
                appointmentLabel.set({
                  cursor: "pointer",
                  toolTipText: osparc.utils.Utils.formatDateWithCityAndTZ(new Date(appointment)),
                });
              }
              appointmentLabel.setValue(appointmentText);
              extraContextLayout.add(appointmentLabel);
            }
            */
          }
        };
        updateExtraContext();
        conversation.addListener("changeExtraContext", () => updateExtraContext(), this);
      }

      const openProjectButton = this.getChildControl("open-project-button");
      if (conversation && conversation.getContextProjectId()) {
        openProjectButton.show();
      } else {
        openProjectButton.exclude();
      }

      const options = this.getChildControl("conversation-options");
      if (conversation) {
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

    __openAppointmentDetails: function() {
      const win = new osparc.widget.DateTimeChooser();
      win.addListener("dateChanged", e => {
        const newValue = e.getData()["newValue"];
        this.getConversation().setAppointment(newValue)
          .catch(err => console.error(err));
        win.close();
      }, this);
      win.open();
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

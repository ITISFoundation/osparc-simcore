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

qx.Class.define("osparc.po.SendEmail", {
  extend: osparc.po.BaseView,

  construct: function() {
    this.base(arguments);

    this.__selectedGroupIds = [];
  },

  members: {
    __selectedGroupIds: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "email-template-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle",
          })).set({
            marginBottom: 20,
          });
          this._add(control);
          break;
        }
        case "email-template-helper": {
          control = new qx.ui.basic.Label(this.tr("Select email template"));
          this.getChildControl("email-template-container").add(control);
          break;
        }
        case "email-template-selector": {
          control = new qx.ui.form.SelectBox().set({
            width: 200,
            allowGrowX: false,
          });
          control.addListener("changeSelection", e => {
            const selectedItem = e.getData()[0];
            const templateId = selectedItem.getModel();
            this.__templateSelected(templateId);
          }, this);
          this.getChildControl("email-template-container").add(control);
          break;
        }
        case "form-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Grid(10, 5));
          control.getLayout().setColumnFlex(1, 1);
          this._add(control);
          break;
        }
        case "recipients-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6).set({
            alignY: "middle",
          })).set({
            backgroundColor: "input-background",
            height: 26,
            marginBottom: 5,
          });
          const formContainer = this.getChildControl("form-container");
          formContainer.add(new qx.ui.basic.Label(this.tr("To")).set({
            paddingTop: 5,
          }), {
            row: 0,
            column: 0
          });
          formContainer.add(control, {
            row: 0,
            column: 1
          });
          break;
        }
        case "add-recipient-button": {
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/plus/12").set({
            allowGrowX: false,
            allowGrowY: true,
            toolTipText: this.tr("Add Recipient"),
          });
          control.addListener("execute", () => this.__openCollaboratorsManager(), this);
          this.getChildControl("recipients-container").add(control);
          break;
        }
        case "recipients-chips": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(4, 4).set({
            alignY: "middle",
          }));
          this.getChildControl("recipients-container").add(control, {
            flex: 1
          });
          break;
        }
        case "subject-field": {
          control = new qx.ui.form.TextField().set({
            marginBottom: 10
          });
          const formContainer = this.getChildControl("form-container");
          formContainer.add(new qx.ui.basic.Label(this.tr("Subject")).set({
            paddingTop: 5,
          }), {
            row: 1,
            column: 0
          });
          formContainer.add(control, {
            row: 1,
            column: 1
          });
          break;
        }
        case "email-editor-and-preview": {
          control = new osparc.editor.EmailEditor();
          const container = new qx.ui.container.Scroll();
          container.add(control);
          this._add(container, {
            flex: 1
          });
          break;
        }
        case "button-bar": {
          const layout = new qx.ui.layout.HBox(10);
          layout.setAlignX("right");
          control = new qx.ui.container.Composite(layout).set({
            padding: 10
          });
          this._add(control);
          break;
        }
        case "send-email-button":
          control = new osparc.ui.form.FetchButton(this.tr("Send")).set({
            appearance: "strong-button",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__sendEmailClicked(), this);
          this.getChildControl("button-bar").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("email-template-helper");
      const selectBox = this.getChildControl("email-template-selector");
      this.getChildControl("add-recipient-button");
      this.getChildControl("recipients-chips");
      this.getChildControl("subject-field");
      this.getChildControl("email-editor-and-preview");
      this.getChildControl("send-email-button");

      this.__populateEmailTemplates(selectBox);
    },

    __populateEmailTemplates: function(selectBox) {
      osparc.message.Messages.fetchEmailTemplates()
        .then(templates => {
          templates.forEach(template => {
            const templateName = template["ref"]["templateName"];
            const item = new qx.ui.form.ListItem(templateName);
            selectBox.add(item);
          });
          if (templates.length) {
            const firstItem = selectBox.getChildren()[0];
            selectBox.setSelection([firstItem]);
            this.__templateSelected(firstItem.getLabel());
          }
        });
    },

    __templateSelected: function(templateId) {
      if (!templateId) return;
      osparc.message.Messages.fetchEmailPreview(templateId)
        .then(template => {
          const subjectField = this.getChildControl("subject-field");
          subjectField.setValue(template["messageContent"]["subject"]);
          const emailEditor = this.getChildControl("email-editor-and-preview");
          emailEditor.setTemplateEmail(template["messageContent"]["body"]["html"]);
        });
    },

    __openCollaboratorsManager: function() {
      const data = {
        resourceType: "emailRecipients",
      };
      const collaboratorsManager = new osparc.share.NewCollaboratorsManager(data, true, false);
      collaboratorsManager.getActionButton().setLabel(this.tr("Add"));
      collaboratorsManager.addListener("addCollaborators", e => {
        const data = e.getData();
        const selectedGids = data.selectedGids;
        selectedGids.forEach(gid => {
          if (!this.__selectedGroupIds.includes(gid)) {
            this.__selectedGroupIds.push(gid);
          }
        });
        this.__updateRecipientsChips();
        collaboratorsManager.close();
      }, this);
    },

    __updateRecipientsChips: function() {
      const chipsContainer = this.getChildControl("recipients-chips");
      chipsContainer.removeAll();
      const groupsStore = osparc.store.Groups.getInstance();
      this.__selectedGroupIds.forEach((gid, index) => {
        const group = groupsStore.getGroup(gid);
        const chip = new qx.ui.basic.Atom(group.getLabel(), "@FontAwesome5Solid/times/10").set({
          toolTipText: group.getDescription(),
          padding: [2, 8],
          decorator: "chip",
          cursor: "pointer",
          iconPosition: "right",
          gap: 8,
          allowGrowY: true,
          backgroundColor: "background-main-3",
        });
        chip.addListener("tap", () => {
          this.__selectedGroupIds.splice(index, 1);
          this.__updateRecipientsChips();
        }, this);
        chipsContainer.add(chip);
      });
    },

    __sendEmailClicked: function() {
      // make sure at least one recipient is selected
      if (!this.__selectedGroupIds.length) {
        osparc.FlashMessenger.logAs(this.tr("Please select at least one recipient"), "WARNING");
        return;
      }

      // make sure subject is not empty
      const subjectField = this.getChildControl("subject-field");
      if (!subjectField.getValue()) {
        osparc.FlashMessenger.logAs(this.tr("Please enter a subject"), "WARNING");
        return;
      }

      // if the user is not in the preview page, force them there so they can see the final email before sending
      const previewPage = this.getChildControl("email-editor-and-preview").getChildControl("preview-page");
      if (!previewPage.isVisible()) {
        const tabView = previewPage.getLayoutParent().getLayoutParent();
        tabView.setSelection([previewPage]);
        osparc.FlashMessenger.logAs(this.tr("Please preview the email before sending"), "WARNING");
        return;
      }

      this.__sendEmail();
    },

    __sendEmail: function() {
      const sending = () => {
        this.setEnabled(false);
        this.getChildControl("send-email-button").setFetching(true);
      }

      const notSending = () => {
        this.setEnabled(true);
        this.getChildControl("send-email-button").setFetching(false);
      }

      sending();

      const subjectField = this.getChildControl("subject-field");
      const subject = subjectField.getValue();
      const emailEditor = this.getChildControl("email-editor-and-preview");
      const bodyHtml = emailEditor.composeWholeHtml();
      const bodyText = emailEditor.getBodyText();
      const sendMessagePromise = osparc.message.Messages.sendMessage(this.__selectedGroupIds, subject, bodyHtml, bodyText);
      const pollTasks = osparc.store.PollTasks.getInstance();
      pollTasks.createPollingTask(sendMessagePromise)
        .then(task => {
          task.addListener("resultReceived", () => {
            osparc.FlashMessenger.logAs(this.tr("Email sent successfully"), "INFO");
            notSending();
          });
          task.addListener("pollingError", e => {
            osparc.FlashMessenger.logError(e.getData());
            notSending();
          });
        })
        .catch(err => {
          const errorMsg = err.message || this.tr("An error occurred while sending the test email");
          osparc.FlashMessenger.logError(errorMsg);
          notSending();
        });
    },
  }
});

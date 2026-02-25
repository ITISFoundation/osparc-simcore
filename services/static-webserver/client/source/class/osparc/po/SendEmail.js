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

  members: {
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
        case "email-editor": {
          control = new osparc.po.EmailEditor();
          this._add(control, {
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
      this.getChildControl("email-editor");
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
          const emailEditor = this.getChildControl("email-editor");
          const subjectField = emailEditor.getChildControl("subject-field");
          subjectField.setValue(template["messageContent"]["subject"]);
          const emailContentEditor = emailEditor.getChildControl("email-content-editor-and-preview");
          emailContentEditor.setTemplateEmail(template["messageContent"]["bodyHtml"]);
        });
    },

    __sendEmailClicked: function() {
      const emailEditor = this.getChildControl("email-editor");
      const selectedGroupIds = emailEditor.getSelectedGroupIds();
      // make sure at least one recipient is selected
      if (!selectedGroupIds.length) {
        osparc.FlashMessenger.logAs(this.tr("Please select at least one recipient"), "WARNING");
        return;
      }

      // make sure subject is not empty
      const subjectField = emailEditor.getChildControl("subject-field");
      if (!subjectField.getValue()) {
        osparc.FlashMessenger.logAs(this.tr("Please enter a subject"), "WARNING");
        return;
      }

      // if the user is not in the preview page, force them there so they can see the final email before sending
      const previewPage = emailEditor.getChildControl("email-content-editor-and-preview").getChildControl("preview-page");
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

      const emailEditor = this.getChildControl("email-editor");
      const selectedGroupIds = emailEditor.getSelectedGroupIds();
      const subjectField = emailEditor.getChildControl("subject-field");
      const subject = subjectField.getValue();
      const emailContentEditor = emailEditor.getChildControl("email-content-editor-and-preview");
      const bodyHtml = emailContentEditor.composeWholeHtml();
      const bodyText = emailContentEditor.getBodyText();
      const sendMessagePromise = osparc.message.Messages.sendMessage(selectedGroupIds, subject, bodyHtml, bodyText);
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

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo-Valero (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.PreRegistration", {
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-preregistration":
          control = this.__searchPreRegistration();
          this._add(control);
          break;
        case "finding-status":
          control = new qx.ui.basic.Label().set({
            rich: true
          });
          this._add(control);
          break;
        case "pre-registration-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("search-preregistration");
      this.getChildControl("finding-status");
      this.getChildControl("pre-registration-container");
    },

    __searchPreRegistration: function() {
      const groupBox = osparc.po.BaseView.createGroupBox(this.tr("Pre-Registration"));
      const form = this.__preRegistrationForm();
      const formRenderer = new qx.ui.form.renderer.Single(form);
      groupBox.add(formRenderer);

      return groupBox;
    },

    __preRegistrationForm: function() {
      const form = new qx.ui.form.Form();
      const requestAccountData = new qx.ui.form.TextArea().set({
        required: true,
        minHeight: 200,
        placeholder: this.tr("Copy&Paste the Request Account Form in JSON format here ...")
      });
      form.add(requestAccountData, this.tr("Request Form"));

      const submitBtn = new osparc.ui.form.FetchButton(this.tr("Submit"));
      submitBtn.set({
        appearance: "form-button"
      });

      submitBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.users.pre-register", true)) {
          return;
        }
        if (form.validate()) {
          submitBtn.setFetching(true);

          const flashErrorMsg = this.tr("Pre-Registration Failed. See details below");
          const findingStatus = this.getChildControl("finding-status");
          findingStatus.setValue(this.tr("Searching Pre-Registered users..."));

          let params;
          try {
            params = {
              data: JSON.parse(requestAccountData.getValue())
            };
          } catch (err) {
            console.error(err);

            const detailErrorMsg = `Error parsing Request Form JSON. ${err}`;
            findingStatus.setValue(detailErrorMsg);

            osparc.FlashMessenger.logAs(flashErrorMsg, "ERROR");
            submitBtn.setFetching(false);
            return
          }

          osparc.data.Resources.fetch("poUsers", "preRegister", params)
            .then(data => {
              if (data.length) {
                findingStatus.setValue(this.tr("Pre-Registered as:"));
              } else {
                findingStatus.setValue(this.tr("No Pre-Registered user found"));
              }
              this.__populatePreRegistrationLayout(data);
            })
            .catch(err => {
              const detailErrorMsg = this.tr(`Error during Pre-Registeristration: ${err.message}`)
              findingStatus.setValue(detailErrorMsg);
              console.error(err);
              osparc.FlashMessenger.logAs(flashErrorMsg, "ERROR");
            })
            .finally(() => submitBtn.setFetching(false));
        }
      }, this);
      form.addButton(submitBtn);

      return form;
    },

    __populatePreRegistrationLayout: function(respData) {
      const preRegistrationContainer = this.getChildControl("pre-registration-container");
      const preregistrationRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "preregistration-data");
      preRegistrationContainer.add(preregistrationRespViewer);
    }
  }
});

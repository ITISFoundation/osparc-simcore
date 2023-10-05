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

qx.Class.define("osparc.auth.ui.RequestAccount", {
  extend: osparc.auth.core.BaseAuthPage,


  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
    __requestButton: null,
    __cancelButton: null,

    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Request Account"));

      const firstName = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("First Name")
      });
      this.add(firstName);

      const lastName = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Last Name")
      });
      this.add(lastName);

      const email = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Email")
      });
      this.add(email);

      const phone = new qx.ui.form.TextField().set({
        placeholder: this.tr("Phone Number")
      });
      this.add(phone);

      const company = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Company/University Name")
      });
      this.add(company);

      const address = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Address")
      });
      this.add(address);

      const country = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Country")
      });
      this.add(country);

      const application = new qx.ui.form.SelectBox().set({
        required: true
      });
      [{
        id: "Antenna_Design",
        label: "Antenna Design"
      }, {
        id: "MRI_System_Design_and_Optimization",
        label: "MRI System Design and Optimization"
      }, {
        id: "MRI_Implant_Safety",
        label: "MRI Implant Safety"
      }, {
        id: "MRI_Safety",
        label: "MRI Safety"
      }, {
        id: "Focused_Ultrasound",
        label: "Focused Ultrasound"
      }, {
        id: "EM-induced_Neuronal_Dynamics",
        label: "EM-induced Neuronal Dynamics"
      }, {
        id: "Thermal_Therapies",
        label: "Thermal Therapies"
      }, {
        id: "Wireless_Body_Area_Networks",
        label: "Wireless Body Area Networks"
      }, {
        id: "Wireless_Power_Transfer",
        label: "Wireless Power Transfer"
      }, {
        id: "Other",
        label: "Other (please specify below)"
      }].forEach(appData => {
        const lItem = new qx.ui.form.ListItem(appData.label, null, appData.id);
        application.add(lItem);
      });
      this.add(application, null, "Application");

      const description = new qx.ui.form.TextField().set({
        placeholder: this.tr("Description")
      });
      this.add(description);

      const hear = new qx.ui.form.SelectBox().set({
        required: true
      });
      [{
        id: "Search_Engine",
        label: "Search Engine"
      }, {
        id: "Conference",
        label: "Conference"
      }, {
        id: "Publication",
        label: "Publication"
      }, {
        id: "Social_Media",
        label: "Social Media"
      }, {
        id: "Other",
        label: "Other (please specify below)"
      }].forEach(hearData => {
        const lItem = new qx.ui.form.ListItem(hearData.label, null, hearData.id);
        hear.add(lItem);
      });
      this.add(hear, null, "How did you hear about us?");

      const message = new qx.ui.form.TextField().set({
        placeholder: this.tr("Message")
      });
      this.add(message);

      // validation
      const validator = new qx.ui.form.validation.Manager();
      validator.add(email, qx.util.Validate.email());

      // submit & cancel buttons
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const submitBtn = this.__requestButton = new qx.ui.form.Button(this.tr("Request")).set({
        center: true,
        appearance: "strong-button"
      });
      osparc.utils.Utils.setIdToWidget(submitBtn, "registrationSubmitBtn");
      grp.add(submitBtn, {
        flex:1
      });

      const cancelBtn = this.__cancelButton = new qx.ui.form.Button(this.tr("Cancel"));
      grp.add(cancelBtn, {
        flex:1
      });

      // interaction
      submitBtn.addListener("execute", e => {
        const valid = validator.validate();
        if (valid) {
          const formData = {
            email: email.getValue()
          };
          this.__submit(formData);
        }
      }, this);

      cancelBtn.addListener("execute", () => this.fireDataEvent("done", null), this);

      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });

      this.add(grp);
    },

    __submit: function(formData) {
      console.log(formData);
      /*
      osparc.auth.Manager.getInstance().register(formData)
        .then(log => {
          this.fireDataEvent("done", log.message);
          osparc.FlashMessenger.getInstance().log(log);
        })
        .catch(err => {
          const msg = err.message || this.tr("Cannot register user");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
      */
    },

    _onAppear: function() {
      // Listen to "Enter" key
      const commandEnter = new qx.ui.command.Command("Enter");
      this.__requestButton.setCommand(commandEnter);

      // Listen to "Esc" key
      const commandEsc = new qx.ui.command.Command("Esc");
      this.__cancelButton.setCommand(commandEsc);
    },

    _onDisappear: function() {
      this.__requestButton.setCommand(null);
      this.__cancelButton.setCommand(null);
    }
  }
});

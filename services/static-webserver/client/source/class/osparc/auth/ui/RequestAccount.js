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

      const doubleSpaced = [];

      // form
      const firstName = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(firstName, this.tr("First Name"), null, "firstName");

      this.addListener("appear", () => {
        firstName.focus();
        firstName.activate();
      });

      const lastName = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(lastName, this.tr("Last Name"), null, "lastName");

      const email = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(email, this.tr("Email"), qx.util.Validate.email(), "email");

      const phone = new qx.ui.form.TextField();
      this._form.add(phone, this.tr("Phone Number"), null, "phone");

      if (
        osparc.product.Utils.isProduct("s4lacad") ||
        osparc.product.Utils.isProduct("s4ldektopacad")
      ) {
        const university = new qx.ui.form.TextField().set({
          required: true
        });
        doubleSpaced.push(university);
        this._form.add(university, this.tr("University"), null, "university");
      } else {
        const company = new qx.ui.form.TextField().set({
          required: true
        });
        doubleSpaced.push(company);
        this._form.add(company, this.tr("Company Name"), null, "company");
      }

      const address = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(address, this.tr("Address"), null, "address");

      const country = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(country, this.tr("Country"), null, "country");

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
      this._form.add(application, this.tr("Application"), null, "application");

      const description = new qx.ui.form.TextField();
      doubleSpaced.push(description);
      this._form.add(description, this.tr("Description"), null, "description");

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
      doubleSpaced.push(hear);
      this._form.add(hear, this.tr("How did you hear about us?"), null, "hear");

      const message = new qx.ui.form.TextField();
      doubleSpaced.push(message);
      this._form.add(message, this.tr("Message"), null, "message");

      // const formRenderer = new qx.ui.form.renderer.Single(this._form);
      const formRenderer = new osparc.ui.form.renderer.DoubleV(this._form, doubleSpaced);
      this.add(formRenderer);

      // buttons
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
        const valid = this._form.validate();
        if (valid) {
          const formData = {};
          Object.entries(this._form.getItems()).forEach(([key, field]) => {
            const val = field.getValue();
            if (val && (typeof val === "object") && ("classname" in val)) {
              formData[key] = val.getModel();
            } else {
              formData[key] = val;
            }
          });
          this.__submit(formData);
        }
      }, this);

      cancelBtn.addListener("execute", () => this.fireDataEvent("done", null), this);

      this.add(grp);
    },

    __submit: function(formData) {
      console.log(formData);
      const msg = this.tr("The request is being processed, you will here from us in the coming hours");
      osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
      this.fireDataEvent("done");
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

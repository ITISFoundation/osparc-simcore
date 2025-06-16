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

/**
 * @asset(osparc/denylist.json")
 */

qx.Class.define("osparc.auth.ui.RequestAccount", {
  extend: osparc.auth.core.BaseAuthPage,

  members: {
    __captchaField: null,
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
      switch (osparc.product.Utils.getProductName()) {
        case "s4lacad":
        case "s4ldesktopacad":
        case "tiplite": {
          this._form.add(email, this.tr("University Email"), null, "email");
          let validator = qx.util.Validate.email();
          osparc.utils.Utils.fetchJSON("/resource/osparc/denylist.json")
            .then(denylistData => {
              if ("lite" in denylistData) {
                const denylist = denylistData["lite"];
                validator = osparc.auth.core.Utils.denylistEmailValidator(denylist);
              }
            })
            .catch(console.error)
            .finally(() => {
              this._form.getValidationManager().add(email, validator);
            });
          break;
        }
        default:
          this._form.add(email, this.tr("Email"), qx.util.Validate.email(), "email");
          break;
      }

      const phone = new qx.ui.form.TextField();
      this._form.add(phone, this.tr("Phone Number"), null, "phone");


      const organization = new qx.ui.form.TextField();
      doubleSpaced.push(organization);
      switch (osparc.product.Utils.getProductName()) {
        case "s4l":
          this._form.add(organization, this.tr("Company Name"), null, "company");
          organization.setRequired(true);
          break;
        case "s4lacad":
        case "s4ldesktopacad":
          this._form.add(organization, this.tr("University"), null, "university");
          organization.setRequired(true);
          break;
        case "tiplite":
          this._form.add(organization, this.tr("University"), null, "university");
          break;
        case "tis":
          this._form.add(organization, this.tr("Organization"), null, "organization");
          break;
        case "osparc":
          this._form.add(organization, this.tr("Research Group/Organization"), null, "organization");
          break;
      }


      const address = new qx.ui.form.TextField().set({
        required: true
      });
      doubleSpaced.push(address);
      this._form.add(address, this.tr("Address"), null, "address");


      const city = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(city, this.tr("City"), null, "city");

      const postalCode = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(postalCode, this.tr("Postal code"), null, "postalCode");


      const country = new qx.ui.form.SelectBox().set({
        required: true
      });
      doubleSpaced.push(country);
      const countries = osparc.store.StaticInfo.getInstance().getCountries();
      countries.forEach(c => {
        const cItem = new qx.ui.form.ListItem(c.name, null, c.alpha2).set({
          rich: true
        });
        country.add(cItem);
      });
      // preselect
      fetch("https://ipapi.co/json")
        .then(res => res.json())
        .then(data => {
          const countryFound = country.getSelectables().find(c => c.getModel().toUpperCase() === data.country_code.toUpperCase());
          if (countryFound) {
            country.setSelection([countryFound])
          }
        })
        .catch(err => {
          console.error(err);
          const emptyItem = new qx.ui.form.ListItem("", null, "");
          country.add(emptyItem);
          country.setSelection([emptyItem]);
        });
      this._form.add(country, this.tr("Country"), null, "country");


      switch (osparc.product.Utils.getProductName()) {
        case "s4l":
        case "s4lacad":
        case "s4ldesktopacad": {
          const application = new qx.ui.form.SelectBox();
          [{
            id: "other",
            label: "Other"
          }, {
            id: "Antenna_Design_for_Wireless_Communication",
            label: "Antenna Design for Wireless Communication"
          }, {
            id: "Bioelectronics,_Electroceuticals_and_Neuroprosthetics",
            label: "Bioelectronics, Electroceuticals & Neuroprosthetics"
          }, {
            id: "Safety_and_Efficacy_Assessment",
            label: "Safety & Efficacy Assessment"
          }, {
            id: "Exposure_and_Compliance",
            label: "Exposure & Compliance"
          }, {
            id: "Focused_Ultrasound",
            label: "Focused Ultrasound"
          }, {
            id: "In_Silico_Trials",
            label: "In <i>Silico</i> Trials"
          }, {
            id: "Implant_Design",
            label: "Implant Design"
          }, {
            id: "Magnetic_Resonance_Imaging",
            label: "Magnetic Resonance Imaging"
          }, {
            id: "Neurostimulation",
            label: "Neurostimulation"
          }, {
            id: "Personalized_Medicine",
            label: "Personalized Medicine"
          }, {
            id: "Thermal_Therapies",
            label: "Thermal Therapies"
          }, {
            id: "Wireless_Power_Transfer_Systems",
            label: "Wireless Power Transfer Systems"
          }, {
            id: "Vascular_Flow_and_Perfusion",
            label: "Vascular Flow & Perfusion"
          }].forEach(appData => {
            const lItem = new qx.ui.form.ListItem(appData.label, null, appData.id).set({
              rich: true
            });
            application.add(lItem);
          });
          doubleSpaced.push(application);
          this._form.add(application, this.tr("Application"), null, "application");

          const description = new qx.ui.form.TextField();
          doubleSpaced.push(description);
          this._form.add(description, this.tr("Description"), null, "description");
          break;
        }
        case "osparc": {
          const application = new qx.ui.form.SelectBox();
          [{
            id: "other",
            label: "Other"
          }, {
            id: "Reuse_Existing_Services_And_Models",
            label: "Reuse Existing Services And Models"
          }, {
            id: "Data_Analysis",
            label: "Data Analysis"
          }, {
            id: "Personalized_Medicine",
            label: "Personalized Medicine"
          }, {
            id: "Neurostimulation",
            label: "Neurostimulation"
          }, {
            id: "Safety_And_Efficacy_Assessment",
            label: "Safety & Efficacy Assessment"
          }, {
            id: "Device_Design_And_Optimization",
            label: "Device Design & Optimization"
          }, {
            id: "Magnetic_Resonance_Imaging",
            label: "Magnetic Resonance Imaging"
          }, {
            id: "Bioelectromagnetics",
            label: "Bioelectromagnetics"
          }, {
            id: "In_Silico_Trials",
            label: "In Silico Trials"
          }, {
            id: "Image_based_Modeling",
            label: "Image-based Modeling"
          }].forEach(appData => {
            const lItem = new qx.ui.form.ListItem(appData.label, null, appData.id).set({
              rich: true
            });
            application.add(lItem);
          });
          doubleSpaced.push(application);
          this._form.add(application, this.tr("Application"), null, "application");
          break;
        }
      }


      const hear = new qx.ui.form.SelectBox();
      let hearOptions = [];
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          hearOptions = [{
            id: "Other",
            label: "Other"
          }, {
            id: "SPARC_Portal_Or_Event",
            label: "SPARC Portal Or Event"
          }, {
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
          }];
          break;
        default:
          hearOptions = [{
            id: "Other",
            label: "Other"
          }, {
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
          }];
          break;
      }
      hearOptions.forEach(hearData => {
        const lItem = new qx.ui.form.ListItem(hearData.label, null, hearData.id);
        hear.add(lItem);
      });
      doubleSpaced.push(hear);
      this._form.add(hear, this.tr("How did you hear about us?"), null, "hear");


      // accept links
      // Privacy Policy link
      let ppLink = "";
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
        case "tis":
        case "tiplite":
          ppLink = osparc.CookiePolicy.getITISPrivacyPolicyLink("our privacy policy");
          break;
        default:
          ppLink = osparc.CookiePolicy.getS4LPrivacyPolicyLink("our privacy policy");
          break;
      }
      const ppText = this.tr("I acknowledge that data will be processed in accordance to ") + ppLink;
      const privacyPolicy = new qx.ui.form.CheckBox().set({
        required: true,
        value: false
      });
      doubleSpaced.push(privacyPolicy);
      this._form.add(privacyPolicy, ppText, null, "privacyPolicy")

      // Eula link
      if (osparc.product.Utils.getProductName() !== "osparc") {
        const eulaLink = osparc.CookiePolicy.getZMTEULALink("end-users license agreement (EULA)");
        const eulaText = "I accept the " + eulaLink + " and I will use the product in accordance with it";
        const eula = new qx.ui.form.CheckBox().set({
          required: true,
          value: false
        });
        doubleSpaced.push(eula);
        this._form.add(eula, eulaText, null, "eula");
      }


      const content = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      const formRenderer = new osparc.ui.form.renderer.DoubleV(this._form, doubleSpaced);
      content.add(formRenderer);
      const captchaLayout = this.__createCaptchaLayout();
      this._form.getValidationManager().add(this.__captchaField);
      content.add(captchaLayout);
      const scrollView = new qx.ui.container.Scroll();
      scrollView.add(content);
      this.add(scrollView, {
        flex: 1
      });

      // buttons
      const grp = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));
      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const submitBtn = this.__requestButton = new qx.ui.form.Button(this.tr("Request")).set({
        center: true,
        appearance: "form-button"
      });
      osparc.utils.Utils.setIdToWidget(submitBtn, "registrationSubmitBtn");
      buttons.addAt(submitBtn, 1, {
        flex:1
      });

      const cancelBtn = this.__cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "form-button-text"
      });
      buttons.addAt(cancelBtn, 0, {
        flex:1
      });

      grp.add(buttons)

      // interaction
      submitBtn.addListener("execute", () => this.__requestPressed(), this);
      cancelBtn.addListener("execute", () => this.fireDataEvent("done", null), this);

      this.add(grp);
    },

    __requestPressed: function() {
      const validForm = this._form.validate();
      if (validForm) {
        const formData = {};
        Object.entries(this._form.getItems()).forEach(([key, field]) => {
          const val = field.getValue();
          if (val && (typeof val === "object") && ("classname" in val)) {
            formData[key] = val.getModel();
          } else {
            formData[key] = val;
          }
        });
        this.__submit(formData, this.__captchaField.getValue());
      }
    },

    __submit: function(formData, captchaValue) {
      const params = {
        data: {
          "form": formData,
          "captcha": captchaValue
        }
      };
      osparc.data.Resources.fetch("auth", "postRequestAccount", params)
        .then(() => {
          const msg = this.tr("Your request is being processed. You will hear from us soon");
          osparc.FlashMessenger.logAs(msg, "INFO");
          this.fireDataEvent("done");
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          this.__restartCaptcha();
        });
    },

    __createCaptchaLayout: function() {
      const captchaGrid = new qx.ui.layout.Grid(5, 5);
      captchaGrid.setColumnAlign(0, "center", "bottom");
      captchaGrid.setColumnFlex(2, 1);
      const captchaLayout = new qx.ui.container.Composite(captchaGrid);

      const captchaImage = this.__captchaImage = new qx.ui.basic.Image().set({
        allowShrinkX: true,
        allowShrinkY: true,
        scale: true,
        width: 140,
        height: 45
      });
      captchaLayout.add(captchaImage, {
        column: 0,
        row: 0,
        rowSpan: 2
      });

      const restartCaptcha = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/sync-alt/12",
        toolTipText: this.tr("Reload Captcha")
      });
      restartCaptcha.addListener("tap", () => this.__restartCaptcha(), this);
      captchaLayout.add(restartCaptcha, {
        column: 1,
        row: 1
      });

      const label = new qx.ui.basic.Label(this.tr("Type the 6 digits:")).set({
        font: "text-12"
      });
      captchaLayout.add(label, {
        column: 2,
        row: 0
      });

      const captchaField = this.__captchaField = new qx.ui.form.TextField().set({
        backgroundColor: "transparent",
        required: true
      });
      captchaLayout.add(captchaField, {
        column: 2,
        row: 1
      });

      return captchaLayout;
    },

    __restartCaptcha: function() {
      this.__captchaImage.setSource(null);
      let url = osparc.data.Resources.resources["auth"].endpoints["captcha"].url;
      // Since the url doesn't change, this dummy query parameter will force the frontend to make a new request
      url += "?" + new Date().getTime();
      this.__captchaImage.setSource(url);

      this.__captchaField.resetValue();
    },

    _onAppear: function() {
      this.__restartCaptcha();

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

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/** Login page
 *
 * - Form with fields necessary to login
 * - Form data validation
 * - Adds links to register and reset pages. Transitions are fired as events.
 * - To execute login, it delegates on the auth.manager
 * - Minimal layout and appearance is delegated to the selected theme
 */

qx.Class.define("osparc.auth.ui.LoginView", {
  extend: osparc.auth.core.BaseAuthPage,

  events: {
    "toRegister": "qx.event.type.Event",
    "toRequestAccount": "qx.event.type.Event",
    "toReset": "qx.event.type.Event",
    "toVerifyPhone": "qx.event.type.Data",
    "to2FAValidationCode": "qx.event.type.Data"
  },

  members: {
    __loginBtn: null,
    __loginAnnouncements: null,

    // overrides base
    _buildPage: function() {
      const announcementUIFactory = osparc.announcement.AnnouncementUIFactory.getInstance();
      const addAnnouncements = () => {
        if (this.__loginAnnouncements) {
          this.remove(this.__loginAnnouncements);
        }
        this.__loginAnnouncements = announcementUIFactory.createLoginAnnouncements();
        this.addAt(this.__loginAnnouncements, 0);
      };
      if (announcementUIFactory.hasLoginAnnouncement()) {
        addAnnouncements();
      } else {
        announcementUIFactory.addListenerOnce("changeAnnouncements", () => addAnnouncements());
      }

      // form
      const email = new qx.ui.form.TextField().set({
        required: true
      });
      email.getContentElement().setAttribute("autocomplete", "username");
      osparc.utils.Utils.setIdToWidget(email, "loginUserEmailFld");
      this._form.add(email, " Your email address", qx.util.Validate.email(), "email");
      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });

      const pass = new osparc.ui.form.PasswordField().set({
        required: true
      });
      pass.getChildControl("passwordField").getContentElement().setAttribute("autocomplete", "current-password");
      osparc.utils.Utils.setIdToWidget(pass.getChildControl("passwordField"), "loginPasswordFld");
      this._form.add(pass, " Your password", null, "password");

      this.beautifyFormFields();
      const formRenderer = new qx.ui.form.renderer.SinglePlaceholder(this._form);
      this.add(formRenderer);

      // buttons
      const loginBtn = this.__loginBtn = new osparc.ui.form.FetchButton(this.tr("Sign in")).set({
        center: true,
        appearance: "strong-button"
      });
      loginBtn.addListener("execute", () => this.__login(), this);
      osparc.utils.Utils.setIdToWidget(loginBtn, "loginSubmitBtn");
      this.add(loginBtn);


      //  (create account/request account) | forgot password? links
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      const createAccountBtn = new osparc.ui.form.LinkButton(this.tr("Create Account"));
      const createAccountAction = osparc.product.Utils.getCreateAccountAction();
      if (["REQUEST_ACCOUNT_FORM", "REQUEST_ACCOUNT_INSTRUCTIONS"].includes(createAccountAction)) {
        createAccountBtn.setLabel(this.tr("Request Account"));
      }
      createAccountBtn.addListener("execute", () => {
        if (window.location.hostname === "tip.itis.swiss") {
          this.__openTIPITISSWISSPhaseOutDialog();
        } else if (createAccountAction === "REGISTER") {
          this.fireEvent("toRegister");
        } else if (createAccountAction === "REQUEST_ACCOUNT_FORM") {
          this.fireEvent("toRequestAccount");
        } else if (createAccountAction === "REQUEST_ACCOUNT_INSTRUCTIONS") {
          osparc.store.Support.openInvitationRequiredDialog();
        }
      }, this);
      osparc.utils.Utils.setIdToWidget(createAccountBtn, "loginCreateAccountBtn");

      const forgotBtn = new osparc.ui.form.LinkButton(this.tr("Forgot Password?"));
      forgotBtn.addListener("execute", () => this.fireEvent("toReset"), this);
      osparc.utils.Utils.setIdToWidget(forgotBtn, "loginForgotPasswordBtn");

      [createAccountBtn, forgotBtn].forEach(btn => {
        grp.add(btn.set({
          center: true,
          allowGrowX: true
        }), {
          width: "50%"
        });
      });

      this.add(grp);

      if (osparc.product.Utils.isProduct("tis") || osparc.product.Utils.isProduct("tiplite")) {
        let text = "";
        if (osparc.product.Utils.isProduct("tiplite")) {
          text = "The TIP tool is designed for research purposes only and is not intended for clinical use."
        } else {
          text = `
            1) The TIP tool is designed for research purposes only and is not intended for clinical use.
            </br>
            </br>
            2) Users are responsible for ensuring the anonymization and privacy protection of personal data.
            </br>
            </br>
            3) The development, maintenance and usage of the TIP tool is fully sponsored by the IT’IS Foundation, with the exception of the 61 complex 3D electromagnetic simulations on the AWS cluster required for the personalized plans.
          `;
        }
        const disclaimer = osparc.announcement.AnnouncementUIFactory.createLoginAnnouncement(this.tr("Disclaimer"), text);
        this.add(disclaimer);

        this.add(new qx.ui.core.Spacer(), {
          flex: 1
        });

        const poweredByLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
          alignX: "center",
          allowGrowX: false,
          cursor: "pointer"
        });
        poweredByLayout.addListener("tap", () => window.open("https://sim4life.swiss/"));
        const label = new qx.ui.basic.Label(this.tr("powered by"));
        poweredByLayout.add(label);
        const s4lLogo = new qx.ui.basic.Image("osparc/Sim4Life_full_logo_white.svg");
        s4lLogo.set({
          width: osparc.auth.LoginPage.LOGO_WIDTH/2,
          height: osparc.auth.LoginPage.LOGO_HEIGHT/2,
          scale: true,
          alignX: "center"
        });
        poweredByLayout.add(s4lLogo);
        this.add(poweredByLayout);
      }
    },

    __openTIPITISSWISSPhaseOutDialog: function() {
      const createAccountWindow = new osparc.ui.window.Dialog("Request Account").set({
        maxWidth: 380
      });
      let message = "This version of the planning tool will be phased out soon and no longer accepts new users.";
      message += "<br>";
      const tipLiteLabel = osparc.utils.Utils.createHTMLLink("TIP.lite", "https://tip-lite.science/");
      const tipLabel = osparc.utils.Utils.createHTMLLink("TIP", "https://tip.science/");
      const hereLabel = osparc.utils.Utils.createHTMLLink("here", "https://itis.swiss/tools-and-systems/ti-planning/overview/");
      message += `Please visit ${tipLiteLabel} or ${tipLabel} instead. See ${hereLabel} for more information.`;
      createAccountWindow.setMessage(message);
      createAccountWindow.center();
      createAccountWindow.open();
    },

    getEmail: function() {
      const email = this._form.getItems().email;
      return email.getValue();
    },

    __login: function() {
      if (!this._form.validate()) {
        return;
      }

      this.__loginBtn.setFetching(true);

      const email = this._form.getItems().email;
      const pass = this._form.getItems().password;

      const loginFun = msg => {
        this.__loginBtn.setFetching(false);
        this.fireDataEvent("done", msg);
        // we don't need the form any more, so remove it and mock-navigate-away
        // and thus tell the password manager to save the content
        this._form.dispose();
        window.history.replaceState(null, window.document.title, window.location.pathname);
      };

      const verifyPhoneCbk = () => {
        this.__loginBtn.setFetching(false);
        this.fireDataEvent("toVerifyPhone", email.getValue());
        // we don't need the form any more, so remove it and mock-navigate-away
        // and thus tell the password manager to save the content
        this._form.dispose();
        window.history.replaceState(null, window.document.title, window.location.pathname);
      };

      const twoFactorAuthCbk = (nextStep, message, retryAfter) => {
        this.__loginBtn.setFetching(false);
        osparc.FlashMessenger.getInstance().logAs(message, "INFO");
        this.fireDataEvent("to2FAValidationCode", {
          userEmail: email.getValue(),
          nextStep,
          message,
          retryAfter
        });
        // we don't need the form any more, so remove it and mock-navigate-away
        // and thus tell the password manager to save the content
        this._form.dispose();
        window.history.replaceState(null, window.document.title, window.location.pathname);
      };

      const failFun = msg => {
        this.__loginBtn.setFetching(false);
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Typed an invalid email or password");
        [email, pass].forEach(item => {
          item.set({
            invalidMessage: msg,
            valid: false
          });
        });

        osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.login(email.getValue(), pass.getValue())
        .then(resp => {
          if (resp.status === 202) {
            if (resp.nextStep === "PHONE_NUMBER_REQUIRED") {
              verifyPhoneCbk();
            } else if (["SMS_CODE_REQUIRED", "EMAIL_CODE_REQUIRED"].includes(resp.nextStep)) {
              twoFactorAuthCbk(resp.nextStep, resp.message, resp.retryAfter);
            }
          } else if (resp.status === 200) {
            loginFun(resp.message);
          }
        })
        .catch(err => failFun(err));
    },

    resetValues: function() {
      if (this._form.getGroups()) {
        // if there are no groups, getItems will fail
        const fieldItems = this._form.getItems();
        for (const key in fieldItems) {
          fieldItems[key].resetValue();
        }
      }
    },

    _onAppear: function() {
      // Listen to "Enter" key
      const command = new qx.ui.command.Command("Enter");
      this.__loginBtn.setCommand(command);
    },

    _onDisappear: function() {
      this.__loginBtn.setCommand(null);
    }
  }
});

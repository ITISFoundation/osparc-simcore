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

    // overrides base
    _buildPage: function() {
      const announcementUIFactory = osparc.announcement.AnnouncementUIFactory.getInstance();
      if (announcementUIFactory.hasLoginAnnouncement()) {
        this.addAt(announcementUIFactory.createLoginAnnouncement(), 0);
      } else {
        announcementUIFactory.addListenerOnce("changeAnnouncement", e => {
          const announcement = e.getData();
          if (announcement) {
            this.addAt(announcementUIFactory.createLoginAnnouncement(), 0);
          }
        });
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
      const config = osparc.store.Store.getInstance().get("config");
      if (config["invitation_required"]) {
        createAccountBtn.setLabel(this.tr("Request Account"));
      }
      createAccountBtn.addListener("execute", () => {
        createAccountBtn.setEnabled(false);
        if (config["invitation_required"]) {
          if (osparc.product.Utils.isS4LProduct()) {
            this.fireEvent("toRequestAccount");
          } else {
            osparc.store.Support.openInvitationRequiredDialog();
          }
        } else {
          this.fireEvent("toRegister");
        }
        createAccountBtn.setEnabled(true);
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

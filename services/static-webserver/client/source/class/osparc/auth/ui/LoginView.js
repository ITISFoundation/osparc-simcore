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
        this.add(announcementUIFactory.createLoginAnnouncement());
      }

      const formRenderer = new qx.ui.form.renderer.SinglePlaceholder(this._form).set({
        allowGrowX: true
      });
      this.add(formRenderer);

      const email = new qx.ui.form.TextField().set({
        width: osparc.auth.core.BaseAuthPage.FORM_WIDTH,
        required: true,
        allowGrowX: true
      });
      email.getContentElement().setAttribute("autocomplete", "username");
      osparc.utils.Utils.setIdToWidget(email, "loginUserEmailFld");
      this._form.add(email, " Your email address", qx.util.Validate.email(), "email");
      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });
      const pass = new osparc.ui.form.PasswordField().set({
        width: osparc.auth.core.BaseAuthPage.FORM_WIDTH,
        required: true,
        placeholder: this.tr(" Your password")
      });
      pass.getChildControl("passwordField").getContentElement().setAttribute("autocomplete", "current-password");
      osparc.utils.Utils.setIdToWidget(pass.getChildControl("passwordField"), "loginPasswordFld");
      this._form.add(pass, " Your password", null, "password");

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
      osparc.data.Resources.getOne("config")
        .then(config => {
          if (config["invitation_required"]) {
            createAccountBtn.setLabel(this.tr("Request Account"));
          }
        })
        .catch(err => console.error(err));
      createAccountBtn.addListener("execute", () => {
        createAccountBtn.setEnabled(false);
        osparc.data.Resources.getOne("config")
          .then(config => {
            if (config["invitation_required"]) {
              if (osparc.product.Utils.getProductName().includes("s4l")) {
                this.fireEvent("toRequestAccount");
              } else {
                osparc.store.Support.openInvitationRequiredDialog();
              }
            } else {
              this.fireEvent("toRegister");
            }
          })
          .catch(err => console.error(err));
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

      const loginFun = function(log) {
        this.__loginBtn.setFetching(false);
        this.fireDataEvent("done", log.message);
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

      const twoFactorAuthCbk = msg => {
        this.__loginBtn.setFetching(false);
        osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
        this.fireDataEvent("to2FAValidationCode", msg);
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
      manager.login(email.getValue(), pass.getValue(), loginFun, verifyPhoneCbk, twoFactorAuthCbk, failFun, this);
    },

    resetValues: function() {
      const fieldItems = this._form.getItems();
      for (const key in fieldItems) {
        fieldItems[key].resetValue();
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

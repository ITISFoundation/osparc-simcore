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
 * - Minimal layout and apperance is delegated to the selected theme
 */

qx.Class.define("osparc.auth.ui.LoginView", {
  extend: osparc.auth.core.BaseAuthPage,
  include: [
    osparc.auth.core.MAuth
  ],

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events: {
    "toRegister": "qx.event.type.Event",
    "toReset": "qx.event.type.Event"
  },

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
    // overrides base
    __form: null,
    __loginBtn: null,

    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      const image = new osparc.ui.basic.OSparcLogo().set({
        width: 250,
        height: 150
      });
      this.add(image);

      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Your email address"),
        required: true
      });
      this.add(email);
      email.getContentElement().setAttribute("autocomplete", "username");
      osparc.utils.Utils.setIdToWidget(email, "loginUserEmailFld");
      this.__form.add(email, "", qx.util.Validate.email(), "email", null);
      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });
      const pass = new qx.ui.form.PasswordField().set({
        placeholder: this.tr("Your password"),
        required: true
      });
      pass.getContentElement().setAttribute("autocomplete", "current-password");
      osparc.utils.Utils.setIdToWidget(pass, "loginPasswordFld");
      this.add(pass);
      this.__form.add(pass, "", null, "password", null);

      const loginBtn = this.__loginBtn = new osparc.ui.form.FetchButton(this.tr("Sign in"));
      loginBtn.addListener("execute", () => {
        loginBtn.setFetching(true);
        this.__login(loginBtn);
      }, this);
      osparc.utils.Utils.setIdToWidget(loginBtn, "loginSubmitBtn");
      this.add(loginBtn);


      //  create account | forgot password? links
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      const registerBtn = this.createLinkButton(this.tr("Create Account"), () => {
        osparc.data.Resources.getOne("config")
          .then(config => {
            if (config["invitation_required"]) {
              let text = this.tr("Registration is currently only available with an invitation.");
              text += "<br>";
              text += this.tr("Please contact info@itis.swiss");
              osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");
            } else {
              this.fireEvent("toRegister");
            }
          })
          .catch(err => {
            console.error(err);
            this.fireEvent("toRegister");
          });
      }, this);
      osparc.utils.Utils.setIdToWidget(registerBtn, "loginCreateAccountBtn");

      const forgotBtn = this.createLinkButton(this.tr("Forgot Password?"), () => {
        this.fireEvent("toReset");
      }, this);
      osparc.utils.Utils.setIdToWidget(forgotBtn, "loginForgotPasswordBtn");

      [registerBtn, forgotBtn].forEach(btn => {
        grp.add(btn.set({
          center: true,
          allowGrowX: true
        }), {
          width: "50%"
        });
      });

      this.add(grp);

      // TODO: add here loging with NIH and openID
      // this.add(this.__buildExternals());
    },

    __buildExternals: function() {
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      [this.tr("Login with NIH"), this.tr("Login with OpenID")].forEach(txt => {
        const btn = this.createLinkButton(txt, function() {
          // TODO add here callback
          console.error("Login with external services are still not implemented");
        }, this);

        grp.add(btn.set({
          center: true
        }), {
          flex:1
        });
      });

      return grp;
    },

    __login: function(loginBtn) {
      if (!this.__form.validate()) {
        return;
      }

      const email = this.__form.getItems().email;
      const pass = this.__form.getItems().password;

      const successFun = function(log) {
        loginBtn.setFetching(false);
        this.fireDataEvent("done", log.message);
        // we don't need the form any more, so remove it and mock-navigate-away
        // and thus tell the password manager to save the content
        this._formElement.dispose();
        window.history.replaceState(null, window.document.title, window.location.pathname);
      };

      const failFun = function(msg) {
        loginBtn.setFetching(false);
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Introduced an invalid email or password");
        [email, pass].forEach(item => {
          item.set({
            invalidMessage: msg,
            valid: false
          });
        });

        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.login(email.getValue(), pass.getValue(), successFun, failFun, this);
    },

    resetValues: function() {
      const fieldItems = this.__form.getItems();
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

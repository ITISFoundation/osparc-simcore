/* ************************************************************************

   qxapp - the simcore frontend

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

qx.Class.define("qxapp.auth.ui.LoginView", {
  extend: qxapp.auth.core.BaseAuthPage,
  include: [
    qxapp.auth.core.MAuth
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
    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      const atm = new qx.ui.basic.Atom().set({
        icon: "qxapp/osparc-white.svg",
        iconPosition: "top"
      });
      atm.getChildControl("icon").set({
        width: 250,
        height: 150,
        scale: true
      });
      this.add(atm);

      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Your email address"),
        required: true
      });
      this.add(email);
      email.getContentElement().setAttribute("autocomplete", "username");
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
      this.add(pass);
      this.__form.add(pass, "", null, "password", null);

      const loginBtn = new qx.ui.form.Button(this.tr("Log In"));
      loginBtn.addListener("execute", function() {
        this.__login();
      }, this);
      // Listen to "Enter" key
      this.addListener("keypress", function(keyEvent) {
        if (keyEvent.getKeyIdentifier() === "Enter") {
          this.__login();
        }
      }, this);
      this.add(loginBtn);


      //  create account | forgot password? links
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      const registerBtn = this.createLinkButton(this.tr("Create Account"), () => {
        const interval = 1000;
        const configTimer = new qx.event.Timer(interval);
        const resource = qxapp.io.rest.ResourceFactory.getInstance();
        let registerWithInvitation = resource.registerWithInvitation();
        configTimer.addListener("interval", () => {
          registerWithInvitation = resource.registerWithInvitation();
          if (registerWithInvitation !== null) {
            configTimer.stop();
            if (registerWithInvitation) {
              let text = this.tr("Registration is currently only available with an invitation.");
              text += "<br>";
              text += this.tr("Please contact info@itis.swiss");
              qxapp.component.widget.FlashMessenger.getInstance().logAs(text, "INFO");
            } else {
              this.fireEvent("toRegister");
            }
          }
        }, this);
        configTimer.start();
      }, this);

      const forgotBtn = this.createLinkButton(this.tr("Forgot Password?"), () => {
        this.fireEvent("toReset");
      }, this);

      [registerBtn, forgotBtn].forEach(btn => {
        grp.add(btn.set({
          center: true
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

    __login: function() {
      if (!this.__form.validate()) {
        return;
      }

      const email = this.__form.getItems().email;
      const pass = this.__form.getItems().password;

      const manager = qxapp.auth.Manager.getInstance();

      const successFun = function(log) {
        this.fireDataEvent("done", log.message);
        // we don't need the form any more, so remove it and mock-navigate-away
        // and thus tell the password manager to save the content
        this._formElement.dispose();
        window.history.replaceState(null, window.document.title, window.location.pathname);
      };

      const failFun = function(msg) {
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Introduced an invalid email or password");
        [email, pass].forEach(item => {
          item.set({
            invalidMessage: msg,
            valid: false
          });
        });

        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      manager.login(email.getValue(), pass.getValue(), successFun, failFun, this);
    },

    resetValues: function() {
      const fieldItems = this.__form.getItems();
      for (const key in fieldItems) {
        fieldItems[key].resetValue();
      }
    }
  }
});

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

qx.Class.define("qxapp.auth.ui.LoginPage", {
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

      let atm = new qx.ui.basic.Atom().set({
        icon: "qxapp/osparc-white.svg",
        iconPosition: "top"
      });
      atm.getChildControl("icon").set({
        width: 250,
        height: 150,
        scale: true
      });
      this.add(atm);

      let email = new qx.ui.form.TextField().set({
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
      let pass = new qx.ui.form.PasswordField().set({
        placeholder: this.tr("Your password"),
        required: true
      });
      pass.getContentElement().setAttribute("autocomplete", "current-password");
      this.add(pass);
      this.__form.add(pass, "", null, "password", null);

      let loginBtn = new qx.ui.form.Button(this.tr("Log In"));
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
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        separator: "main"
      }));

      let registerBtn = this.createLinkButton(this.tr("Create Account"), function() {
        this.fireEvent("toRegister");
      }, this);

      let forgotBtn = this.createLinkButton(this.tr("Forgot Password?"), function() {
        this.fireEvent("toReset");
      }, this);

      [registerBtn, forgotBtn].forEach(btn => {
        grp.add(btn.set({
          center: true
        }), {
          flex: 1
        });
      });

      this.add(grp);

      // TODO: add here loging with NIH and openID
      // this.add(this.__buildExternals());
    },

    __buildExternals: function() {
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      [this.tr("Login with NIH"), this.tr("Login with OpenID")].forEach(txt => {
        let btn = this.createLinkButton(txt, function() {
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

      let manager = qxapp.auth.Manager.getInstance();

      let successFun = function(log) {
        this.fireDataEvent("done", log.message);
        // we don't need the form any more, so remove it and mock-navigate-away
        // and thus tell the password manager to save the content
        this._formElement.dispose();
        window.history.replaceState(null, window.document.title, window.location.pathname);
      };

      let failFun = function(msg) {
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
      let fieldItems = this.__form.getItems();
      for (var key in fieldItems) {
        fieldItems[key].resetValue();
      }
    }
  }
});

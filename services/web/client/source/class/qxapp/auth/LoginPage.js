/**
 *  TODO: layout should be adaptable
 *
 *
 * Based on
 * http://www.softwaresamurai.org/2018/01/06/login-form-with-php-and-qooxdoo/
 *
 */

qx.Class.define("qxapp.auth.LoginPage", {
  extend: qxapp.auth.BaseAuthPage,

  construct: function() {
    this.base(arguments);
  },

  destruct: function() {
    this.base(arguments);
    console.debug("destroying LoginPage");
  },
  members: {
    __form: null,

    // overrides base
    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      var atm = new qx.ui.basic.Atom().set({
        icon: "qxapp/itis-white.png",
        iconPosition: "top",
        width: this.getWidth(),
        marginBottom: this._marginHeader
      });
      this.add(atm);

      var email = new qx.ui.form.TextField();
      email.setPlaceholder("Your email address");
      email.setRequired(true);
      this.add(email);
      this.__form.add(email, "", qx.util.Validate.email(), "email", null);

      var pass = new qx.ui.form.PasswordField();
      pass.setPlaceholder("Your password");
      pass.setRequired(true);
      this.add(pass);
      this.__form.add(pass, "", null, "password", null);


      // |        Login-|
      let grpBtns = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      grpBtns.set({
        marginTop: this._marginFooter
      });

      var btnLogin = this.createButton(this.tr("Log In"), this._widthBtn, function() {
        if (this.__form.validate()) {
          this.login();
        }
      }, this);
      grpBtns.add(btnLogin, {
        right: 0
      });

      this.add(grpBtns);


      // |~ Remember -|- ForgotPassword ~|
      let grpLinks = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      grpLinks.set({
        marginTop: 2*this._marginFooter,
        width: this.getWidth()
      });

      // TODO: Temporary disabled. 'Remember me' implies keeping login status in server
      // var chk = new qx.ui.form.CheckBox("<i style='color: #FFFFFF'>" + this.tr("Remember me") + "</i>");
      // var lbl = chk.getChildControl("label");
      // lbl.setRich(true);
      // grpLinks.add(chk, {
      //  left: "5%"
      // });
      // this.__form.add(chk, "", null, "remember", null);
      const mid = parseInt(this.getWidth() / 2);
      var registerLnk = this.createLinkButton(this.tr("Create Account"), function() {
        this.register();
      }, this);
      grpLinks.add(registerLnk, {
        right: mid + 20
      });

      grpLinks.add(new qx.ui.basic.Atom("|"), {
        right: mid
      });

      var forgotLink = this.createLinkButton(this.tr("Forgot Password?"), function() {
        this.forgot();
      }, this);
      grpLinks.add(forgotLink, {
        left: mid + 15
      });
      this.add(grpLinks);
    },

    login: function() {
      // Data
      const email = this.__form.getItems().email;
      const pass = this.__form.getItems().password;
      const auth = new qx.io.request.authentication.Basic(email.getValue(), pass.getValue());

      let request = new qx.io.request.Xhr();
      const prefix = qxapp.io.rest.AbstractResource.API;
      request.set({
        authentication: auth,
        url: prefix + "/token",
        method: "GET"
      });

      request.addListener("success", function(e) {
        // Completes without error and *transport status indicates success*
        let req = e.getTarget();
        console.debug("Login suceeded:", "status  :", req.getStatus(), "phase   :", req.getPhase(), "response: ", req.getResponse());
        this.assert(req == request);

        // saves token for future requests
        qxapp.auth.Store.setToken(req.getResponse().token);

        // Switches to main
        let app = qx.core.Init.getApplication();
        app.start();
        this.destroy();
      }, this);

      request.addListener("fail", function(e) {
        // TODO: implement in flash message.
        // TODO: why if failed? Add server resposne message

        const msg = this.tr("Invalid email or password");
        email.setInvalidMessage(msg);
        email.setValid(false);

        pass.setInvalidMessage(msg);
        pass.setValid(false);

        this.show();
      }, this);

      request.send();
    },

    forgot: function() {
      var forgot = new qxapp.auth.ResetPassPage();
      forgot.show();
      this.destroy();
    },

    register: function() {
      var register = new qxapp.auth.RegistrationPage();
      register.show();
      this.destroy();
    }
  }
});

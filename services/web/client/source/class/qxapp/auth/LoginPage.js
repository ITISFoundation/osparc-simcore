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

  members: {
    __form: null,

    // overrides base
    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      let atm = new qx.ui.basic.Atom().set({
        icon: "qxapp/itis-white.png",
        iconPosition: "top"
      });
      this.add(atm);

      let email = new qx.ui.form.TextField();
      email.setPlaceholder(this.tr("Your email address"));
      email.setRequired(true);
      this.add(email);
      this.__form.add(email, "", qx.util.Validate.email(), "email", null);

      let pass = new qx.ui.form.PasswordField();
      pass.setPlaceholder(this.tr("Your password"));
      pass.setRequired(true);
      this.add(pass);
      this.__form.add(pass, "", null, "password", null);

      // |               Login-|
      // TODO: Temporary disabled. 'Remember me' implies keeping login status in server
      // let chk = new qx.ui.form.CheckBox(this.tr("Remember me"));
      // this.__form.add(chk, "", null, "remember", null);

      let loginBtn = new qx.ui.form.Button(this.tr("Log In"));
      loginBtn.addListener("execute", function() {
        if (this.__form.validate()) {
          this.login();
        }
      }, this);
      this.add(loginBtn);


      //  create account | forgot password?
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        separator: "main"
      }));

      let registerBtn = this.createLinkButton(this.tr("Create Account"), function() {
        this.register();
      }, this);

      let forgotBtn = this.createLinkButton(this.tr("Forgot Password?"), function() {
        this.forgot();
      }, this);

      [registerBtn, forgotBtn].forEach(btn => {
        grp.add(btn.set({
          center: true
        }), {
          flex:1
        });
      });

      this.add(grp);

      // TODO: add here loging with NIH and openID
      // let grp2 = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      // ["Login with NIH", "Login with OpenID"].forEach(txt => {
      //   let btn = this.createLinkButton(this.tr(txt), function(){}, this);
      //   grp2.add(btn.set({
      //     center: true
      //   }), {
      //     flex:1
      //   });
      // }, this);
      // this.add(grp2);
    },

    login: function() {
      //---------------------------------------------------------------------------
      // TODO: temporarily will allow any user until issue #162 is resolved and/or
      // python server has active API
      if (!qx.core.Environment.get("dev.enableFakeSrv")) {
        // Switches to main
        qxapp.auth.Store.setToken("fake-token");
        let app = qx.core.Init.getApplication();
        app.start();
        this.destroy();
        return;
      }
      //---------------------------------------------------------------------------

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

        [email, pass].forEach(item => {
          item.set({
            invalidMessage: this.tr("Invalid email or password"),
            valid: false
          });
        });
        this.show();
      }, this);

      request.send();
    },

    forgot: function() {
      let forgot = new qxapp.auth.ResetPassPage();
      forgot.show();
      this.destroy();
    },

    register: function() {
      let register = new qxapp.auth.RegistrationPage();
      register.show();
      this.destroy();
    }
  }
});

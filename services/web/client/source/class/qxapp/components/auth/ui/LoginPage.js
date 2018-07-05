/**
 *  TODO: layout should be adaptable
 *
 *
 * Based on
 * http://www.softwaresamurai.org/2018/01/06/login-form-with-php-and-qooxdoo/
 *
 */

qx.Class.define("qxapp.auth.LoginPage", {
  extend: qx.ui.container.Composite,
  include: qxapp.auth.MAuthPage,

  construct: function() {
    this.base(arguments);
    // Setup children's layout and widget dims
    this.setLayout(new qx.ui.layout.Canvas());
    this.set({
      width: 300,
      height: 250
    });

    this.__buildPage();
    // Place this in document's center. TODO: should be automatically reposition of document size changed!?
    var top = parseInt((qx.bom.Document.getHeight() - this.getHeight()) / 2, 10);
    var left = parseInt((qx.bom.Document.getWidth() - this.getWidth()) / 2, 10);
    var app = qx.core.Init.getApplication();
    app.getRoot().add(this, {
      top: top,
      left: left
    });
  },

  destruct: function() {
    console.debug("destroying LoginPage");
  },
  members: {
    _form: null,

    __buildPage: function() {
      this._form = new qx.ui.form.Form();

      var top = 0;
      var atm = new qx.ui.basic.Atom().set({
        icon: "auth/itis.png",
        iconPosition: "top"
      });
      atm.setWidth(this.getWidth() - 20);
      this.add(atm, {
        top: top,
        left: 10
      });

      top += 65;
      var email = new qx.ui.form.TextField();
      email.setPlaceholder("Your email address");
      email.setRequired(true);
      this.add(email, {
        top: top,
        left: 10,
        right: 10
      });
      this._form.add(email, "", qx.util.Validate.email(), "email", null);

      top += 40;
      var pass = new qx.ui.form.PasswordField();
      pass.setPlaceholder("Your password");
      pass.setRequired(true);
      this.add(pass, {
        top: top,
        left: 10,
        right: 10
      });
      this._form.add(pass, "", null, "password", null);

      top += 35;
      var chk = new qx.ui.form.CheckBox("<b style='color: #FFFFFF'>" + this.tr("Remember me?") + "</b>");
      var lbl = chk.getChildControl("label");
      lbl.setRich(true);
      this.add(chk, {
        top: top,
        left: 10
      });
      this._form.add(chk, "", null, "remember", null);

      var btnForgot = this.createLinkButton(this.tr("Forgot Password?"), function() {
        this.forgot();
      }, this);
      this.add(btnForgot, {
        top: top,
        right: 10
      });

      var width = parseInt((this.getWidth() - 30) / 2, 10);
      var btnLogin = this.createButton(this.tr("Log In"), width, function() {
        if (this._form.validate()) {
          this.login();
        }
      }, this);
      this.add(btnLogin, {
        bottom: 30,
        left: 10
      });

      var btnRegister = this.createButton(this.tr("Register"), width, function() {
        this.register();
      }, this);
      this.add(btnRegister, {
        bottom: 30,
        right: 10
      });
    },

    login: function() {
      // Data
      var email = this._form.getItems().email;
      var pass = this._form.getItems().password;
      var remember = this._form.getItems().remember;

      var str = "type=login";
      str += "&username=" + email.getValue();
      str += "&password=" + pass.getValue();
      str += "&remember=" + remember.getValue();

      var app = qx.core.Init.getApplication();
      app.request(str, function(success) {
        var page = null;
        if (success) {
          page = new qxapp.auth.MainPage();
          page.show();
          this.destroy();
        } else {
          // Flash message
          var message = this.tr("Invalid email or password");
          email.setInvalidMessage(message);
          pass.setInvalidMessage(message);
          email.setValid(false);
          pass.setValid(false);
          //alert(this.tr("Could not log in."));
        }
      }, this);
    },

    forgot: function() {
      var forgot = new qxapp.auth.ResetPassPage();
      forgot.show();
      this.destroy();
    },

    register: function() {
      var register = new qxapp.auth.RegisterPage();
      register.show();
      this.destroy();
    }
  }
});

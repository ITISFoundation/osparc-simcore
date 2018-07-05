
qx.Class.define("qxapp.auth.RegistrationPage", {
  extend: qxapp.auth.BaseAuthPage,

  construct: function() {
    this.base(arguments);
  },
  destruct: function() {
    console.debug("destroying RegistrationPage");
  },

  members: {
    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Register"));

      var name = new qx.ui.form.TextField();
      name.setPlaceholder("Introduce your email");
      this.add(name);

      var pass = new qx.ui.form.PasswordField();
      pass.setPlaceholder("Introduce a password");
      this.add(pass);

      var pass2 = new qx.ui.form.PasswordField();
      pass2.setPlaceholder("Retype your password");
      this.add(pass2);


      // buttons
      var grp = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      grp.set({
        marginTop: this._marginFooter
      });

      var btn = new qx.ui.form.Button(this.tr("Submit"));
      btn.setWidth(this._widthBtn);
      grp.add(btn, {
        left: 0
      });

      btn.addListener("execute", function(e) {
        this.__register();
      }, this);

      btn = new qx.ui.form.Button(this.tr("Cancel"));
      btn.setWidth(this._widthBtn);
      grp.add(btn, {
        right: 0
      });

      btn.addListener("execute", function(e) {
        this.__cancel();
      }, this);

      this.add(grp);
    },

    __register: function() {
      this.debug("Registering new user");
      // fail if user exists, etc
      // back to login
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    },

    __cancel: function() {
      this.debug("Cancel registration");
      // back to login
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }
  }
});

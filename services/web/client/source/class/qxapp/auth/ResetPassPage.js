/** Page to reset reset user's password
 *
 */
qx.Class.define("qxapp.auth.ResetPassPage", {
  extend: qxapp.auth.BaseAuthPage,

  construct: function() {
    this.base(arguments);
  },
  destruct: function() {
    this.base(arguments);
    console.debug("destroying ResetPassPage");
  },

  members: {
    __email: null,

    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Reset Password"));

      var email = new qx.ui.form.TextField();
      email.setPlaceholder(this.tr("Introduce your email to reset your passoword"));
      this.__email = email;
      this.add(email);

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
        this.__submit();
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

    __cancel: function() {
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    },

    __submit: function() {
      console.debug("sends email to reset password to ", this.__email);
      // TODO: flash ...  "email sent..."
      // TODO: query server to send reset email. to user?
      // TODO: if user not in registry, flash "unknown email"?
      // back to login
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }

  }
});

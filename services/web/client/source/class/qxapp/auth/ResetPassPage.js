/** Page to reset reset user's password
 *
 */
qx.Class.define("qxapp.auth.ResetPassPage", {
  extend: qxapp.auth.BaseAuthPage,

  members: {

    // overrides base
    _buildPage: function() {

      let manager = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Reset Password"));

      // email
      let email = new qx.ui.form.TextField();
      email.setRequired(true);
      email.setPlaceholder(this.tr("Introduce your email to reset your passoword"));
      this.add(email);

      manager.add(email, qx.util.Validate.email());

      // submit and cancel buttons
      let grp = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      grp.set({
        marginTop: this._marginFooter
      });

      let btn = new qx.ui.form.Button(this.tr("Submit"));
      btn.setWidth(this._widthBtn);
      grp.add(btn, {
        left: 0
      });

      btn.addListener("execute", function(e) {
        const valid = manager.validate();
        if (valid) {
          this.submit(email.getValue());
        }
      }, this);

      btn = new qx.ui.form.Button(this.tr("Cancel"));
      btn.setWidth(this._widthBtn);
      grp.add(btn, {
        right: 0
      });

      btn.addListener("execute", function(e) {
        this.cancel();
      }, this);

      this.add(grp);
    },

    cancel: function() {
      let login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    },

    submit: function(email) {
      console.debug("sends email to reset password to ", email);
      // TODO: flash ...  "email sent..."
      // TODO: query server to send reset email. to user?
      // TODO: if user not in registry, flash "unknown email"?
      // back to login
      let login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }

  }
});

/** Page to request password reset for a non-logged-in user
 *
 */
qx.Class.define("qxapp.auth.ui.ResetPassRequestPage", {
  extend: qxapp.auth.core.BaseAuthPage,

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {

    // overrides base
    _buildPage: function() {
      let manager = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Reset Password"));

      // email
      let email = new qx.ui.form.TextField();
      email.setRequired(true);
      email.setPlaceholder(this.tr("Introduce your registration email"));
      this.add(email);

      manager.add(email, qx.util.Validate.email());

      // submit and cancel buttons
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      let submitBtn = new qx.ui.form.Button(this.tr("Submit"));
      grp.add(submitBtn, {
        flex:1
      });

      let cancelBtn = new qx.ui.form.Button(this.tr("Cancel"));
      grp.add(cancelBtn, {
        flex:1
      });

      // interaction
      submitBtn.addListener("execute", function(e) {
        const valid = manager.validate();
        if (valid) {
          this.__submit(email);
        }
      }, this);

      cancelBtn.addListener("execute", function(e) {
        this.fireDataEvent("done", null);
      }, this);

      this.add(grp);
    },

    __submit: function(email) {
      console.debug("sends email to reset password to ", email);

      let manager = qxapp.auth.Manager.getInstance();

      let successFun = function(log) {
        this.fireDataEvent("done", log.message);
        qxapp.component.widget.FlashMessenger.getInstance().log(log);
      };

      let failFun = function(msg) {
        msg = msg || this.tr("Could not request password reset");
        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR", "user");
      };

      manager.resetPasswordRequest(email.getValue(), successFun, failFun, this);
    }

  }
});

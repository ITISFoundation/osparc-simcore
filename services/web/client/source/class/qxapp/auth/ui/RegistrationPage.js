
/**
 *
 *  TODO: add a check to prevent bots to register users
*/
qx.Class.define("qxapp.auth.ui.RegistrationPage", {
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

      this._addTitleHeader(this.tr("Registration"));

      // email, pass1 == pass2
      let email = new qx.ui.form.TextField();
      email.setRequired(true);
      email.setPlaceholder(this.tr("Introduce your email"));
      this.add(email);

      let uname = new qx.ui.form.TextField();
      uname.setRequired(true);
      uname.setPlaceholder(this.tr("Introduce a user name"));
      this.add(uname);

      let pass1 = new qx.ui.form.PasswordField();
      pass1.setRequired(true);
      pass1.setPlaceholder(this.tr("Introduce a password"));
      this.add(pass1);

      let pass2 = new qx.ui.form.PasswordField();
      pass2.setRequired(true);
      pass2.setPlaceholder(this.tr("Retype the password"));
      this.add(pass2);

      // interaction
      email.addListener("changeValue", function(e) {
        // Auto-guess
        if (uname.getValue()=== null) {
          let data = e.getData().split("@")[0];
          uname.setValue(qx.lang.String.capitalize(qx.lang.String.clean(data)));
        }
      }, this);

      // validation
      manager.add(email, qx.util.Validate.email());
      manager.add(pass1, function(value, itemForm) {
        const isValid = value !== null && value.length > 2;
        if (!isValid) {
          itemForm.setInvalidMessage("Please enter a password at with least 3 characters.");
        }
        return isValid;
      });
      manager.setValidator(function(_itemForms) {
        const isValid = pass1.getValue() == pass2.getValue();
        if (!isValid) {
          [pass1, pass2].forEach(pass => {
            pass.setInvalidMessage("Passwords do not match.");
            pass.setValid(isValid);
          });
        }
        return isValid;
      });


      // submit & cancel buttons
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
          this.__submit({
            email: email.getValue(),
            username: uname.getValue(),
            pass: pass1.getValue()
          });
        }
      }, this);

      cancelBtn.addListener("execute", function(e) {
        this.fireDataEvent("done", null);
      }, this);

      this.add(grp);
    },

    __submit: function(userData) {
      console.debug("Registering new user");

      let manager = qxapp.auth.Manager.getInstance();
      manager.register(userData, function(success, msg) {
        if (success) {
          this.fireDataEvent("done", msg);
        }
        // TODO: if fails, flash reason (e.g. username already exists)
      }, this);
    }
  }
});

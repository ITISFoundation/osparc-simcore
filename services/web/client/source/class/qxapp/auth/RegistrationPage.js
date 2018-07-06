
/**
 *
 *  TODO: add a check to prevent bots to register users
*/
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
      let manager = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Register"));

      // email, pass1 == pass2
      let email = new qx.ui.form.TextField();
      email.setRequired(true);
      email.setPlaceholder(this.tr("Introduce your email"));
      this.add(email);
      this.__email = email;

      let pass1 = new qx.ui.form.PasswordField();
      pass1.setRequired(true);
      pass1.setPlaceholder(this.tr("Introduce a password"));
      this.add(pass1);
      this.__pass1 = pass1;

      let pass2 = new qx.ui.form.PasswordField();
      pass2.setRequired(true);
      pass2.setPlaceholder(this.tr("Retype your password"));
      this.add(pass2);

      // validation
      manager.add(email, qx.util.Validate.email());
      manager.add(pass1, function(value, itemForm) {
        const isValid = value !== null && value.length > 2;
        if (!isValid) {
          itemForm.setInvalidMessage("Please enter a password at with least 3 characters.");
        }
        return isValid;
      });
      manager.setValidator(function(itemForms) {
        const isValid = pass1.getValue() == pass2.getValue();
        if (!isValid) {
          const msg = "Passwords do not match.";
          pass1.setInvalidMessage(msg);
          pass2.setInvalidMessage(msg);
          pass1.setValid(isValid);
          pass2.setValid(isValid);
        }
        return isValid;
      });


      // submit & cancel buttons
      let grp = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      grp.set({
        marginTop: this._marginFooter
      });

      let submitBtn = this._newButton(this.tr("Submit"));
      grp.add(submitBtn, {
        left: 0
      });

      submitBtn.addListener("execute", function(e) {
        const valid = manager.validate();
        if (valid) {
          this.register({
            email: email.getValue(),
            pass: pass1.getValue()
          });
        }
      }, this);

      let cancelBtn = this._newButton(this.tr("Cancel"));
      grp.add(cancelBtn, {
        right: 0
      });

      cancelBtn.addListener("execute", function(e) {
        this.cancel();
      }, this);

      this.add(grp);
    },

    register: function(data) {
      console.debug("Registering new user");

      // TODO: request server for new user
      // TODO: if fails, flash reason (e.g. username already exists)
      // TODO: if succeeds, switch to login page and flash server message: e.g. "confirmation email has been sent"

      let login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    },

    cancel: function() {
      this.debug("Cancel registration");
      // back to login
      let login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }
  }
});

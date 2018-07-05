
/**
 *
 *  TODO: add a check to prevent bots to register users
*/
qx.Class.define("qxapp.auth.RegistrationPage", {
  extend: qxapp.auth.BaseAuthPage,

  construct: function() {
    this.__manager = new qx.ui.form.validation.Manager();
    this.base(arguments);
  },
  destruct: function() {
    console.debug("destroying RegistrationPage");
  },

  members: {
    __manager: null,

    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Register"));

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

      // Validation
      this.__manager.add(email, qx.util.Validate.email());
      this.__manager.add(pass1, function(value, itemForm) {
        const isValid = value !== null && value.length > 2;
        if (!isValid) {
          itemForm.setInvalidMessage("Please enter a password at with least 3 characters.");
        }
        return isValid;
      });

      this.__manager.setValidator(function(itemForms) {
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


      // buttons
      let grp = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      grp.set({
        marginTop: this._marginFooter
      });

      let submitBtn = this._newButton(this.tr("Submit"));
      grp.add(submitBtn, {
        left: 0
      });

      submitBtn.addListener("execute", function(e) {
        const valid = this.__manager.validate();
        if (valid) {
          this.__register({
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
        this.__cancel();
      }, this);

      this.add(grp);
    },

    __register: function(data) {
      console.debug("Registering new user");

      let user = new qxapp.io.rest.User();

      user.addListener("success", function(e) {
        console.debug("Resource Event", e.toString(), e.getAction());

        // TODO: Flash: a confirmation email has been sent (message by )

        let login = new qxapp.auth.LoginPage();
        login.show();
        this.destroy();
      });


      user.addListener("error", function(e) {
        console.debug("Resource Event", e.toString(), e.getAction());
        // fail if user exists, etc
        // back to login

        // TODO: Flash error
        alert(e.getData());


        this.__manager.resetValidator();
      }, this);

      user.post(data);
    },

    __cancel: function() {
      this.debug("Cancel registration");
      // back to login
      let login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }
  }
});


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
    __email: null,

    // overrides base
    _buildPage: function() {
      let manager = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Registration"));

      // email, pass1 == pass2
      let email = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Introduce your email")
      });
      this.add(email);
      this.__email = email;

      // let uname = new qx.ui.form.TextField().set({
      //   required: true,
      //   placeholder: this.tr("Introduce a user name")
      // });
      // this.add(uname);

      let pass1 = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Introduce a password")
      });
      this.add(pass1);

      let pass2 = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype the password")
      });
      this.add(pass2);

      // interaction
      // email.addListener("changeValue", function(e) {
      //   // Auto-guess
      //   if (uname.getValue()=== null) {
      //     let data = e.getData().split("@")[0];
      //     uname.setValue(qx.lang.String.capitalize(qx.lang.String.clean(data)));
      //   }
      // }, this);

      // validation
      manager.add(email, qx.util.Validate.email());
      manager.add(pass1, function(value, itemForm) {
        const isValid = value !== null && value.length > 2;
        if (!isValid) {
          const msg = qx.locale.Manager.tr("Please enter a password at with least 3 characters.");
          itemForm.setInvalidMessage(msg);
        }
        return isValid;
      });
      manager.setValidator(function(_itemForms) {
        const isValid = pass1.getValue() == pass2.getValue();
        if (!isValid) {
          [pass1, pass2].forEach(pass => {
            pass.set({
              invalidMessage: qx.locale.Manager.tr("Passwords do not match"),
              valid: false
            });
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
            password: pass1.getValue(),
            confirm: pass2.getValue()
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

      let successFun = function(log) {
        // TODO: add flash
        this.fireDataEvent("done", log.message);
      };

      let failFun = function(msg) {
        msg = msg || this.tr("Cannot register user");

        // Flashes via email
        this.__email.set({
          invalidMessage: msg,
          valid: false
        });
      };
      manager.register(userData, successFun, failFun, this);
    }

  }
});

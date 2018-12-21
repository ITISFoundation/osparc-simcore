/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

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
      let validator = new qx.ui.form.validation.Manager();

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
      pass1.addListener("changeValue", e => {
        qxapp.auth.Manager.getInstance().evalPasswordStrength(e.getData(), (strength, rating, improvement) => {
          let msg = "Password is " + rating.toLowerCase() + ".";
          let level = "INFO";

          if (strength < 0.4) {
            level = "WARNING";
            msg += "\n";
            if (improvement) {
              msg += "Possible improvements: \n";
              for (var key in improvement) {
                msg += "- " + improvement[key] + "\n";
              }
            }
          }
          qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, level);
        });
      }, this);

      // email.addListener("changeValue", function(e) {
      //   // Auto-guess
      //   if (uname.getValue()=== null) {
      //     let data = e.getData().split("@")[0];
      //     uname.setValue(qx.lang.String.capitalize(qx.lang.String.clean(data)));
      //   }
      // }, this);



      // validation
      validator.add(email, qx.util.Validate.email());
      validator.setValidator(function(_itemForms) {
        return qxapp.auth.core.Utils.checkSamePasswords(pass1, pass2);
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
        const valid = validator.validate();
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
        this.fireDataEvent("done", log.message);
        qxapp.component.widget.FlashMessenger.getInstance().log(log);
      };

      let failFun = function(msg) {
        msg = msg || this.tr("Cannot register user");
        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      manager.register(userData, successFun, failFun, this);
    }

  }
});

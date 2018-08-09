/** Login page
 *
 * - Form with fields necessary to login
 * - Form data validation
 * - Adds links to register and reset pages. Transitions are fired as events.
 * - To execute login, it delegates on the auth.manager
 * - Minimal layout and apperance is delegated to the selected theme
 */

qx.Class.define("qxapp.auth.ui.LoginPage", {
  extend: qxapp.auth.core.BaseAuthPage,
  include: [
    qxapp.auth.core.MAuth
  ],

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events: {
    "toRegister": "qx.event.type.Event",
    "toReset": "qx.event.type.Event"
  },

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
    __form: null,

    // overrides base
    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      let atm = new qx.ui.basic.Atom().set({
        icon: "qxapp/osparc-white-small.png",
        iconPosition: "top"
      });
      this.add(atm);

      let email = new qx.ui.form.TextField();
      email.setPlaceholder(this.tr("Your email address"));
      email.setRequired(true);
      this.add(email);
      this.__form.add(email, "", qx.util.Validate.email(), "email", null);

      let pass = new qx.ui.form.PasswordField();
      pass.setPlaceholder(this.tr("Your password"));
      pass.setRequired(true);
      this.add(pass);
      this.__form.add(pass, "", null, "password", null);

      // TODO: Temporary disabled. 'Remember me' implies keeping login status in server
      // let chk = new qx.ui.form.CheckBox(this.tr("Remember me"));
      // this.__form.add(chk, "", null, "remember", null);

      let loginBtn = new qx.ui.form.Button(this.tr("Log In"));
      loginBtn.addListener("execute", function() {
        if (this.__form.validate()) {
          this.__login();
        }
      }, this);
      this.add(loginBtn);


      //  create account | forgot password? links
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        separator: "main"
      }));

      let registerBtn = this.createLinkButton(this.tr("Create Account"), function() {
        this.fireEvent("toRegister");
      }, this);

      let forgotBtn = this.createLinkButton(this.tr("Forgot Password?"), function() {
        this.fireEvent("toReset");
      }, this);

      [registerBtn, forgotBtn].forEach(btn => {
        grp.add(btn.set({
          center: true
        }), {
          flex: 1
        });
      });

      this.add(grp);

      // TODO: add here loging with NIH and openID
      // this.add(this.__buildExternals());
    },

    __buildExternals: function() {
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      [this.tr("Login with NIH"), this.tr("Login with OpenID")].forEach(txt => {
        let btn = this.createLinkButton(txt, function() {
          // TODO add here callback
          console.error("Login with external services are still not implemented");
        }, this);

        grp.add(btn.set({
          center: true
        }), {
          flex:1
        });
      });

      return grp;
    },

    __login: function() {
      const email = this.__form.getItems().email;
      const pass = this.__form.getItems().password;

      let manager = qxapp.auth.Manager.getInstance();

      manager.login(email.getValue(), pass.getValue(), function(success, msg) {
        // TODO: implement in flash message.
        // TODO: should get more specific error message produced by server. eg. invalid or unregistered user, ...
        if (success) {
          this.fireDataEvent("done", msg);
        } else {
          if (msg===null) {
            msg = this.tr("Invalid email or password");
          }
          [email, pass].forEach(item => {
            item.set({
              invalidMessage: msg,
              valid: false
            });
          });
        }
      }, this);
    },

    resetValues: function() {
      let fieldItems = this.__form.getItems();
      for (var key in fieldItems) {
        fieldItems[key].resetValue();
      }
    }
  }
});

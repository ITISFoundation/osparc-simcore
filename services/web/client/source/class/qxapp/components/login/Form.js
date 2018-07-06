/**
 * Collection of items and buttons to log-in
 *
 * TODO add translation
*/

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.login.Form", {
  extend: qx.ui.form.Form,

  construct: function() {
    this.base(arguments);

    // TODO: add also login with user-id
    // FIXME: WARNING add [DOM] Password field is not contained in a form: (More info: https://goo.gl/9p2vKq)

    let username = new qx.ui.form.TextField();
    username.set({
      required: true,
      placeholder: this.tr("Your email address"),
      tabIndex: 1
    });
    this.add(username, "", qx.util.Validate.email(), "username", null);

    let password = new qx.ui.form.PasswordField();
    password.set({
      required: true,
      placeholder: this.tr("Your password"),
      tabIndex: username.getTabIndex()+1
    });
    password.setPlaceholder();
    this.add(password, "", null, "password", null);

    // TODO:
    // let remember = new qx.ui.form.CheckBox();
    // this.add(remember, "Remember Me", null, "remember");

    // Buttons
    let submit = new qx.ui.form.Button(this.tr("Sign in"));
    this.addButton(submit);
    submit.setTabIndex(password.getTabIndex()+1);

    // data binding
    this.__controller = new qx.data.controller.Form(null, this);
    this.__model = this.__controller.createModel(); // model created out of the form

    submit.addListener("execute", this.__onSubmitButtonExecuted, this);
  },

  events: {

    // Whenever the login form is submitted: Event data: The new text value of the field.
    "submit": "qx.event.type.Data"
  },

  members: {
    __model: null,
    __controller: null,

    __onSubmitButtonExecuted: function() {
      if (this.validate()) {
        this.fireDataEvent("submit", this.getData());
      }
    },

    flashInvalidLogin: function(msg = null) {
      let username = this.getItems().user;
      let password = this.getItems().password;

      [username, password].forEach(w => {
        w.set({
          invalidMessage: msg === null ? this.tr("Invalid user or password") : msg,
          valid: false
        });
      });
    },

    getData: function() {
      // let serializer = function (object) {
      //   if (object instanceof qx.ui.form.ListItem) {
      //     return object.getLabel();
      //   }
      // };
      // const data = qx.util.Serializer.toJson(this.__model, serializer);

      const data = {
        username: this.__model.getUsername(),
        password: this.__model.getPassword()
      };
      return data;
    }
  }
});

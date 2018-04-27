/**
 * Collection of items and buttons to log-in
 *
 * TODO add translation
*/

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.login.Form", {
  extend: qx.ui.form.Form,

  construct: function() {
    this.base(arguments);

    // Items
    let username = new qx.ui.form.TextField();
    // TODO: add qx.util.Validate.checkEmail
    // TODO: add also login with user-id
    username.setRequired(true);
    username.setPlaceholder("email");
    this.add(username, "User", null, "user", null);

    // FIXME: add [DOM] Password field is not contained in a form: (More info: https://goo.gl/9p2vKq)
    let password = new qx.ui.form.PasswordField();
    password.setRequired(true);
    this.add(password, "Password", null, "password", null);

    // TODO:
    // let remember = new qx.ui.form.CheckBox();
    // this.add(remember, "Remember Me", null, "remember");

    // Buttons
    let submit = new qx.ui.form.Button("Sign in");
    this.addButton(submit);

    // data binding
    this.__controller = new qx.data.controller.Form(null, this);
    this.__model = this.__controller.createModel(); // model created out of the form

    submit.addListener("execute", this.__onSubmitButtonExecuted, this);
  },

  events: {
    /** Whenever the login form is submitted
         *
         *  Event data: The new text value of the field.
         */
    "submit": "qx.event.type.Data"
  },

  members: {
    __model: null,
    __controller: null,

    __onSubmitButtonExecuted : function() {
      if (this.validate()) {
        // copy current model and fire event
        this.fireDataEvent("submit", this.getData());
      }
    },

    getData : function() {
      /*
            let serializer = function (object) {
                if (object instanceof qx.ui.form.ListItem) {
                    return object.getLabel();
                }
            };
            const data = qx.util.Serializer.toJson(this.__model, serializer);
            */
      const data = {
        username: this.__model.getUser(),
        password: this.__model.getPassword()
      };
      return data;
    }
  }
});

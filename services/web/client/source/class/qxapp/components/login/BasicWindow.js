/* global qxapp */

qx.Class.define("qxapp.components.login.BasicWindow", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base();

    this.setCaption("Login");
    this.setShowMinimize(false);
    this.setShowMaximize(false);
    this.setShowClose(false);

    this.setLayout(new qx.ui.layout.VBox());

    let form = new qx.ui.form.Form();
    let userName = new qx.ui.form.TextField();
    // userName.setRequired(true);
    form.add(userName, "Name");
    let password = new qx.ui.form.PasswordField();
    // password.setRequired(true);
    form.add(password, "Password");
    let sendButton = new qx.ui.form.Button("Login");
    let scope = this;
    sendButton.addListener("execute", function() {
      if (form.validate()) {
        if (qxapp.utils.Utils.inHouse(form.getGroups()[0].items[1].getValue())) {
          this.fireDataEvent("Login", true);
          this.close();
        }
      }
    }, scope);
    form.addButton(sendButton);

    this.add(new qx.ui.form.renderer.Single(form));
  },

  events: {
    "Login": "qx.event.type.Event"
  }
});

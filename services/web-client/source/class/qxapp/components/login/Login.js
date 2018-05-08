/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.login.Login", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox(30));

    // standard login. i.e. using app database
    let platformLogin = new qxapp.components.login.Standard();
    this.add(platformLogin, {
      width: "60%"
    });

    // login could offer different types. eg. standard, NIH, lDAP ...
    // or other third parties. Each login can be added as a different
    // widget. Can be e.g. implemented as a Tabview as in gitlab or
    // with buttons on the side as in wix
    let externalLogin = this.__createExternalLogin();
    this.add(externalLogin);

    // TODO: check how to bypass child events to parent
    platformLogin.addListener("login", function(e) {
      this.fireDataEvent("login", e.getData());
    }, this);
  },

  events: {
    "login": "qx.event.type.Data"
  },

  members: {

    __createExternalLogin: function() {
      /**
       * For demo purposes
       */
      let layout = new qx.ui.layout.VBox(10).set({
        alignY: "middle"
      });
      let loginGroup = new qx.ui.container.Composite(layout);

      let loginOpenId = new qx.ui.form.Button().set({
        label: "Continue with openID"
        // FIXME: icon size
        // icon: "https://upload.wikimedia.org/wikipedia/commons/8/88/Openid.svg",
      });
      loginGroup.add(loginOpenId);

      let loginNIH = new qx.ui.form.Button().set({
        label: "Continue with NIH"
        // FIXME: icon size
        // icon: "qxapp/nih-419.png",
      });
      loginGroup.add(loginNIH);

      // Connect dummy
      loginOpenId.addListener("execute", function() {
        const img = "https://upload.wikimedia.org/wikipedia/commons/8/88/Openid.svg";

        let win = new qx.ui.window.Window("External Login");
        win.setLayout(new qx.ui.layout.Basic());
        win.setModal(true);
        win.add(new qx.ui.basic.Image(img));
        win.open();
      });

      loginNIH.addListener("execute", function() {
        const img = "qxapp/nih-419.png";

        let win = new qx.ui.window.Window("External Login");
        win.setLayout(new qx.ui.layout.Basic());
        win.setModal(true);
        win.add(new qx.ui.basic.Image(img));
        win.open();
      });

      return loginGroup;
    }
  }
});

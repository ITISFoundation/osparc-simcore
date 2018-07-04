
qx.Class.define("qxapp.auth.RegisterPage", {
  extend: qx.ui.container.Composite,
  include: [qxapp.auth.MAuthPage],

  construct: function() {
    this.base(arguments);

    // Setup children's layout and widget dims
    this.setLayout(new qx.ui.layout.VBox(10));
    this.set({
      width: 300,
      height: 250
    });

    this.__buildPage();

    // Place this in document's center. TODO: should be automatically reposition of document size changed!?
    var top = parseInt((qx.bom.Document.getHeight() - this.getHeight()) / 2, 10);
    var left = parseInt((qx.bom.Document.getWidth() - this.getWidth()) / 2, 10);
    var app = qx.core.Init.getApplication();
    app.getRoot().add(this, {
      top: top,
      left: left
    });
  },
  destruct: function() {
    console.debug("destroying RegisterPage");
  },

  members: {

    __buildPage: function() {
      var font = new qx.bom.Font(24, ["Arial"]);
      font.setBold(true);
      var txt = "<center><b style='color: #FFFFFF'>" + this.tr("Register") + "</b></center>";
      var lbl = new qx.ui.basic.Label(txt);
      lbl.setFont(font);
      lbl.setRich(true);
      lbl.setWidth(this.getWidth() - 20);
      this.add(lbl);

      var line = new qx.ui.core.Widget();
      line.setHeight(1);
      line.setBackgroundColor("white");
      this.add(line);

      var name = new qx.ui.form.TextField();
      name.setPlaceholder("Introduce your email");
      this.add(name);

      var pass = new qx.ui.form.PasswordField();
      pass.setPlaceholder("Introduce a password");
      this.add(pass);

      var pass2 = new qx.ui.form.PasswordField();
      pass2.setPlaceholder("Retype your password");
      this.add(pass2);

      // buttons
      var grp = new qx.ui.container.Composite();
      grp.setLayout(new qx.ui.layout.Canvas());

      var width = parseInt((this.getWidth() - 30) / 2, 10);
      var btn = new qx.ui.form.Button(this.tr("Submit"));
      btn.setWidth(width);
      grp.add(btn, {
        bottom: 20,
        left: 0
      });

      btn.addListener("execute", function(e) {
        this.__register();
      }, this);

      btn = new qx.ui.form.Button(this.tr("Cancel"));
      btn.setWidth(width);
      grp.add(btn, {
        bottom: 20,
        right: 0
      });

      btn.addListener("execute", function(e) {
        this.__cancel();
      }, this);

      this.add(grp);
    },

    __register: function() {
      this.debug("Registering new user");
      // fail if user exists, etc
      // back to login
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    },

    __cancel: function() {
      this.debug("Cancel registration");
      // back to login
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }
  }
});

qx.Class.define("qxapp.auth.ForgotPage", {
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
    console.debug("destroying ForgotPage");
  },

  members: {
    __email: null,

    __buildPage: function() {
      var font = new qx.bom.Font(24, ["Arial"]);
      font.setBold(true);

      var txt = "<center><b style='color: #FFFFFF'>" + this.tr("Reset Password") + "</b></center>";
      var lbl = new qx.ui.basic.Label(txt);
      lbl.setFont(font);
      lbl.setRich(true);
      lbl.setWidth(this.getWidth() - 20);
      this.add(lbl);

      var line = new qx.ui.core.Widget();
      line.setHeight(1);
      line.setBackgroundColor("white");
      this.add(line);

      var email = new qx.ui.form.TextField();
      email.setPlaceholder(this.tr("Introduce your email to reset your passoword"));
      this.__email = email;
      this.add(email);


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
        this.__submit();
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

    __cancel: function() {
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    },

    __submit: function() {
      console.debug("sends email to reset password to ", this.__email);
      // flash ...  "email sent..."
      // back to login
      var login = new qxapp.auth.LoginPage();
      login.show();
      this.destroy();
    }

  }
});

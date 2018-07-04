qx.Class.define("qxapp.auth.MainPage", {
  extend: qx.ui.container.Composite,
  include: [qxapp.auth.MAuthPage],
  construct: function() {
    this.base(arguments);
    this.setLayout(new qx.ui.layout.VBox(20));
    this.set({
      width:qx.bom.Document.getWidth(),
      height: qx.bom.Document.getHeight()
    });

    this.__buildPage();

    var app = qx.core.Init.getApplication();
    app.getRoot().add(this, {
      top: 0,
      left: 0,
      bottom:0,
      right:0
    });
  },
  destruct: function() {
    console.debug("destroying Main Application");
  },

  members: {
    __buildPage: function() {
      var txt = "<center><b style='color: #FFFFFF'>" + this.tr("Welcome!") + "</b></center>";
      var atm = new qx.ui.basic.Atom(txt).set({
        icon: "auth/itis.png",
        iconPosition: "top"
      });
      atm.setWidth(this.getWidth() - 20);

      var font = new qx.bom.Font(24, ["Arial"]);
      font.setBold(true);

      var lbl = atm.getChildControl("label");
      lbl.setFont(font);
      lbl.setRich(true);
      lbl.setWidth(this.getWidth() - 20);
      this.add(atm);

      //txt = "<center><i style='color: #FFFFFF'>" + this.tr("Loading!") + "</i></center>";
      //atm = new qx.ui.basic.Atom(txt).set({
      //  icon: "http://i.imgur.com/sOX1GUR.gif",
      //  iconPosition: "top"
      //});
      //this.add(atm);
      // TODO loading gif


      var btn = new qx.ui.form.Button(this.tr("Logout"));
      btn.setAllowGrowX(false);
      btn.setAlignX("center");
      this.add(btn);

      btn.addListener("execute", function(e) {
        var page = new qxapp.auth.LoginPage();
        page.show();
        this.destroy();
      }, this);
    }
  }
});

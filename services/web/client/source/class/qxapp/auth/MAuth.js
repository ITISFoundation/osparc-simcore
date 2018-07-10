/**
 * Helpers to build Auth Pages (temporary)
*/
qx.Mixin.define("qxapp.auth.MAuth", {

  members:{

    /**
     * Create link button
     * TODO: create its own widget under qxapp.core.ui
     */
    createLinkButton: function(txt, cbk, ctx) {
      var strForgot = "<center><i style='color: gray'>" + txt + "</i></center>";
      var atm = new qx.ui.basic.Atom(strForgot);
      atm.set({
        cursor: "pointer"
      });
      var lbl = atm.getChildControl("label");
      lbl.setRich(true);
      lbl.setAllowGrowY(true);
      atm.addListener("mouseover", function() {
        atm.setLabel("<u style='color: gray'>" + strForgot + "</u>");
      }, this);
      atm.addListener("mouseout", function() {
        atm.setLabel(strForgot);
      }, this);
      atm.addListener("click", function() {
        cbk.call(this); //  == this.cbk()
      }, ctx);

      return atm;
    },

    /**
     * Custom button creation
     *
     * TODO: move this somewhere else! its own widget?
     * NOTE: DEPRECATED!!!! DO NOT USE
     */
    createButton: function(txt, width, cbk, ctx) {
      var btn = new qx.ui.form.Button(txt);
      btn.set({
        width: width,
        cursor: "pointer"
      });
      btn.addListener("execute", function(e) {
        cbk.call(this); // <= this.call() in ctx
      }, ctx);

      return btn;
    }
  }
});

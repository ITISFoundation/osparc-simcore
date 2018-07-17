/**
 * Helpers to build Auth Pages (temporary)
*/
qx.Mixin.define("qxapp.auth.core.MAuth", {

  members:{

    /**
     * Create link button
     * TODO: create its own widget under qxapp.core.ui.LinkButton (extend Button with different apperance)
     */
    createLinkButton: function(txt, cbk, ctx) {
      txt = "<center><i style='color: gray'>" + txt + "</i></center>";
      let atm = new qx.ui.basic.Atom(txt);
      let lbl = atm.getChildControl("label");
      lbl.setRich(true);
      lbl.setAllowGrowY(true);
      atm.addListener("mouseover", function() {
        atm.setLabel("<u style='color: gray'>" + txt + "</u>");
      }, this);
      atm.addListener("mouseout", function() {
        atm.setLabel(txt);
      }, this);
      atm.addListener("click", function() {
        cbk.call(this); //  == this.cbk()
      }, ctx);

      return atm;
    }

  }
});

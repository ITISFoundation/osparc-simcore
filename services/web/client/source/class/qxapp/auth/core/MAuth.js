/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

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
      const atm = new qxapp.ui.form.LinkButton(txt).set({
        appearance: "link-button"
      });
      atm.addListener("execute", function() {
        cbk.call(this);
      }, ctx);
      return atm;
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsImage", {
  extend: osparc.ui.basic.SVGImage,

  construct: function() {
    this.base(arguments, "osparc/coins-solid.svg");

    const store = osparc.store.Store.getInstance();
    store.addListener("changeContextWallet", this.__updateWallet, this);
    this.__updateWallet();
  },

  members: {
    __updateWallet: function() {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (contextWallet) {
        contextWallet.addListener("changeCreditsAvailable", this.__updateColor, this);
        this.__updateColor();
      }
    },

    __updateColor: function() {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (contextWallet) {
        const credits = contextWallet.getCreditsAvailable();
        const creditsColorKeyword = osparc.desktop.credits.Utils.creditsToColor(credits, "strong-main");
        this.setImageColor(creditsColorKeyword);
      }
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.Utils", {
  type: "static",

  statics: {
    createWalletSelector: function(accessRight = "read") {
      const walletSelector = new qx.ui.form.SelectBox();

      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const store = osparc.store.Store.getInstance();
      let defaultWallet = null;
      store.getWallets().forEach(wallet => {
        if (myGid in wallet.getAccessRights() && wallet.getAccessRights()[myGid][accessRight]) {
          const sbItem = new qx.ui.form.ListItem(wallet.getName());
          sbItem.walletId = wallet.getWalletId();
          walletSelector.add(sbItem);
          if (defaultWallet === null) {
            defaultWallet = sbItem;
          }
        }
      });

      return walletSelector;
    }
  }
});

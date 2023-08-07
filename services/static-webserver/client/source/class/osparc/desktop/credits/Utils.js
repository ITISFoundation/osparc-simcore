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
    createWalletSelector: function(accessRight = "read", onlyActive = false, emptySelection = false) {
      const walletSelector = new qx.ui.form.SelectBox();

      const wallets = osparc.store.Store.getInstance().getWallets();
      if (emptySelection) {
        const sbItem = new qx.ui.form.ListItem(qx.locale.Manager.tr("Select Wallet"));
        sbItem.walletId = null;
        walletSelector.add(sbItem);
      }
      wallets.forEach(wallet => {
        if (onlyActive && wallet.getStatus() !== "ACTIVE") {
          return;
        }
        const found = wallet.getMyAccessRights();
        if (found && found[accessRight]) {
          const sbItem = new qx.ui.form.ListItem(wallet.getName());
          sbItem.walletId = wallet.getWalletId();
          walletSelector.add(sbItem);
        }
      });

      return walletSelector;
    }
  }
});

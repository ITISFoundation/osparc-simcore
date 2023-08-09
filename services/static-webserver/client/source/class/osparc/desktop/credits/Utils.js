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
      const store = osparc.store.Store.getInstance();

      const walletSelector = new qx.ui.form.SelectBox();

      const populateSelectBox = selectBox => {
        selectBox.removeAll();

        const wallets = store.getWallets();
        if (emptySelection) {
          const sbItem = new qx.ui.form.ListItem(qx.locale.Manager.tr("Select Wallet"));
          sbItem.walletId = null;
          selectBox.add(sbItem);
        }
        wallets.forEach(wallet => {
          if (onlyActive && wallet.getStatus() !== "ACTIVE") {
            return;
          }
          const found = wallet.getMyAccessRights();
          if (found && found[accessRight]) {
            const sbItem = new qx.ui.form.ListItem(wallet.getName());
            sbItem.walletId = wallet.getWalletId();
            selectBox.add(sbItem);
          }
        });
      };

      populateSelectBox(walletSelector);
      store.addListener("changeWallets", () => populateSelectBox(walletSelector));

      return walletSelector;
    }
  }
});

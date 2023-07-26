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

qx.Class.define("osparc.desktop.wallets.WalletsView", {
  extend: qx.ui.container.Stack,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  events: {
    "buyCredits": "qx.event.type.Data"
  },

  members: {
    __walletsList: null,
    __walletDetails: null,

    __buildLayout: function() {
      const walletsPage = this.__walletsList = new osparc.desktop.wallets.WalletsList();
      const walletDetails = this.__walletDetails = new osparc.desktop.wallets.WalletDetails();
      this.add(walletsPage);
      this.add(walletDetails);

      walletsPage.addListener("walletSelected", e => {
        const walletId = e.getData();
        this.openWalletDetails(walletId);
      });

      walletDetails.addListener("backToWallets", () => {
        this.setSelection([walletsPage]);
        walletsPage.loadWallets();
      });

      walletsPage.addListener("buyCredits", e => this.fireDataEvent("buyCredits", e.getData()));
    },

    openWalletDetails: function(walletId) {
      const openWalletDetails = walletId2 => {
        const walletModel = this.__walletsList.getWalletModel(walletId2);
        this.__walletDetails.setCurrentWallet(walletModel);
        this.setSelection([this.__walletDetails]);
      };
      if (this.__walletsList.isWalletsLoaded()) {
        openWalletDetails(walletId);
      } else {
        this.__walletsList.addListenerOnce("changeWalletsLoaded", () => openWalletDetails(walletId));
      }
    }
  }
});

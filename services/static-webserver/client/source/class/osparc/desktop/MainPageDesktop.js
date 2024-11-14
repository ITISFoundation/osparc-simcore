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

qx.Class.define("osparc.desktop.MainPageDesktop", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this._add(osparc.notification.RibbonNotifications.getInstance());

    const navBar = new osparc.navigation.NavigationBar();
    navBar.populateLayout();
    // exclude some items from the navigation bar
    navBar.getChildControl("dashboard-label").exclude();
    navBar.getChildControl("dashboard-button").exclude();
    navBar.getChildControl("notifications-button").exclude();
    navBar.getChildControl("help").exclude();

    // exclude all the menu entries except "log-out" from user menu
    const userMenuButton = navBar.getChildControl("user-menu");
    const userMenu = userMenuButton.getMenu();
    // eslint-disable-next-line no-underscore-dangle
    const userMenuEntries = userMenu._getCreatedChildControls();
    Object.entries(userMenuEntries).forEach(([id, userMenuEntry]) => {
      if (!["mini-profile-view", "po-center", "log-out"].includes(id)) {
        userMenuEntry.exclude();
      }
    });
    // exclude also the separators
    userMenu.getChildren().forEach(child => {
      if (child.classname === "qx.ui.menu.Separator") {
        child.exclude();
      }
    });
    this._add(navBar);

    osparc.MaintenanceTracker.getInstance().startTracker();

    const store = osparc.store.Store.getInstance();
    const preloadPromises = [];
    const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
    if (walletsEnabled) {
      preloadPromises.push(store.reloadCreditPrice());
      preloadPromises.push(store.reloadWallets());
    }
    preloadPromises.push(store.getAllClassifiers(true));
    preloadPromises.push(osparc.store.Tags.getInstance().fetchTags());
    Promise.all(preloadPromises)
      .then(() => {
        const desktopCenter = new osparc.desktop.credits.DesktopCenter();
        this._add(desktopCenter, {
          flex: 1
        });

        this.__listenToWalletSocket();
      });
  },

  members: {
    __listenToWalletSocket: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      if (!socket.slotExists("walletOsparcCreditsUpdated")) {
        socket.on("walletOsparcCreditsUpdated", data => {
          const store = osparc.store.Store.getInstance();
          const walletFound = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(data["wallet_id"]));
          if (walletFound) {
            walletFound.setCreditsAvailable(parseFloat(data["osparc_credits"]));
          }
        }, this);
      }
    }
  }
});

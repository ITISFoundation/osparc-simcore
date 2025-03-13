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

qx.Class.define("osparc.desktop.wallets.WalletsList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const listsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    osparc.utils.Utils.setIdToWidget(listsLayout, "walletsList");
    this._add(listsLayout);

    const headerPersonal = this.__createHeader(this.tr("Personal"), true);
    listsLayout.add(headerPersonal);
    this.__noPersonalWalletsLabel = new qx.ui.basic.Label().set({
      value: this.tr("No personal Credit Account found"),
      font: "text-13",
      marginLeft: 10
    });
    listsLayout.add(this.__noPersonalWalletsLabel);
    const listPersonal = this.__createWalletsList("personalWalletsList");
    listsLayout.add(listPersonal);
    this.__personalWalletsModel = this.__createModelFromList(listPersonal);

    const headerShared = this.__createHeader(this.tr("Shared with me"), false);
    listsLayout.add(headerShared);
    this.__noSharedWalletsLabel = new qx.ui.basic.Label().set({
      value: this.tr("No shared Credit Accounts found"),
      font: "text-13",
      marginLeft: 10
    });
    listsLayout.add(this.__noSharedWalletsLabel);
    const listShared = this.__createWalletsList("sharedWalletsList");
    listsLayout.add(listShared);
    this.__sharedWalletsModel = this.__createModelFromList(listShared);

    this.loadWallets();
  },

  events: {
    "walletSelected": "qx.event.type.Data",
    "buyCredits": "qx.event.type.Data"
  },

  properties: {
    walletsLoaded: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeWalletsLoaded"
    }
  },

  members: {
    __noPersonalWalletsLabel: null,
    __noSharedWalletsLabel: null,
    __personalWalletsModel: null,
    __sharedWalletsModel: null,

    getWalletModel: function(walletId) {
      return this.__personalWalletsModel.concat(this.__sharedWalletsModel).toArray().find(
        walletModel => walletModel.getWalletId() === parseInt(walletId)
      );
    },

    __getWalletsFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "walletsList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __createWalletsList: function(widgetId) {
      const walletsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        backgroundColor: "transparent",
        height: null,
        focusable: false
      });
      osparc.utils.Utils.setIdToWidget(walletsUIList, widgetId);
      return walletsUIList;
    },

    __createModelFromList: function(walletsUIList) {
      const walletsModel = new qx.data.Array();
      const walletsCtrl = new qx.data.controller.List(walletsModel, walletsUIList, "name");
      walletsCtrl.setDelegate({
        createItem: () => new osparc.desktop.wallets.WalletListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("walletId", "key", null, item, id);
          ctrl.bindProperty("walletId", "model", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("creditsAvailable", "creditsAvailable", null, item, id);
          ctrl.bindProperty("status", "status", null, item, id);
          ctrl.bindProperty("preferredWallet", "preferredWallet", null, item, id);
          ctrl.bindProperty("autoRecharge", "autoRecharge", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("walletsList");

          item.addListener("openEditWallet", e => this.__openEditWallet(e.getData()));
          item.addListener("openShareWallet", e => this.__walletSelected(e.getData()));
          item.addListener("buyCredits", e => this.fireDataEvent("buyCredits", e.getData()));
          item.addListener("toggleFavourite", e => {
            const {
              walletId
            } = e.getData();
            const preferencesSettings = osparc.Preferences.getInstance();
            preferencesSettings.requestChangePreferredWalletId(parseInt(walletId));
          });
        }
      });

      return walletsModel;
    },

    __walletSelected: function(wallet) {
      this.fireDataEvent("walletSelected", wallet);
    },

    loadWallets: function() {
      this.__personalWalletsModel.removeAll();
      this.__sharedWalletsModel.removeAll();

      const store = osparc.store.Store.getInstance();
      const usersPrimaryGroup = osparc.auth.Data.getInstance().getGroupId()
      store.getWallets().forEach(wallet => {
        if (wallet.getOwner() === usersPrimaryGroup) {
          this.__personalWalletsModel.append(wallet)
        } else {
          this.__sharedWalletsModel.append(wallet)
        }
      });
      this.setWalletsLoaded(true);

      this.__noPersonalWalletsLabel.set({
        visibility: this.__personalWalletsModel.getLength() ? "excluded" : "visible"
      });
      this.__noSharedWalletsLabel.set({
        visibility: this.__sharedWalletsModel.getLength() ? "excluded" : "visible"
      });
    },

    __openEditWallet: function(walletId) {
      const wallet = this.getWalletModel(walletId);
      if (wallet === null) {
        return;
      }

      const walletEditor = new osparc.desktop.wallets.WalletEditor();
      wallet.bind("walletId", walletEditor, "walletId");
      wallet.bind("name", walletEditor, "name");
      wallet.bind("description", walletEditor, "description");
      const title = this.tr("Credit Account Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(walletEditor, title, 400, 250);
      walletEditor.addListener("updateWallet", () => this.__updateWallet(win, walletEditor));
      walletEditor.addListener("cancel", () => win.close());
    },

    __updateWallet: function(win, walletEditor) {
      walletEditor.setIsFetching(true);

      const store = osparc.store.Store.getInstance();
      const walletId = walletEditor.getWalletId();
      const found = store.getWallets().find(wallet => wallet.getWalletId() === walletId);
      if (found) {
        const name = walletEditor.getName();
        const description = walletEditor.getDescription();
        const params = {
          url: {
            "walletId": walletId
          },
          data: {
            "name": name,
            "description": description || null,
            "status": found.getStatus()
          }
        };
        osparc.data.Resources.fetch("wallets", "put", params)
          .then(() => {
            osparc.FlashMessenger.logAs(name + this.tr(" successfully edited"));
            const wallet = osparc.desktop.credits.Utils.getWallet(walletId);
            wallet.set(params.data);
          })
          .catch(err => {
            console.error(err);
            const msg = err.message || this.tr("Something went wrong updating the Credit Account");
            osparc.FlashMessenger.logAs(msg, "ERROR");
          })
          .finally(() => {
            walletEditor.setIsFetching(false);
            win.close();
          });
      }

      win.close();
    },

    __createHeader: function(label, showCurrently) {
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const userWallets = new qx.ui.basic.Label().set({
        value: label,
        alignX: "left",
        rich: true,
        font: "text-14"
      });
      header.add(userWallets);
      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      if (showCurrently) {
        const selectColumn = new qx.ui.basic.Label(this.tr("Currently in use")).set({
          marginRight: 18
        });
        header.add(selectColumn)
      }
      return header;
    }
  }
});

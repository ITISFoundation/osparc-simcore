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

    const msg = this.tr("Credit Accounts are this and that.");
    const intro = new qx.ui.basic.Label().set({
      value: msg,
      alignX: "left",
      rich: true,
      font: "text-13"
    });
    this._add(intro);

    this._add(this.__getWalletsFilter());
    this._add(osparc.data.Roles.createRolesWalletInfo());
    this._add(this.__getWalletsList(), {
      flex: 1
    });

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

  statics: {
    sortWallets: function(a, b) {
      const aPreferredWallet = a.isPreferredWallet();
      const bPreferredWallet = b.isPreferredWallet();
      if (aPreferredWallet) {
        return -1;
      } else if (bPreferredWallet) {
        return 1;
      }
      const aAccessRights = a.getAccessRights();
      const bAccessRights = b.getAccessRights();
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (
        aAccessRights &&
        bAccessRights &&
        aAccessRights.find(ar => ar["gid"] === myGid) &&
        bAccessRights.find(ar => ar["gid"] === myGid)
      ) {
        const aAr = aAccessRights.find(ar => ar["gid"] === myGid);
        const bAr = bAccessRights.find(ar => ar["gid"] === myGid);
        const sorted = osparc.share.Collaborators.sortByAccessRights(aAr, bAr);
        if (sorted !== 0) {
          return sorted;
        }
        if (("getName" in a) && ("getName" in b)) {
          return a.getName().localeCompare(b.getName());
        }
        return 0;
      }
      return 0;
    }
  },

  members: {
    __walletsUIList: null,
    __walletsModel: null,

    getWalletModel: function(walletId) {
      let wallet = null;
      this.__walletsModel.forEach(walletModel => {
        if (walletModel.getWalletId() === parseInt(walletId)) {
          wallet = walletModel;
        }
      });
      return wallet;
    },

    __getWalletsFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "walletsList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getWalletsList: function() {
      const walletsUIList = this.__walletsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "background-main-2"
      });
      walletsUIList.addListener("changeSelection", e => this.__walletSelected(e.getData()), this);

      const walletsModel = this.__walletsModel = new qx.data.Array();
      const walletsCtrl = new qx.data.controller.List(walletsModel, walletsUIList, "name");
      walletsCtrl.setDelegate({
        createItem: () => new osparc.desktop.wallets.WalletListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("walletId", "key", null, item, id);
          ctrl.bindProperty("walletId", "model", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("creditsAvailable", "creditsAvailable", null, item, id);
          ctrl.bindProperty("status", "status", null, item, id);
          ctrl.bindProperty("preferredWallet", "preferredWallet", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("walletsList");
          const thumbanil = item.getChildControl("thumbnail");
          thumbanil.getContentElement().setStyles({
            "border-radius": "16px"
          });

          item.addListener("openEditWallet", e => this.__openEditWallet(e.getData()));
          item.addListener("buyCredits", e => this.fireDataEvent("buyCredits", e.getData()));
          item.addListener("toggleFavourite", e => {
            const {
              walletId
            } = e.getData();
            const preferencesSettings = osparc.Preferences.getInstance();
            preferencesSettings.addListener("changePreferredWalletId", () => this.loadWallets());
            preferencesSettings.requestChangePreferredWalletId(parseInt(walletId));
          });
        }
      });

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(walletsUIList);

      return scrollContainer;
    },

    __walletSelected: function(data) {
      if (data && data.length>0) {
        const wallet = data[0];
        this.fireDataEvent("walletSelected", wallet.getModel());
      }
    },

    loadWallets: function() {
      this.__walletsUIList.resetSelection();
      const walletsModel = this.__walletsModel;
      walletsModel.removeAll();

      const store = osparc.store.Store.getInstance();
      store.getWallets().sort(this.self().sortWallets);
      store.getWallets().forEach(wallet => walletsModel.append(wallet));
      this.setWalletsLoaded(true);
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
      wallet.bind("thumbnail", walletEditor, "thumbnail", {
        converter: val => val ? val : ""
      });
      const title = this.tr("Credit Account Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(walletEditor, title, 400, 250);
      walletEditor.addListener("updateWallet", () => this.__updateWallet(win, walletEditor.getChildControl("save"), walletEditor));
      walletEditor.addListener("cancel", () => win.close());
    },

    __updateWallet: function(win, button, walletEditor) {
      button.setFetching(true);

      const store = osparc.store.Store.getInstance();
      const walletId = walletEditor.getWalletId();
      const found = store.getWallets().find(wallet => wallet.getWalletId() === walletId);
      if (found) {
        const name = walletEditor.getName();
        const description = walletEditor.getDescription();
        const thumbnail = walletEditor.getThumbnail();
        const params = {
          url: {
            "walletId": walletId
          },
          data: {
            "name": name,
            "description": description || null,
            "thumbnail": thumbnail || null,
            "status": found.getStatus()
          }
        };
        osparc.data.Resources.fetch("wallets", "put", params)
          .then(() => {
            osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
            const wallet = osparc.desktop.credits.Utils.getWallet(walletId);
            wallet.set(params.data);
          })
          .catch(err => {
            console.error(err);
            const msg = err.message || this.tr("Something went wrong updating the Credit Account");
            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
          })
          .finally(() => {
            button.setFetching(false);
            win.close();
          });
      }

      button.setFetching(false);
      win.close();
    }
  }
});

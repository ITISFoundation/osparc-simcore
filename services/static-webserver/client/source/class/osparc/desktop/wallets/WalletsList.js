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

    const msg = this.tr("Wallets are this and that.");
    const intro = new qx.ui.basic.Label().set({
      value: msg,
      alignX: "left",
      rich: true,
      font: "text-13"
    });
    this._add(intro);

    this._add(this.__getWalletsFilter());
    this._add(this.__getWalletsList(), {
      flex: 1
    });

    const newWalletButton = this.__getCreateWalletSection();
    newWalletButton.exclude();
    this._add(newWalletButton);
    if (osparc.data.Permissions.getInstance().canDo("user.wallets.create")) {
      // Only users that are managers of organizations can create wallets
      const store = osparc.store.Store.getInstance();
      store.getGroupsOrganizationsWithRights("write")
        .then(orgs => {
          newWalletButton.setVisibility(orgs && orgs.length ? "visible" : "excluded");
        });
    }

    this.loadWallets();
  },

  events: {
    "walletSelected": "qx.event.type.Data"
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
      const sorted = osparc.component.share.Collaborators.sortByAccessRights(a.getAccessRights(), b.getAccessRights());
      if (sorted !== 0) {
        return sorted;
      }
      if (("label" in a) && ("label" in b)) {
        return a["label"].localeCompare(b["label"]);
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

    __getCreateWalletSection: function() {
      const createWalletBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("New Wallet"),
        alignX: "center",
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false
      });
      createWalletBtn.addListener("execute", function() {
        const newWallet = true;
        const walletEditor = new osparc.desktop.wallets.WalletEditor(newWallet);
        const title = this.tr("Wallet Details Editor");
        const win = osparc.ui.window.Window.popUpInWindow(walletEditor, title, 400, 250);
        walletEditor.addListener("createWallet", () => this.__createWallet(win, walletEditor.getChildControl("create"), walletEditor));
        walletEditor.addListener("cancel", () => win.close());
      }, this);
      return createWalletBtn;
    },

    __getWalletsFilter: function() {
      const filter = new osparc.component.filter.TextFilter("text", "walletsList").set({
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
      const walletsCtrl = new qx.data.controller.List(walletsModel, walletsUIList, "label");
      walletsCtrl.setDelegate({
        createItem: () => new osparc.desktop.wallets.WalletListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("walletId", "key", null, item, id);
          ctrl.bindProperty("walletId", "model", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("label", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("credits", "credits", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("walletsList");
          const thumbanil = item.getChildControl("thumbnail");
          thumbanil.getContentElement().setStyles({
            "border-radius": "16px"
          });

          item.addListener("openEditWallet", e => {
            const walletId = e.getData();
            this.__openEditWallet(walletId);
          });

          item.addListener("deleteWallet", e => {
            const walletId = e.getData();
            this.__deleteWallet(walletId);
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

      const newWallet = false;
      const walletEditor = new osparc.desktop.wallets.WalletEditor(newWallet);
      wallet.bind("walletId", walletEditor, "walletId");
      wallet.bind("label", walletEditor, "label");
      wallet.bind("description", walletEditor, "description");
      wallet.bind("thumbnail", walletEditor, "thumbnail", {
        converter: val => val ? val : ""
      });
      const title = this.tr("Wallet Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(walletEditor, title, 400, 250);
      walletEditor.addListener("updateWallet", () => this.__updateWallet(win, walletEditor.getChildControl("save"), walletEditor));
      walletEditor.addListener("cancel", () => win.close());
    },

    __deleteWallet: function(walletId) {
      let wallet = null;
      this.__walletsModel.forEach(walletModel => {
        if (walletModel.getWalletId() === parseInt(walletId)) {
          wallet = walletModel;
        }
      });
      if (wallet === null) {
        return;
      }

      const name = wallet.getLabel();
      const msg = this.tr("Are you sure you want to delete ") + name + "?";
      const win = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const params = {
            url: {
              "walletId": walletId
            }
          };
          osparc.data.Resources.fetch("wallets", "delete", params)
            .then(() => {
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Wallet successfully deleted"), "INFO");
            })
            .catch(err => {
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong deleting ") + name, "ERROR");
              console.error(err);
            })
            .finally(() => win.close());
        }
      }, this);
    },

    __createWallet: function(win, button, walletEditor) {
      const walletId = walletEditor.getWalletId();
      const name = walletEditor.getLabel();
      const description = walletEditor.getDescription();
      const thumbnail = walletEditor.getThumbnail();
      const params = {
        url: {
          "walletId": walletId
        },
        data: {
          "label": name,
          "description": description,
          "thumbnail": thumbnail || null
        }
      };
      osparc.data.Resources.fetch("wallets", "post", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          button.setFetching(false);
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong creating ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        })
        .finally(() => win.close());
    },

    __updateWallet: function(win, button, walletEditor) {
      const walletId = walletEditor.getWalletId();
      const name = walletEditor.getLabel();
      const description = walletEditor.getDescription();
      const thumbnail = walletEditor.getThumbnail();
      const params = {
        url: {
          "walletId": walletId
        },
        data: {
          "label": name,
          "description": description,
          "thumbnail": thumbnail || null
        }
      };
      osparc.data.Resources.fetch("wallets", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
          button.setFetching(false);
          win.close();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        });
    }
  }
});

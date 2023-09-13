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

qx.Class.define("osparc.desktop.wallets.WalletDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this._add(this.__getTitleLayout());
    this._add(this.__getTabs(), {
      flex: 1
    });
  },

  events: {
    "backToWallets": "qx.event.type.Event",
    "buyCredits": "qx.event.type.Data"
  },

  members: {
    __walletModel: null,
    __titleLayout: null,
    __walletListItem: null,
    __membersList: null,

    setWallet: function(walletModel) {
      if (walletModel === null) {
        return;
      }
      this.__walletModel = walletModel;

      const walletListItem = this.__addWalletListItem();
      walletModel.bind("walletId", walletListItem, "key");
      walletModel.bind("walletId", walletListItem, "model");
      walletModel.bind("accessRights", walletListItem, "accessRights");
      walletModel.bind("thumbnail", walletListItem, "thumbnail");
      walletModel.bind("name", walletListItem, "title");
      walletModel.bind("description", walletListItem, "subtitle");
      walletModel.bind("creditsAvailable", walletListItem, "creditsAvailable");
      walletModel.bind("status", walletListItem, "status");
      walletModel.bind("preferredWallet", walletListItem, "preferredWallet");

      walletListItem.addListener("buyCredits", e => this.fireDataEvent("buyCredits", e.getData()));

      this.__membersList.setWallet(walletModel);
    },

    __getTitleLayout: function() {
      const titleLayout = this.__titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const prevBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Back to Credit Accounts list"),
        icon: "@FontAwesome5Solid/arrow-left/20",
        backgroundColor: "transparent"
      });
      prevBtn.addListener("execute", () => this.fireEvent("backToWallets"));
      titleLayout.add(prevBtn);

      this.__addWalletListItem();

      return titleLayout;
    },

    __addWalletListItem: function() {
      if (this.__walletListItem) {
        this.__titleLayout.remove(this.__walletListItem);
      }
      const walletListItem = this.__walletListItem = new osparc.desktop.wallets.WalletListItem();
      walletListItem.getChildControl("options").hide();
      walletListItem.addListener("openEditWallet", () => this.__openEditWallet());
      this.__titleLayout.add(walletListItem, {
        flex: 1
      });
      return walletListItem;
    },

    __openEditWallet: function() {
      const wallet = this.__walletModel;

      const newWallet = false;
      const walletEditor = new osparc.desktop.wallets.WalletEditor(newWallet);
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
      const walletId = walletEditor.getWalletId();
      const name = walletEditor.getName();
      const description = walletEditor.getDescription();
      const thumbnail = walletEditor.getThumbnail();
      const params = {
        url: {
          "walletId": walletId
        },
        data: {
          "name": name,
          "description": description,
          "thumbnail": thumbnail || null,
          "status": this.__walletModel.getStatus()
        }
      };
      osparc.data.Resources.fetch("wallets", "put", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
          osparc.store.Store.getInstance().invalidate("wallets");
          const store = osparc.store.Store.getInstance();
          store.reloadWallets();
          this.__walletModel.set({
            name: name,
            description: description,
            thumbnail: thumbnail || null
          });
        })
        .catch(err => {
          console.error(err);
          const msg = err.message || (this.tr("Something went wrong editing ") + name);
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        })
        .finally(() => {
          button.setFetching(false);
          win.close();
        });
    },

    __createTabPage: function(label, icon) {
      const tabPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox()
      });
      if (label) {
        tabPage.setLabel(label);
      }
      if (icon) {
        tabPage.setIcon(icon);
      }
      tabPage.getChildControl("button").set({
        font: "text-13"
      });
      return tabPage;
    },

    __getTabs: function() {
      const tabView = new qx.ui.tabview.TabView().set({
        contentPadding: 10
      });
      tabView.getChildControl("pane").set({
        backgroundColor: "background-main-2"
      });

      const membersListPage = this.__createTabPage(this.tr("Members"), "@FontAwesome5Solid/users/14");
      const membersList = this.__membersList = new osparc.desktop.wallets.MembersList();
      membersListPage.add(membersList, {
        flex: 1
      });
      tabView.add(membersListPage);

      return tabView;
    }
  }
});

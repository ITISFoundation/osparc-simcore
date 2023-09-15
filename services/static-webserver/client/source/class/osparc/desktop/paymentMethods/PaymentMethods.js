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

qx.Class.define("osparc.desktop.paymentMethods.PaymentMethods", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.getChildControl("intro-text");
    this.getChildControl("add-payment-methods-button");
    this.getChildControl("payment-methods-list-layout");

    this.__fetchPaymentMethods();
  },

  properties: {
    paymentMethods: {
      check: "Array",
      init: [],
      nullable: false,
      apply: "__applyPaymentMethods"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Intro text about payment methods"),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        case "add-payment-methods-button":
          control = new qx.ui.form.Button().set({
            appearance: "strong-button",
            label: this.tr("Add Payment Method"),
            icon: "@FontAwesome5Solid/plus/14",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__addNewPaymentMethod(), this);
          this._add(control);
          break;
        case "payment-methods-list-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __addNewPaymentMethod: function() {
      const wallets = osparc.store.Store.getInstance().getWallets();
      wallets.forEach(wallet => {
        if (wallet.getMyAccessRights()["write"]) {
          const params = {
            url: {
              walletId: wallet.getWalletId()
            }
          };
          osparc.data.Resources.fetch("payments-methods", "init", params);
        }
      });
    },

    __fetchPaymentMethods: function() {
      const listLayout = this.getChildControl("payment-methods-list-layout");
      listLayout.removeAll();

      listLayout.add(new qx.ui.basic.Label().set({
        value: this.tr("Fetching Payment Methods"),
        font: "text-14",
        rich: true,
        wrap: true
      }));

      const promises = [];
      const wallets = osparc.store.Store.getInstance().getWallets();
      wallets.forEach(wallet => {
        if (wallet.getMyAccessRights()["write"]) {
          const params = {
            url: {
              walletId: wallet.getWalletId()
            }
          };
          promises.push(osparc.data.Resources.fetch("payments-methods", "get", params));
        }
      });
      Promise.all(promises)
        .then(paymentMethods => {
          const allPaymentMethods = [];
          paymentMethods.forEach(paymentMethod => allPaymentMethods.push(...paymentMethod));
          listLayout.removeAll();
          if (allPaymentMethods.length) {
            listLayout.add(this.__getPaymentMethodsList(allPaymentMethods));
          } else {
            listLayout.add(new qx.ui.basic.Label().set({
              value: this.tr("No Payment Methods found"),
              font: "text-14",
              rich: true,
              wrap: true
            }));
          }
        })
        .catch(err => console.error(err));
    },

    __getPaymentMethodsList: function(allPaymentMethods) {
      console.log(allPaymentMethods);
      const paymentMethodsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "background-main-2"
      });
      /*
      paymentMethodsUIList.addListener("changeSelection", e => this.__walletSelected(e.getData()), this);

      const walletsModel = this.__walletsModel = new qx.data.Array();
      const walletsCtrl = new qx.data.controller.List(walletsModel, paymentMethodsUIList, "name");
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
      */

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(paymentMethodsUIList);

      return scrollContainer;
    }
  }
});

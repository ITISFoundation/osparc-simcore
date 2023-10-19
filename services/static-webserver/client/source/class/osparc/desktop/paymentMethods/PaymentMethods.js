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
    const walletSelectorLayout = this.getChildControl("wallet-selector-layout");
    const walletSelector = walletSelectorLayout.getChildren()[1];
    this.getChildControl("payment-methods-list-layout");
    this.getChildControl("add-payment-methods-button");

    this.__fetchPaymentMethods();
    walletSelector.addListener("changeSelection", () => this.__fetchPaymentMethods());
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
    __allPaymentMethods: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Credit cards used for payments in your personal Credit Account"),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        case "wallet-selector-layout":
          control = osparc.desktop.credits.Utils.createWalletSelectorLayout("write");
          this._add(control);
          break;
        case "payment-methods-list-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this._add(control, {
            flex: 1
          });
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
      }
      return control || this.base(arguments, id);
    },

    __getSelectedWalletId: function() {
      const walletSelector = this.getChildControl("wallet-selector-layout").getChildren()[1];
      const walletSelection = walletSelector.getSelection();
      return walletSelection && walletSelection.length ? walletSelection[0].walletId : null;
    },

    __addNewPaymentMethod: function() {
      const walletId = this.__getSelectedWalletId();
      if (walletId) {
        const params = {
          url: {
            walletId: walletId
          }
        };
        osparc.data.Resources.fetch("paymentMethods", "init", params)
          .then(() => this.__fetchPaymentMethods());
      }
    },

    __fetchPaymentMethods: function() {
      const listLayout = this.getChildControl("payment-methods-list-layout");
      listLayout.removeAll();

      const fetchingLabel = new qx.ui.basic.Atom().set({
        label: this.tr("Fetching Payment Methods"),
        icon: "@FontAwesome5Solid/circle-notch/12",
        font: "text-14"
      });
      fetchingLabel.getChildControl("icon").getContentElement().addClass("rotate");
      listLayout.add(fetchingLabel);

      const walletId = this.__getSelectedWalletId();
      const params = {
        url: {
          walletId: walletId
        }
      };
      osparc.data.Resources.fetch("paymentMethods", "get", params)
        .then(paymentMethods => {
          listLayout.removeAll();
          if (paymentMethods.length) {
            listLayout.add(this.__populatePaymentMethodsList(paymentMethods));
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

    __populatePaymentMethodsList: function(allPaymentMethods) {
      this.__allPaymentMethods = allPaymentMethods;
      const paymentMethodsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "background-main-2"
      });

      const paymentMethodsModel = this.__paymentMethodsModel = new qx.data.Array();
      const paymentMethodsCtrl = new qx.data.controller.List(paymentMethodsModel, paymentMethodsUIList, "name");
      paymentMethodsCtrl.setDelegate({
        createItem: () => new osparc.desktop.paymentMethods.PaymentMethodListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("idr", "key", null, item, id);
          ctrl.bindProperty("idr", "model", null, item, id);
          ctrl.bindProperty("walletId", "walletId", null, item, id);
          ctrl.bindProperty("cardHolderName", "cardHolderName", null, item, id);
          ctrl.bindProperty("cardType", "cardType", null, item, id);
          ctrl.bindProperty("cardNumberMasked", "cardNumberMasked", null, item, id);
          ctrl.bindProperty("expirationMonth", "expirationMonth", null, item, id);
          ctrl.bindProperty("expirationYear", "expirationYear", null, item, id);
        },
        configureItem: item => {
          item.addListener("openPaymentMethodDetails", e => this.__openPaymentMethodDetails(e.getData()));
          item.addListener("deletePaymentMethod", e => this.__deletePaymentMethod(e.getData()));
        }
      });

      paymentMethodsModel.removeAll();
      allPaymentMethods.forEach(paymentMethod => {
        const paymentMethodModel = qx.data.marshal.Json.createModel(paymentMethod);
        paymentMethodsModel.append(paymentMethodModel);
      });

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(paymentMethodsUIList);

      return scrollContainer;
    },

    __findPaymentMethod: function(idr) {
      return this.__allPaymentMethods.find(paymentMethod => paymentMethod["idr"] === idr);
    },

    __openPaymentMethodDetails: function(idr) {
      const paymentMethod = this.__findPaymentMethod(idr);
      if (paymentMethod) {
        osparc.desktop.paymentMethods.PaymentMethodDetails.popUpInWindow(paymentMethod);
      }
    },

    __deletePaymentMethod: function(idr) {
      const paymentMethod = this.__findPaymentMethod(idr);
      if (paymentMethod) {
        const params = {
          url: {
            walletId: paymentMethod["walletId"],
            paymentMethodId: paymentMethod["idr"]
          }
        };
        osparc.data.Resources.fetch("paymentMethods", "delete", params)
          .then(() => this.__fetchPaymentMethods());
      }
    }
  }
});

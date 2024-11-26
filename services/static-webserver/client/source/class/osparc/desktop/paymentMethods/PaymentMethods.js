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

    const groupsStore = osparc.store.Groups.getInstance();
    const myGid = groupsStore.getMyGroupId();
    const store = osparc.store.Store.getInstance();
    const personalWallet = store.getWallets().find(wallet => wallet.getOwner() === myGid)
    this.__personalWalletId = personalWallet.getWalletId()
    this.__buildLayout()
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

    __buildLayout: function() {
      this._removeAll();

      this.__introLabel = new qx.ui.basic.Label().set({
        value: this.tr("Credit cards used for payments in your personal Credit Account"),
        font: "text-14",
        rich: true,
        wrap: true
      });
      this._add(this.__introLabel);

      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10))
      this.__addPaymentMethodBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("Add Payment Method"),
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false
      });
      this.__addPaymentMethodBtn.addListener("execute", () => this.__addNewPaymentMethod(), this);
      buttonContainer.add(this.__addPaymentMethodBtn);
      this.__fetchingMsg = new qx.ui.basic.Atom().set({
        label: this.tr("Fetching Payment Methods"),
        icon: "@FontAwesome5Solid/circle-notch/12",
        font: "text-14",
        visibility: "excluded"
      });
      this.__fetchingMsg.getChildControl("icon").getContentElement().addClass("rotate");
      buttonContainer.add(this.__fetchingMsg);
      this._add(buttonContainer);

      this.__listContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        allowStretchY: true
      });
      this._add(this.__listContainer, {
        flex: 1
      });

      this.__fetchPaymentMethods()
    },

    __addNewPaymentMethod: function() {
      const walletId = this.__personalWalletId;
      if (walletId) {
        const params = {
          url: {
            walletId
          }
        };
        osparc.data.Resources.fetch("paymentMethods", "init", params)
          .then(data => {
            const gatewayWindow = this.__popUpPaymentGateway(data.paymentMethodId, data.paymentMethodFormUrl);
            osparc.wrapper.WebSocket.getInstance().getSocket().once("paymentMethodAcknowledged", ({ paymentMethodId }) => {
              if (paymentMethodId === data.paymentMethodId) {
                gatewayWindow.close();
                this.__fetchPaymentMethods();
              }
            });
          });
      }
    },

    __cancelPaymentMethod: function(paymentMethodId) {
      // inform backend
      const params = {
        url: {
          walletId: this.__personalWalletId,
          paymentMethodId
        }
      };
      osparc.data.Resources.fetch("paymentMethods", "cancel", params)
        .finally(() => this.__fetchPaymentMethods());
    },

    __windowClosed: function(paymentMethodId) {
      const msg = this.tr("The window was closed. Try again and follow the instructions inside the opened window.");
      osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
      this.__cancelPaymentMethod(paymentMethodId);
    },

    __popUpPaymentGateway: function(paymentMethodId, url) {
      const options = {
        width: 450,
        height: 600
      };

      const pgWindow = osparc.desktop.credits.PaymentGatewayWindow.popUp(
        url,
        "Add payment method",
        options
      );
      // listen to "tap" instead of "execute": the "execute" is not propagated
      pgWindow.getChildControl("close-button").addListener("tap", () => this.__windowClosed(paymentMethodId));

      return pgWindow;
    },

    __fetchPaymentMethods: function() {
      this.__fetchingMsg.setVisibility("visible");
      const walletId = this.__personalWalletId;
      const params = {
        url: {
          walletId
        }
      };
      osparc.data.Resources.fetch("paymentMethods", "get", params)
        .then(paymentMethods => {
          this.__listContainer.removeAll();
          if (paymentMethods.length) {
            this.__listContainer.add(this.__populatePaymentMethodsList(paymentMethods), {
              flex: 1
            });
          } else {
            this.__listContainer.add(new qx.ui.basic.Label().set({
              value: this.tr("No Payment Methods found"),
              font: "text-14",
              rich: true,
              wrap: true
            }));
          }
        })
        .finally(() => this.__fetchingMsg.setVisibility("excluded"))
        .catch(err => {
          console.error(err)
          osparc.FlashMessenger.getInstance().logAs(
            this.tr("We could not retrieve your saved payment methods. Please try again later."),
            "ERROR"
          );
        });
    },

    __populatePaymentMethodsList: function(allPaymentMethods) {
      this.__allPaymentMethods = allPaymentMethods;
      const paymentMethodsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "transparent"
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

      allPaymentMethods.forEach(paymentMethod => {
        const paymentMethodModel = qx.data.marshal.Json.createModel(paymentMethod);
        paymentMethodsModel.append(paymentMethodModel);
      });

      return paymentMethodsUIList;
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
    },

    getPaymentMethods: function() {
      return this.__allPaymentMethods || [];
    }
  }
});

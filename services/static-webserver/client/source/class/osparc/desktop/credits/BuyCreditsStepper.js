/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.BuyCreditsStepper", {
  extend: qx.ui.container.Stack,
  construct(paymentMethods) {
    this.base(arguments);
    this.__paymentMethods = paymentMethods;
    const groupsStore = osparc.store.Groups.getInstance();
    const myGid = groupsStore.getMyGroupId()
    const store = osparc.store.Store.getInstance();
    this.__personalWallet = store.getWallets().find(wallet => wallet.getOwner() === myGid)
    this.__buildLayout()
  },
  events: {
    "completed": "qx.event.type.Event"
  },
  properties: {
    paymentId: {
      check: "String",
      init: null,
      nullable: true
    }
  },
  members: {
    __buildLayout() {
      this.removeAll();
      this.__form = new osparc.desktop.credits.BuyCreditsForm(this.__paymentMethods);
      this.__form.addListener("submit", e => {
        const {
          amountDollars: priceDollars,
          osparcCredits, paymentMethodId
        } = e.getData();
        const params = {
          url: {
            walletId: this.__personalWallet.getWalletId()
          },
          data: {
            priceDollars,
            osparcCredits
          }
        };
        this.__form.setFetching(true);
        if (paymentMethodId) {
          params.url.paymentMethodId = paymentMethodId;
          osparc.data.Resources.fetch("payments", "payWithPaymentMethod", params)
            .then(data => {
              const { paymentId } = data
              osparc.wrapper.WebSocket.getInstance().getSocket().once("paymentCompleted", paymentData => {
                if (paymentId === paymentData.paymentId) {
                  this.__paymentCompleted(paymentData)
                  this.__form.setFetching(false);
                }
              });
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
              this.__form.setFetching(false);
            })
        } else {
          osparc.data.Resources.fetch("payments", "startPayment", params)
            .then(data => {
              const { paymentId, paymentFormUrl } = data;
              this.setPaymentId(paymentId)
              this.__iframe = new qx.ui.embed.Iframe(paymentFormUrl).set({
                decorator: "no-border-2"
              });
              this.add(this.__iframe);
              this.setSelection([this.__iframe])
              osparc.wrapper.WebSocket.getInstance().getSocket().once("paymentCompleted", paymentData => {
                if (paymentId === paymentData.paymentId) {
                  this.__paymentCompleted(paymentData);
                }
              });
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            })
            .finally(() => this.__form.setFetching(false));
        }
      });
      this.__form.addListener("cancel", () => this.fireEvent("completed"));
      this.add(this.__form);
      this.setSelection([this.__form])
    },
    __paymentCompleted(paymentData) {
      if (paymentData && paymentData.completedStatus) {
        const msg = this.tr("Payment ") + osparc.utils.Utils.onlyFirstsUp(paymentData.completedStatus);
        switch (paymentData.completedStatus) {
          case "SUCCESS":
            osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
            break;
          case "PENDING":
            osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
            break;
          case "CANCELED":
          case "FAILED":
            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
            break;
          default:
            console.error("completedStatus unknown");
            break;
        }
      }
      this.fireEvent("completed");
    },
    __isGatewaySelected() {
      const selection = this.getSelection()
      return selection.length === 1 && selection[0] === this.__iframe
    },
    cancelPayment: function() {
      if (this.__isGatewaySelected() && this.getPaymentId()) {
        osparc.data.Resources.fetch("payments", "cancelPayment", {
          url: {
            walletId: this.__personalWallet.getWalletId(),
            paymentId: this.getPaymentId()
          }
        })
      }
    }
  }
});

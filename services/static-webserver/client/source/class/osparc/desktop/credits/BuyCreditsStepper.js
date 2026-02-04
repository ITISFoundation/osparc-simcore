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

    this.__buildLayout()
  },
  events: {
    "completed": "qx.event.type.Event",
    "cancelled": "qx.event.type.Event",
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
      const wallet = osparc.store.Store.getInstance().getMyWallet();
      if (!wallet) {
        const msg = osparc.store.Store.NO_PERSONAL_WALLET_MSG;
        osparc.FlashMessenger.logAs(msg, "WARNING");
        return;
      }

      this.removeAll();
      this.__form = new osparc.desktop.credits.BuyCreditsForm(this.__paymentMethods);
      this.__form.addListener("submit", e => {
        const {
          amountDollars: priceDollars,
          osparcCredits, paymentMethodId
        } = e.getData();
        const params = {
          url: {
            walletId: wallet.getWalletId()
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
              osparc.FlashMessenger.logError(err);
              this.__form.setFetching(false);
            })
        } else {
          osparc.data.Resources.fetch("payments", "startPayment", params)
            .then(data => {
              const { paymentId, paymentFormUrl } = data;
              this.setPaymentId(paymentId)
              this.__iframe = new qx.ui.embed.Iframe(paymentFormUrl).set({
                decorator: "no-border-0"
              });
              this.add(this.__iframe);
              this.setSelection([this.__iframe])
              osparc.wrapper.WebSocket.getInstance().getSocket().once("paymentCompleted", paymentData => {
                if (paymentId === paymentData.paymentId) {
                  this.__paymentCompleted(paymentData);
                }
              });
            })
            .catch(err => osparc.FlashMessenger.logError(err))
            .finally(() => this.__form.setFetching(false));
        }
      });
      this.__form.addListener("cancel", () => this.fireEvent("cancelled"));
      this.add(this.__form);
      this.setSelection([this.__form])
    },
    __paymentCompleted(paymentData) {
      if (paymentData && paymentData.completedStatus) {
        const msg = this.tr("Payment ") + osparc.utils.Utils.onlyFirstsUp(paymentData.completedStatus);
        switch (paymentData.completedStatus) {
          case "SUCCESS":
            osparc.FlashMessenger.logAs(msg, "INFO");
            break;
          case "PENDING":
            osparc.FlashMessenger.logAs(msg, "WARNING");
            break;
          case "CANCELED":
          case "FAILED":
            osparc.FlashMessenger.logError(msg);
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
        const wallet = osparc.store.Store.getInstance().getMyWallet();
        if (!wallet) {
          const msg = osparc.store.Store.NO_PERSONAL_WALLET_MSG;
          osparc.FlashMessenger.logAs(msg, "WARNING");
          return;
        }
        osparc.data.Resources.fetch("payments", "cancelPayment", {
          url: {
            walletId: wallet.getWalletId(),
            paymentId: this.getPaymentId()
          }
        })
      }
    }
  }
});

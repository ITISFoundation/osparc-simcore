/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.BuyCreditsForm", {
  extend: qx.ui.core.Widget,
  construct: function(paymentMethods=[]) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10).set({
      alignX: "center"
    }));

    const title = new qx.ui.basic.Label(this.tr("Buy Credits")).set({
      marginTop: 35,
      font: "title-18"
    });
    this._add(title);

    const subtitle = new qx.ui.basic.Label(this.tr("A one-off, non recurring payment.")).set({
      font: "text-14",
      textAlign: "center"
    });
    this._add(subtitle);

    this._add(this.__getForm(paymentMethods));

    this._add(new qx.ui.core.Spacer(), {
      flex: 1
    });

    this._add(this.__getButtons());
  },

  properties: {
    fetching: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeFetching"
    }
  },

  events: {
    "submit": "qx.event.type.Data",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __amountInput: null,

    __getButtons: function() {
      const buttonsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      })).set({
        marginBottom: 35
      });
      const cancelBtn = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "appmotion-button"
      });
      const buyBtn = this.__buyBtn = new osparc.ui.form.FetchButton(this.tr("Buy Credits")).set({
        appearance: "appmotion-button-action",
        enabled: false
      });
      this.bind("fetching", buyBtn, "fetching");
      cancelBtn.addListener("execute", () => this.fireEvent("cancel"));
      buttonsContainer.add(cancelBtn);
      buyBtn.addListener("execute", () => this.fireDataEvent("submit", {
        paymentMethodId: this.__paymentMethods.getSelection()[0].getModel(),
        ...this.__amountInput.getValues()
      }));
      buttonsContainer.add(buyBtn);
      return buttonsContainer;
    },

    __getForm: function(paymentMethods) {
      const formContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      })).set({
        marginTop: 30
      });
      const amountContainer = this.__amountInput = new osparc.desktop.credits.BuyCreditsInput(osparc.store.Store.getInstance().getCreditPrice());
      amountContainer.addListener("input", e => {
        const {osparcCredits, amountDollars} = e.getData();
        if (!this.__buyBtn.isFetching()) {
          this.__buyBtn.setEnabled(!isNaN(osparcCredits) && !isNaN(amountDollars));
        }
      });
      formContainer.add(amountContainer);

      const paymentMethodContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        marginTop: 30,
        allowStretchX: false
      });
      const paymentMethodLabel = new qx.ui.basic.Label("Pay with").set({
        marginLeft: 15
      });
      paymentMethodContainer.add(paymentMethodLabel);
      const paymentMethodSelect = this.__paymentMethods = new osparc.form.AppMotionSelect().set({
        width: 300,
        allowStretchX: false
      });
      const unsavedCardOption = new qx.ui.form.ListItem("Enter card details in the next step...", null, null);
      paymentMethodSelect.add(unsavedCardOption);
      paymentMethods.forEach(({id, label}) => {
        const item = new qx.ui.form.ListItem(label, null, id);
        paymentMethodSelect.add(item);
      });
      if (paymentMethods.length < 1) {
        paymentMethodSelect.setEnabled(false);
        paymentMethodSelect.setSelection([unsavedCardOption]);
      } else {
        paymentMethodSelect.setSelection([paymentMethodSelect.getChildren()[1]]);
      }
      paymentMethodContainer.add(paymentMethodSelect);
      formContainer.add(paymentMethodContainer);
      return formContainer;
    }
  }
});

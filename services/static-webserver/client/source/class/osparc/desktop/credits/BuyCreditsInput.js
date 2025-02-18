/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.BuyCreditsInput", {
  extend: qx.ui.core.Widget,

  construct(pricePerCredit, currencySymbol = "$") {
    this.base(arguments);

    if (isNaN(pricePerCredit)) {
      return;
    }

    this.__pricePerCredit = pricePerCredit;
    this.__currencySymbol = currencySymbol;
    this._setLayout(new qx.ui.layout.HBox(25).set({
      alignX: "center"
    }));
    this._render();
  },

  events: {
    "input": "qx.event.type.Data"
  },

  members: {
    __pricePerCredit: null,
    __currencySymbol: null,
    __priceInput: null,
    __amountInput: null,
    __totalInput: null,

    _render: function() {
      this._removeAll();

      const [priceContainer, priceInput] = this.__getInputAndLabel(this.tr("Credit Price"), {
        readOnly: true,
        value: this.__pricePerCredit + this.__currencySymbol,
        paddingLeft: 0,
        paddingRight: 0
      });
      this._add(priceContainer);
      this.__priceInput = priceInput;

      const [amountContainer, amountInput] = this.__getSpinnerAndLabel(this.tr("Credit Amount"));
      this.__amountInput = amountInput;
      this._add(amountContainer);

      const [totalContainer, totalInput] = this.__getInputAndLabel(this.tr("Total"), {
        readOnly: true,
        value: "-",
        paddingLeft: 0,
        paddingRight: 0
      });
      this.__totalInput = totalInput;
      const amountChanged = value => {
        totalInput.setValue(value ? 1 * (value * this.__pricePerCredit).toFixed(2) + this.__currencySymbol : "-");
        this.fireDataEvent("input", this.getValues());
      }
      amountInput.getChildControl("textfield").addListener("input", e => amountChanged(e.getData()));
      amountInput.addListener("changeValue", e => amountChanged(e.getData()));
      this._add(totalContainer);

      osparc.store.Store.getInstance().getMinimumAmount()
        .then(minimum => {
          amountInput.set({
            maximum: 100000,
            minimum: Math.ceil(minimum/this.__pricePerCredit),
            value: Math.ceil(minimum/this.__pricePerCredit)
          });
        });
    },

    __getInputAndLabel: function(labelText, inputProps) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignX: "center"
      }));
      const input = new qx.ui.form.TextField().set({
        appearance: "appmotion-buy-credits-input",
        textAlign: "center",
        width: 100,
        ...inputProps
      });
      const label = new qx.ui.basic.Label(labelText);
      container.add(input);
      container.add(label);
      return [container, input];
    },

    __getSpinnerAndLabel: function(labelText, inputProps) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignX: "center"
      }));
      const input = new qx.ui.form.Spinner().set({
        appearance: "appmotion-buy-credits-spinner",
        width: 110,
        ...inputProps
      });
      input.getChildControl("textfield").set({
        font: "text-18",
        textAlign: "center"
      });
      const label = new qx.ui.basic.Label(labelText);
      container.add(input);
      container.add(label);
      return [container, input];
    },

    getValues: function() {
      return {
        osparcCredits: this.__amountInput.getValue(),
        amountDollars: parseFloat(this.__totalInput.getValue().split(this.__currencySymbol)[0])
      }
    }
  }
});

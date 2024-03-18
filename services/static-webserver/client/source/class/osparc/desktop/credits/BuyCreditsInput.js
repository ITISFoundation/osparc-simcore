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
    this.__currencySymbol = currencySymbol
    this.__pricePerCredit = pricePerCredit
    this._setLayout(new qx.ui.layout.HBox(25).set({
      alignX: "center"
    }))
    this._render()
  },

  events: {
    "input": "qx.event.type.Data"
  },

  statics: {
    MINIMUM_TOTAL: 10
  },

  members: {
    _render: function() {
      this._removeAll()

      const [priceContainer, priceInput] = this.__getInputAndLabel("Credit Price", {
        readOnly: true,
        value: this.__pricePerCredit + this.__currencySymbol,
        paddingLeft: 0,
        paddingRight: 0
      })
      this._add(priceContainer)
      this.__priceInput = priceInput

      const [amountContainer, amountInput] = this.__getInputAndLabel("Credit Amount", {
        filter: /^[0-9]*$/ // integers only
      })
      this._add(amountContainer)
      this.__amountInput = amountInput

      const [totalContainer, totalInput] = this.__getInputAndLabel("Total", {
        readOnly: true,
        value: "-",
        paddingLeft: 0,
        paddingRight: 0
      })
      amountInput.addListener("input", e => {
        const value = Number(e.getData());
        totalInput.setValue(value ? 1 * (value * this.__pricePerCredit).toFixed(2) + this.__currencySymbol : "-");
        this.fireDataEvent("input", this.getValues());
      })
      this._add(totalContainer)
      this.__totalInput = totalInput
    },

    __getInputAndLabel: function(labelText, inputProps) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignX: "center"
      }))
      const input = new qx.ui.form.TextField().set({
        appearance: "appmotion-buy-credits-input",
        textAlign: "center",
        width: 80,
        ...inputProps
      })
      const label = new qx.ui.basic.Label(labelText)
      container.add(input)
      container.add(label)
      return [container, input]
    },

    getValues: function() {
      return {
        osparcCredits: parseFloat(this.__amountInput.getValue()),
        amountDollars: parseFloat(this.__totalInput.getValue().split(this.__currencySymbol)[0])
      }
    }
  }
});

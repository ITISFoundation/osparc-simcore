/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.BuyCredits2", {
  extend: qx.ui.container.Composite,
  construct: function(paymentMethods=[]) {
    this.base(arguments, new qx.ui.layout.VBox(10).set({
      alignX: "center"
    }))

    const title = new qx.ui.basic.Label("Buy Credits").set({
      marginTop: 35,
      font: 'title-18'
    })
    const subtitle = new qx.ui.basic.Label("A one-off, non recurring payment.").set({
      font: 'text-14'
    })

    this.add(title)
    this.add(subtitle)
    this.add(this.__getForm(paymentMethods))
    this.add(new qx.ui.core.Spacer(), {
      flex: 1
    })
    this.add(this.__getButtons())
  },
  members: {
    __getButtons: function() {
      const buttonsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: 'center'
      })).set({
        marginBottom: 35
      })
      const cancelBtn = new qx.ui.form.Button("Cancel").set({
        appearance: "appmotion-button"
      })
      const buyBtn = new qx.ui.form.Button("Buy Credits").set({
        appearance: "appmotion-button",
        backgroundColor: "strong-main"
      })
      buttonsContainer.add(cancelBtn)
      buttonsContainer.add(buyBtn)
      return buttonsContainer
    },
    __getForm: function(paymentMethods) {
      const formContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      })).set({
        marginTop: 30
      })
      const amountContainer = new osparc.desktop.credits.BuyCreditsInput(10)
      formContainer.add(amountContainer)

      const paymentMethodContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        marginTop: 30,
        allowStretchX: false
      })
      const paymentMethodLabel = new qx.ui.basic.Label("Pay with").set({
        marginLeft: 15
      })
      paymentMethodContainer.add(paymentMethodLabel)
      const paymentMethodSelect = new osparc.form.AppMotionSelect().set({
        width: 300,
        allowStretchX: false
      })
      const unsavedCardOption = new qx.ui.form.ListItem('Enter card details in the next step...', null, -1)
      paymentMethodSelect.add(unsavedCardOption)
      paymentMethods.forEach(({id, label}) => {
        const item = new qx.ui.form.ListItem(label, null, id)
        paymentMethodSelect.add(item)
      })
      if (paymentMethods.length < 1) {
        paymentMethodSelect.setReadOnly(true)
        paymentMethodSelect.setValue(-1)
      } else {
        paymentMethodSelect.setValue(1)
      }
      paymentMethodContainer.add(paymentMethodSelect)
      formContainer.add(paymentMethodContainer)
      return formContainer
    }
  }
});

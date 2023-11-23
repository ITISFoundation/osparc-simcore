/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.BuyCredits2", {
  extend: qx.ui.container.Composite,
  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox(10).set({
      alignX: "center"
    }))

    const title = new qx.ui.basic.Label("Buy Credits").set({
      font: 'title-18'
    })
    const subtitle = new qx.ui.basic.Label("A one-off, non recurring payment.").set({
      font: 'text-14'
    })

    this.add(title)
    this.add(subtitle)
    this.add(this.__getForm())
    this.add(this.__getButtons())
  },
  members: {
    __getButtons: function() {
      const buttonsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: 'center'
      }))
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
    __getForm: function() {
      const formContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      })).set({
        marginTop: 25
      })
      const amountContainer = new osparc.desktop.credits.BuyCreditsInput(1)
      formContainer.add(amountContainer)
      return formContainer
    }
  }
});

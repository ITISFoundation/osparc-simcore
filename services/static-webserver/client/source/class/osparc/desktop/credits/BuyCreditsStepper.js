/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.BuyCreditsStepper", {
  extend: qx.ui.container.Stack,
  construct(paymentMethods) {
    this.base(arguments)
    this.__form = new osparc.desktop.credits.BuyCreditsForm(paymentMethods);
    this.__form.addListener("submit", e => {
      console.log(e.getData());
      this.__form.setFetching(true)
    })
    this.add(this.__form)
  }
});

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

qx.Class.define("osparc.desktop.credits.PaymentGatewayWindow", {
  type: "static",

  statics: {
    popUp: function(url, id, options, modal, useNativeModalDialog) {
      const blocker = qx.bom.Window.getBlocker();
      blocker.setBlockerColor("#FFF");
      blocker.setBlockerOpacity(0.6);

      const pgWindow = qx.bom.Window.open(
        url,
        id,
        options,
        modal,
        useNativeModalDialog
      );

      // enhance the blocker
      const blockerDomEl = blocker.getBlockerElement();
      blockerDomEl.style.cursor = "pointer";

      // text on blocker
      const label = document.createElement("h1");
      label.innerHTML = "Don’t see the secure Payment Window?<br>Click here to complete your purchase";
      label.style.position = "fixed";
      const labelWidth = 550;
      const labelHeight = 100;
      label.style.width = labelWidth + "px";
      label.style.height = labelHeight + "px";
      const root = qx.core.Init.getApplication().getRoot();
      if (root && root.getBounds()) {
        label.style.left = Math.round(root.getBounds().width/2) - labelWidth/2 + "px";
        label.style.top = Math.round(root.getBounds().height/2) - labelHeight/2 + "px";
      }
      blockerDomEl.appendChild(label);

      blockerDomEl.addEventListener("click", () => pgWindow.focus());

      return pgWindow;
    }
  }
});

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
    popUp: function(url, title, options) {
      const iframe = new qx.ui.embed.Iframe(url).set({
        decorator: "no-border-2"
      })
      return osparc.ui.window.Window.popUpInWindow(iframe, title, options.width, options.height).set({
        clickAwayClose: false
      });
    }
  }
});

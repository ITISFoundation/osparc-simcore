/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.auth.BlurredLoginPageS4LEngineering", {
  extend: qx.ui.embed.Html,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grow());

    this.__loadHtml();
  },

  members: {
    __loadHtml: function() {
      const iframe = new qx.ui.embed.Html();
      iframe.setSource("osparc/S4LEngine_ComingSoon.html");
      this._add(iframe);
    }
  }
});

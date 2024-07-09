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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grow());

    this.__loadHtml();
  },

  members: {
    __loadHtml: function() {
      const htmlEmbed = new qx.ui.embed.Html();
      this._add(htmlEmbed);

      // Fetch the HTML file
      const req = new qx.io.request.Xhr("resource/osparc/S4LEngine_ComingSoon.html");
      req.addListener("success", function(e) {
        var response = e.getTarget().getResponse();
        htmlEmbed.setHtml(response);
      });
      req.send();
    }
  }
});

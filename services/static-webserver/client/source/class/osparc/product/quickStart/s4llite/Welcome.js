/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.quickStart.s4llite.Welcome", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("Quick Start Guide");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const welcomeText = this.tr("Welcome onboard ") + osparc.utils.Utils.capitalize(osparc.auth.Data.getInstance().getUserName()) + ",";
      const welcome = osparc.product.quickStart.Utils.createLabel(welcomeText);
      this._add(welcome);

      const introText = this.tr("\
        This quick user’s guide gives a short introduction to <i>S4L<sup>lite</sup></i>. We will show:<br>\
          - how to get started with a new project,<br>\
          - how to get started from an existing tutorial project<br>\
          - how to open Sim4Life lite desktop simulation projects in <i>S4L<sup>lite</sup></i>,<br>\
          - <i>S4L<sup>lite</sup></i> features, limitations and user interface<br>\
          <br>\
          For more specific technical information, please refer to the Dashboard Manual and the <i>S4L<sup>lite</sup></i> Manual.\
      ");
      const intro = osparc.product.quickStart.Utils.createLabel(introText);
      this._add(intro);

      this._add(new qx.ui.core.Spacer(null, 50));

      const logo = new osparc.ui.basic.Logo().set({
        width: 260,
        height: 110
      });
      this._add(logo);
    }
  }
});

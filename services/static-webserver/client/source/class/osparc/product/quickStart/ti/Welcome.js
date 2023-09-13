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

qx.Class.define("osparc.product.quickStart.ti.Welcome", {
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
        This quick tutorial gives a basic overview of how the TI Planning Tool works and how to navigate through the interface.<br>\
        We will focus on two main aspects, how to:<br>\
        - Use the platform<br>\
        - Get started with a New Plan<br>\
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

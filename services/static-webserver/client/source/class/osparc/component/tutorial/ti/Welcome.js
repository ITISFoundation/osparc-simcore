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

qx.Class.define("osparc.component.tutorial.ti.Welcome", {
  extend: osparc.component.tutorial.SlideBase,

  construct: function() {
    const product = osparc.utils.Utils.getProductName();
    const title = product + this.tr(" Quick Start Guide");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const welcome = new qx.ui.basic.Label().set({
        value: this.tr("Welcome onboard ") + osparc.utils.Utils.capitalize(osparc.auth.Data.getInstance().getUserName()) + ",",
        rich: true,
        wrap: true,
        font: "text-14"
      });
      this._add(welcome);

      const intro = new qx.ui.basic.Label().set({
        value: this.tr("\
          This quick tutorial gives a basic overview of how the TI Planning Tool works and how to navigate through the interface.<br>\
          We will focus on two main aspects, how to:<br>\
          - Use the platform<br>\
          - Get started with a New Plan<br>\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      });
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

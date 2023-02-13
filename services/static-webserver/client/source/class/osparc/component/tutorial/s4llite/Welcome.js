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

qx.Class.define("osparc.component.tutorial.s4llite.Welcome", {
  extend: osparc.component.tutorial.SlideBase,

  construct: function() {
    const title = this.tr("Quick Start Guide");
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
        This quick user’s guide gives a short introduction to S4L lite. We will show:<br>\
          - how to get started with a new project,<br>\
          - how to get started from an existing tutorial project<br>\
          - how to open Sim4Life lite desktop simulation projects in S4L lite,<br>\
          - S4L lite features, limitations and user interface<br>\
          <br>\
          For more specific technical information, please refer to the Dashboard Manual and the S4L lite Manual.\
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

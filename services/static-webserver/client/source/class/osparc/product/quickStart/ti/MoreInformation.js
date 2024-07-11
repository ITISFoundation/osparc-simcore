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

qx.Class.define("osparc.product.quickStart.ti.MoreInformation", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("For more information:");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      osparc.product.quickStart.ti.Slides.footerLinks().forEach(footerItem => {
        this._add(footerItem);
      });
    }
  }
});

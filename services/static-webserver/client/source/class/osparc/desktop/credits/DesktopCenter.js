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

/**
 * A mix between the Billing Center and My Account
 */


qx.Class.define("osparc.desktop.credits.DesktopCenter", {
  extend: osparc.desktop.credits.BillingCenter,

  construct: function() {
    this.base(arguments);

    const page = new osparc.desktop.credits.ProfilePage();
    page.showLabelOnTab();
    this._tabsView.addAt(page, 0);
  }
});

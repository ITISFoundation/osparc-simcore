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

    const page = new osparc.desktop.account.ProfilePage();
    const profilePos = 2; // 0: Miniview, 1: Summary
    this.getChildControl("tabs-view").addAt(page, profilePos);
  }
});

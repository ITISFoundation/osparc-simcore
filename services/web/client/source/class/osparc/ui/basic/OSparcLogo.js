/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Theme dependant oSparc logo
 */
qx.Class.define("osparc.ui.basic.OSparcLogo", {
  extend: qx.ui.basic.Image,

  construct: function() {
    this.base(arguments);

    this.set({
      source: osparc.utils.Utils.getLogoPath(),
      scale: true,
      alignX: "center"
    });

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => {
      this.setSource(osparc.utils.Utils.getLogoPath());
    }, this);
  }
});

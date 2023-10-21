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
 * App/theme dependant logo
 */
qx.Class.define("osparc.ui.basic.Logo", {
  extend: qx.ui.basic.Image,

  construct: function() {
    this.base(arguments);

    this.set({
      scale: true,
      alignX: "center",
      padding: 3
    });

    this.resetSourcePath();

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => this.resetSourcePath(), this);
  },

  members: {
    resetSourcePath: function(long = true) {
      const sourcePath = osparc.product.Utils.getLogoPath(long);
      this.set({
        source: sourcePath
      });
    }
  }
});

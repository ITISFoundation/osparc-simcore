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
      alignX: "center"
    });

    this.__resetSourcePath();

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => {
      this.__resetSourcePath();
    }, this);
  },

  members: {
    __resetSourcePath: function() {
      const sourcePath = osparc.utils.Utils.getLogoPath();
      this.set({
        source: sourcePath
      });
    }
  }
});

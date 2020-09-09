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
qx.Class.define("osparc.ui.basic.Logo", {
  extend: qx.ui.basic.Image,

  construct: function() {
    this.base(arguments);

    this.set({
      source: osparc.utils.Utils.getLogoPath(),
      scale: true,
      alignX: "center"
    });

    osparc.data.Resources.get("statics")
      .then(statics => {
        this.set({
          source: "osparc/s4l_logo.png"
        });
      });

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => {
      this.setSource(osparc.utils.Utils.getLogoPath());

      osparc.data.Resources.get("statics")
        .then(statics => {
          this.set({
            source: "osparc/s4l_logo.png"
          });
        });
    }, this);
  }
});

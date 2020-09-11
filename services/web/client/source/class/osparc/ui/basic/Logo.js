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
      scale: true,
      alignX: "center"
    });

    osparc.data.Resources.get("statics")
      .then(statics => {
        this.__resetSource(statics);
      });

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => {
      osparc.data.Resources.get("statics")
        .then(statics => {
          this.__resetSource(statics);
        });
    }, this);
  },

  members: {
    __resetSource: function(statics) {
      let sourcePath = osparc.utils.Utils.getLogoPath();
      if (statics && ("product" in statics)) {
        if (statics["product"] === "s4l") {
          sourcePath = "osparc/s4l_logo.png";
        } else if (statics["product"] === "ti-solutions") {
          sourcePath = "osparc/ti-solutions.svg";
        }
      }
      this.set({
        source: sourcePath
      });
    }
  }
});

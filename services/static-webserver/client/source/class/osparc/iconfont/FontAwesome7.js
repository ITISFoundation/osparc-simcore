/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Make sure FA7 fonts are copied into the build.
 *
 * @asset(iconfont/fontawesome7/webfonts/*)
 */

qx.Class.define("osparc.iconfont.FontAwesome7", {
  type: "static",

  statics: {
    init: function() {
      const path = "iconfont/fontawesome7/css/all.css";
      const uri = qx.util.ResourceManager.getInstance().toUri(path);
      qx.module.Css.includeStylesheet(uri);
    },
  }
});

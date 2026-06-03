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
 * Ensures FA7 font-face declarations and webfonts
 * are included in the build and loaded at runtime.
 *
 * @asset(iconfont/fontawesome7/fa7-fonts.css)
 * @asset(iconfont/fontawesome7/webfonts/fa-brands-400.woff2)
 */

qx.Class.define("osparc.iconfont.FontAwesome7", {
  type: "static",

  statics: {
    init: function() {
      const path = "iconfont/fontawesome7/fa7-fonts.css";
      const uri = qx.util.ResourceManager.getInstance().toUri(path);
      qx.module.Css.includeStylesheet(uri);
    },
  }
});

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

qx.Class.define("osparc.iconfont.FontAwesome7", {
  type: "static",

  statics: {
    init: function() {
      const path = "iconfont/fontawesome7/css/all.css";
      const uri = qx.util.ResourceManager.getInstance().toUri(path);
      // qx.bom.Stylesheet.includeStylesheet(uri);
      qx.module.Css.includeStylesheet(uri);
    },
  }
});

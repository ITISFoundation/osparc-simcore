/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.AppSummary", {
  extend: qx.core.Object,
  type: "singleton",

  members: {
    getValue: function(key) {
      const statics = osparc.store.Store.getInstance().get("appSummary");
      if (key in statics) {
        return statics[key];
      }
      const errorMsg = `${key} not found in statics`;
      console.warn(errorMsg);
      return null;
    }
  }
});

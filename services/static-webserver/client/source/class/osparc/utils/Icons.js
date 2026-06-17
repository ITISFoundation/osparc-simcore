/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.utils.Icons", {
  type: "static",

  statics: {
    user: function(iconSize) {
      if (iconSize) {
        return "@FontAwesomeSolid/user/" + iconSize;
      }
      return osparc.dashboard.CardBase.SHARED_USER;
    },

    organization: function(iconSize) {
      if (iconSize) {
        return "@FontAwesomeSolid/users/" + iconSize;
      }
      return osparc.dashboard.CardBase.SHARED_ORGS;
    },

    everyone: function(iconSize) {
      if (iconSize) {
        return "@FontAwesomeSolid/globe/" + iconSize;
      }
      return osparc.dashboard.CardBase.SHARED_ALL;
    }
  }
});

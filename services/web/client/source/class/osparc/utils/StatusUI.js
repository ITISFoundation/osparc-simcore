/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for dealing with ports.
 *
 */

qx.Class.define("osparc.utils.StatusUI", {
  type: "static",

  statics: {
    getBorderDecorator: function(state) {
      switch (state) {
        case "SUCCESS":
          return "border-ok";
        case "FAILED":
        case "ABORTED":
          return "border-error";
        case "PENDING":
        case "PUBLISHED":
        case "STARTED":
        case "RETRY":
          return "border-busy";
        case "UNKNOWN":
        case "NOT_STARTED":
        default:
          return "no-border";
      }
    }
  }
});

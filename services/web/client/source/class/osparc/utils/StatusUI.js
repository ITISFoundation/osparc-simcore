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
    getIconSource: function(state) {
      switch (state) {
        // computationals
        case "SUCCESS":
          return "@FontAwesome5Solid/check/12";
        case "FAILED":
        case "ABORTED":
          return "@FontAwesome5Solid/exclamation-circle/12";
        case "PENDING":
        case "PUBLISHED":
        case "STARTED":
        case "RETRY":
          return "@FontAwesome5Solid/circle-notch/12";

        // dynamics
        case "ready":
          return "@FontAwesome5Solid/check/12";
        case "failed":
          return "@FontAwesome5Solid/exclamation-circle/12";
        case "starting":
        case "pending":
        case "pulling":
        case "connecting":
          return "@FontAwesome5Solid/circle-notch/12";

        case "UNKNOWN":
        case "NOT_STARTED":
        default:
          return "";
      }
    },

    getLabelValue: function(state) {
      switch (state) {
        case "ready":
          return this.tr("Ready");
        case "failed":
          return this.tr("Error");
        case "starting":
          return this.tr("Starting...");
        case "pending":
          return this.tr("Pending...");
        case "pulling":
          return this.tr("Pulling...");
        case "connecting":
          return this.tr("Connecting...");
        default:
          return state;
      }
    },

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

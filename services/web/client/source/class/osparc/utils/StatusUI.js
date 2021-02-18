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
 * Collection of methods for dealing status decorators.
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
        case "UNKNOWN":
        case "NOT_STARTED":
          return "";

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

        default:
          return "";
      }
    },

    getLabelValue: function(state) {
      switch (state) {
        // computationals
        case "STARTED":
          return qx.locale.Manager.tr("Running");

        // dynamics
        case "ready":
          return qx.locale.Manager.tr("Ready");
        case "failed":
          return qx.locale.Manager.tr("Error");
        case "starting":
          return qx.locale.Manager.tr("Starting...");
        case "pending":
          return qx.locale.Manager.tr("Pending...");
        case "pulling":
          return qx.locale.Manager.tr("Pulling...");
        case "connecting":
          return qx.locale.Manager.tr("Connecting...");

        default:
          return state;
      }
    },

    getColor: function(state) {
      switch (state) {
        // computationals
        case "SUCCESS":
          return "ready-green";
        case "FAILED":
        case "ABORTED":
          return "failed-red";
        case "PENDING":
        case "PUBLISHED":
        case "STARTED":
        case "RETRY":
          return "busy-orange";
        case "UNKNOWN":
        case "NOT_STARTED":
          return "text";

        // dynamics
        case "ready":
          return "ready-green";
        case "failed":
          return "failed-red";
        case "idle":
        case "starting":
        case "pulling":
        case "pending":
        case "connecting":
          return "busy-orange";

        default:
          return "text";
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
          return "no-border";

        default:
          return "no-border";
      }
    }
  }
});

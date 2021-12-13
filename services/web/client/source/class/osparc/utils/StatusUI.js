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
        case "UNKNOWN":
        case "NOT_STARTED":
          return "";
        case "SUCCESS":
          return "@FontAwesome5Solid/check/12";
        case "PENDING":
        case "PUBLISHED":
        case "STARTED":
        case "RETRY":
          return "@FontAwesome5Solid/circle-notch/12";
        case "FAILED":
        case "ABORTED":
          return "@FontAwesome5Solid/exclamation-circle/12";

        // dynamics
        case "idle":
          return "";
        case "ready":
          return "@FontAwesome5Solid/check/12";
        case "starting":
        case "pending":
        case "pulling":
        case "connecting":
          return "@FontAwesome5Solid/circle-notch/12";
        case "failed":
          return "@FontAwesome5Solid/exclamation-circle/12";

        // ports
        case "modified":
          return "@FontAwesome5Solid/exclamation-circle/12";
        case "up-to-date":
          return "@FontAwesome5Solid/check/12";
        case "running":
          return "@FontAwesome5Solid/circle-notch/12";

        // outputs
        case "busy":
          return "@FontAwesome5Solid/circle-notch/12";
        case "out-of-date":
          return "@FontAwesome5Solid/exclamation-circle/12";
          /*
        case "up-to-date":
          return "@FontAwesome5Solid/check/12";
          */

        default:
          return "";
      }
    },

    getLabelValue: function(state) {
      switch (state) {
        // computationals
        case "STARTED":
          return qx.locale.Manager.tr("Running");
        case "NOT_STARTED":
          return qx.locale.Manager.tr("Idle");

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
        // computationals "running"
        case "UNKNOWN":
        case "NOT_STARTED":
          return "text";
        case "SUCCESS":
          return "ready-green";
        case "PENDING":
        case "PUBLISHED":
        case "STARTED":
        case "RETRY":
          return "busy-orange";
        case "FAILED":
        case "ABORTED":
          return "failed-red";

        // dynamics "interactive"
        case "idle":
          return "text";
        case "ready":
          return "ready-green";
        case "starting":
        case "pulling":
        case "pending":
        case "connecting":
          return "busy-orange";
        case "failed":
          return "failed-red";

        // ports
        case "modified":
          return "busy-orange";
        case "up-to-date":
          return "ready-green";

        // output
        case "busy":
        case "out-of-date":
          return "busy-orange";
          /*
        case "up-to-date":
          return "ready-green";
          */

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

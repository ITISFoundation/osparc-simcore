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

qx.Class.define("osparc.service.StatusUI", {
  type: "static",

  statics: {
    setupFilePickerIcon: function(fpNode, icon) {
      fpNode.bind("outputs", icon, "source", {
        converter: outputs => {
          if (osparc.file.FilePicker.getOutput(outputs)) {
            return "@FontAwesome5Solid/check/12";
          }
          return "@FontAwesome5Solid/file/12";
        },
        onUpdate: (source, target) => {
          if (osparc.file.FilePicker.getOutput(source.getOutputs())) {
            target.setTextColor("ready-green");
          } else {
            target.resetTextColor();
          }
        }
      });
    },

    getIconSource: function(state, size = 12) {
      switch (state) {
        // computationals
        case "UNKNOWN":
        case "NOT_STARTED":
          return "";
        case "PUBLISHED":
        case "PENDING":
        case "WAITING_FOR_RESOURCES":
        case "WAITING_FOR_CLUSTER":
        case "STARTED":
        case "RETRY":
          return "@FontAwesome5Solid/circle-notch/"+size;
        case "SUCCESS":
          return "@FontAwesome5Solid/check/"+size;
        case "FAILED":
        case "ABORTED":
          return "@FontAwesome5Solid/exclamation-circle/"+size;

        // dynamics
        case "idle":
          return "@FontAwesome5Solid/hourglass-end/"+size;
        case "ready":
          return "@FontAwesome5Solid/check/"+size;
        case "starting":
        case "stopping":
        case "pending":
        case "pulling":
        case "connecting":
          return "@FontAwesome5Solid/circle-notch/"+size;
        case "deprecated":
          return "@FontAwesome5Solid/exclamation-triangle/"+size;
        case "retired":
        case "failed":
          return "@FontAwesome5Solid/exclamation-circle/"+size;

        // ports
        case "modified":
          return "@FontAwesome5Solid/exclamation-circle/"+size;
        case "up-to-date":
          return "@FontAwesome5Solid/check/"+size;
        case "running":
          return "@FontAwesome5Solid/circle-notch/"+size;

        // outputs
        case "busy":
          return "@FontAwesome5Solid/circle-notch/"+size;
        case "out-of-date":
          return "@FontAwesome5Solid/exclamation-circle/"+size;
          /*
        case "up-to-date":
          return "@FontAwesome5Solid/check/"+size;
          */

        default:
          return "";
      }
    },

    updateCircleAnimation: function(target) {
      const elem = target.getContentElement();
      if (target.getSource() && target.getSource().includes("circle-notch")) {
        osparc.utils.Utils.addClass(elem, "rotate");
      } else {
        osparc.utils.Utils.removeClass(elem, "rotate");
      }
    },

    getLabelValue: function(state) {
      switch (state) {
        // computationals
        case "STARTED":
          return qx.locale.Manager.tr("Running");
        case "NOT_STARTED":
          return qx.locale.Manager.tr("Idle");
        case "WAITING_FOR_RESOURCES":
          return qx.locale.Manager.tr("Waiting for resources");

        // dynamics
        case "idle":
          return qx.locale.Manager.tr("Idle");
        case "ready":
          return qx.locale.Manager.tr("Ready");
        case "failed":
          return qx.locale.Manager.tr("Failed");
        case "deprecated":
          return qx.locale.Manager.tr("Deprecated");
        case "retired":
          return qx.locale.Manager.tr("Retired");
        case "starting":
          return qx.locale.Manager.tr("Starting...");
        case "stopping":
          return qx.locale.Manager.tr("Stopping...");
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
        case "PUBLISHED":
        case "PENDING":
        case "WAITING_FOR_RESOURCES":
        case "WAITING_FOR_CLUSTER":
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
        case "stopping":
        case "pulling":
        case "pending":
        case "connecting":
          return "busy-orange";
        case "deprecated":
          return "warning-yellow";
        case "retired":
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
        case "PUBLISHED":
        case "PENDING":
        case "WAITING_FOR_RESOURCES":
        case "WAITING_FOR_CLUSTER":
        case "STARTED":
        case "RETRY":
          return "border-busy";
        case "UNKNOWN":
        case "NOT_STARTED":
          return "no-border";

        default:
          return "no-border";
      }
    },

    createServiceDeprecatedChip: function() {
      const chip = new osparc.ui.basic.Chip().set({
        label: osparc.service.Utils.DEPRECATED_SERVICE_TEXT,
        icon: osparc.service.StatusUI.getIconSource("deprecated"),
        textColor: "contrasted-text-dark",
        backgroundColor: osparc.service.StatusUI.getColor("deprecated"),
        allowGrowX: false
      });
      return chip;
    },

    createServiceRetiredChip: function() {
      const chip = new osparc.ui.basic.Chip().set({
        label: osparc.service.Utils.RETIRED_SERVICE_TEXT,
        icon: osparc.service.StatusUI.getIconSource("retired"),
        textColor: "contrasted-text-dark",
        backgroundColor: osparc.service.StatusUI.getColor("retired"),
        allowGrowX: false
      });
      return chip;
    }
  }
});

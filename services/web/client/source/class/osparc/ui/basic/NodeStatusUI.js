/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.basic.NodeStatusUI", {
  extend: qx.ui.basic.Atom,

  construct: function(node) {
    this.base(arguments, this.tr("Idle"), "@FontAwesome5Solid/clock/12");

    this.__node = node;
    this.__label = this.getChildControl("label");
    this.__icon = this.getChildControl("icon");

    if (node.isFilePicker()) {
      this.__setupFilepicker();
    } else if (node.isComputational()) {
      this.__setupComputational();
    } else {
      this.__setupInteractive();
    }
  },

  properties: {
    appearance: {
      init: "chip",
      refine: true
    }
  },

  members: {
    __node: null,
    __label: null,
    __icon: null,

    __addClass: function(element, className) {
      if (element) {
        const currentClass = element.getAttribute("class");
        if (currentClass && currentClass.includes(className.trim())) {
          return;
        }
        element.setAttribute("class", ((currentClass || "") + " " + className).trim());
      }
    },

    __removeClass: function(element, className) {
      const currentClass = element.getAttribute("class");
      if (currentClass) {
        const regex = new RegExp(className.trim(), "g");
        element.setAttribute("class", currentClass.replace(regex, ""));
      }
    },

    __setupComputational: function() {
      this.__node.getStatus().bind("running", this.__label, "value", {
        converter: state => {
          if (state) {
            this.show();
            if (state === "STARTED") {
              state = "Running";
            }
            return qx.lang.String.firstUp(state.toLowerCase());
          }
          this.exclude();
          return null;
        }
      });

      this.__node.getStatus().bind("running", this.__icon, "source", {
        converter: state => osparc.utils.StatusUI.getIconSource(state),
        onUpdate: (source, target) => {
          target.show();
          const state = source.getRunning();
          switch (state) {
            case "SUCCESS":
            case "FAILED":
            case "ABORTED":
              this.__removeClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
              return;
            case "PENDING":
            case "PUBLISHED":
            case "STARTED":
            case "RETRY":
              this.__addClass(this.__icon.getContentElement(), "rotate");
              target.resetTextColor();
              return;
            case "UNKNOWN":
            case "NOT_STARTED":
            default:
              target.exclude();
              return;
          }
        }
      });
    },

    __setupInteractive: function() {
      this.__node.getStatus().bind("interactive", this.__label, "value", {
        converter: state => osparc.utils.StatusUI.getLabelValue(state)
      });

      this.__node.getStatus().bind("interactive", this.__icon, "source", {
        converter: state => osparc.utils.StatusUI.getIconSource(state),
        onUpdate: (source, target) => {
          const state = source.getInteractive();
          switch (state) {
            case null:
              this.__removeClass(this.__icon.getContentElement(), "rotate");
              break;
            case "ready":
            case "failed":
              this.__removeClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
              break;
            default:
              this.__addClass(this.__icon.getContentElement(), "rotate");
              target.resetTextColor();
              break;
          }
        }
      });
    },

    __setupFilepicker: function() {
      const node = this.__node;
      this.__node.getStatus().bind("progress", this.__icon, "source", {
        converter: progress => {
          if (progress === 100) {
            return "@FontAwesome5Solid/check/12";
          }
          return "@FontAwesome5Solid/file/12";
        },
        onUpdate: (source, target) => {
          if (source.getProgress() === 100) {
            target.setTextColor("ready-green");
          } else {
            target.resetTextColor();
          }
        }
      });

      this.__node.getStatus().bind("progress", this.__label, "value", {
        converter: progress => {
          if (progress === 100) {
            return osparc.file.FilePicker.getOutputLabel(node.getOutputs());
          }
          return this.tr("Select a file");
        }
      });
    }
  }
});

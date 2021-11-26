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

    this.__label = this.getChildControl("label");
    this.__icon = this.getChildControl("icon");

    this.__setupBlank();
    if (node) {
      this.setNode(node);
    }
  },

  properties: {
    appearance: {
      init: "chip",
      refine: true
    },

    node: {
      check: "osparc.data.model.Node",
      apply: "__applyNode",
      nullable: false,
      init: null
    }
  },

  statics: {
    addClass: function(element, className) {
      if (element) {
        const currentClass = element.getAttribute("class");
        if (currentClass && currentClass.includes(className.trim())) {
          return;
        }
        element.setAttribute("class", ((currentClass || "") + " " + className).trim());
      }
    },

    removeClass: function(element, className) {
      const currentClass = element.getAttribute("class");
      if (currentClass) {
        const regex = new RegExp(className.trim(), "g");
        element.setAttribute("class", currentClass.replace(regex, ""));
      }
    }
  },

  members: {
    __node: null,
    __label: null,
    __icon: null,

    __applyNode: function(node) {
      this.show();
      if (node.isFilePicker()) {
        this.__setupFilepicker();
      } else if (node.isComputational()) {
        this.__setupComputational();
      } else if (node.isDynamic()) {
        this.__setupInteractive();
      } else {
        this.__setupBlank();
      }
    },

    __setupComputational: function() {
      this.getNode().getStatus().bind("running", this.__label, "value", {
        converter: state => {
          if (state) {
            this.show();
            const labelValue = osparc.utils.StatusUI.getLabelValue(state);
            return qx.lang.String.firstUp(labelValue.toLowerCase());
          }
          this.exclude();
          return null;
        },
        onUpdate: (source, target) => {
          const state = source.getRunning();
          target.setTextColor(osparc.utils.StatusUI.getColor(state));
        }
      });

      this.getNode().getStatus().bind("running", this.__icon, "source", {
        converter: state => osparc.utils.StatusUI.getIconSource(state),
        onUpdate: (source, target) => {
          target.show();
          const state = source.getRunning();
          switch (state) {
            case "SUCCESS":
            case "FAILED":
            case "ABORTED":
              this.self().removeClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
              return;
            case "PENDING":
            case "PUBLISHED":
            case "STARTED":
            case "RETRY":
              this.self().addClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
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
      this.getNode().getStatus().bind("interactive", this.__label, "value", {
        converter: state => osparc.utils.StatusUI.getLabelValue(state),
        onUpdate: (source, target) => {
          const state = source.getInteractive();
          target.setTextColor(osparc.utils.StatusUI.getColor(state));
        }
      });

      this.getNode().getStatus().bind("interactive", this.__icon, "source", {
        converter: state => osparc.utils.StatusUI.getIconSource(state),
        onUpdate: (source, target) => {
          const state = source.getInteractive();
          switch (state) {
            case "ready":
            case "failed":
              this.self().removeClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
              break;
            case "idle":
              this.self().removeClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
              break;
            case "starting":
            case "pulling":
            case "pending":
            case "connecting":
              this.self().addClass(this.__icon.getContentElement(), "rotate");
              target.setTextColor(osparc.utils.StatusUI.getColor(state));
              break;
            default:
              this.self().removeClass(this.__icon.getContentElement(), "rotate");
              target.resetTextColor();
              break;
          }
        }
      });
    },

    __setupFilepicker: function() {
      this.getNode().bind("outputs", this.__icon, "source", {
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

      this.getNode().bind("outputs", this.__label, "value", {
        converter: outputs => {
          if (osparc.file.FilePicker.getOutput(outputs)) {
            let outputLabel = osparc.file.FilePicker.getOutputLabel(outputs);
            if (outputLabel === "" && osparc.file.FilePicker.isOutputDownloadLink(outputs)) {
              outputLabel = osparc.file.FilePicker.extractLabelFromLink(outputs);
            }
            return outputLabel;
          }
          return this.tr("Select a file");
        }
      });
    },

    __setupBlank: function() {
      this.exclude();
    }
  }
});

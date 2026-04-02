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

    this.exclude();
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

  members: {
    __applyNode: function(node) {
      this.show();
      if (node.isFilePicker()) {
        this.__setupFilePicker();
      } else if (node.isComputational()) {
        this.__setupComputational();
      } else if (node.isDynamic()) {
        this.__setupInteractive();
      } else {
        this.exclude();
      }
      node.bind("errors", this, "toolTipText", {
        converter: errors => {
          const parts = [];
          if (errors) {
            errors.forEach(error => {
              parts.push(qx.log.appender.Formatter.escapeHTML(error["msg"]));
              let hint = null;
              if (error["type"] === "runtime.oom") {
                if (osparc.store.StaticInfo.isBillableProduct()) {
                  hint = "Tip: Consider selecting a higher pricing tier with more resources, or contact support for assistance.";
                } else {
                  hint = "Tip: Try increasing the RAM limit in the service's resource settings, or reduce the input data size.";
                }
              } else if (error["type"] === "runtime.timeout") {
                hint = "Tip: The service appeared to be hanging or was not producing any log output. It might have an internal issue or was wrongly configured.";
              }
              if (hint) {
                parts.push(hint);
              }
            });
          }
          return parts.length ? parts.join("<br>") : null;
        }
      });
    },

    __setupComputational: function() {
      this.getNode().getStatus().bind("running", this.getChildControl("label"), "value", {
        converter: state => {
          if (state) {
            this.show();
            const labelValue = osparc.service.StatusUI.getLabelValue(state);
            return qx.lang.String.firstUp(labelValue.toLowerCase());
          }
          this.exclude();
          return null;
        },
        onUpdate: (source, target) => {
          const state = source.getRunning();
          target.setTextColor(osparc.service.StatusUI.getColor(state));
        }
      });

      this.getNode().getStatus().bind("running", this.getChildControl("icon"), "source", {
        converter: state => osparc.service.StatusUI.getIconSource(state),
        onUpdate: (source, target) => {
          target.show();
          const state = source.getRunning();
          switch (state) {
            case "SUCCESS":
            case "FAILED":
            case "ABORTED":
              osparc.utils.Utils.removeClass(this.getChildControl("icon").getContentElement(), "rotate");
              target.setTextColor(osparc.service.StatusUI.getColor(state));
              return;
            case "PUBLISHED":
            case "PENDING":
            case "WAITING_FOR_RESOURCES":
            case "WAITING_FOR_CLUSTER":
            case "STARTED":
            case "RETRY":
              osparc.utils.Utils.addClass(this.getChildControl("icon").getContentElement(), "rotate");
              target.setTextColor(osparc.service.StatusUI.getColor(state));
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
      this.getNode().getStatus().bind("interactive", this.getChildControl("label"), "value", {
        converter: state => osparc.service.StatusUI.getLabelValue(state),
        onUpdate: (source, target) => {
          const state = source.getInteractive();
          target.setTextColor(osparc.service.StatusUI.getColor(state));
        }
      });

      this.getNode().getStatus().bind("interactive", this.getChildControl("icon"), "source", {
        converter: state => osparc.service.StatusUI.getIconSource(state),
        onUpdate: (source, target) => {
          osparc.service.StatusUI.updateCircleAnimation(this.getChildControl("icon"));
          const props = qx.util.PropertyUtil.getProperties(osparc.data.model.NodeStatus);
          const state = source.getInteractive();
          if (props["interactive"]["check"].includes(state)) {
            target.setTextColor(osparc.service.StatusUI.getColor(state));
          } else {
            target.resetTextColor();
          }
        }
      });
    },

    __setupFilePicker: function() {
      this.getChildControl("icon").exclude();

      this.getNode().bind("outputs", this.getChildControl("label"), "value", {
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

      this.getNode().getStatus().addListener("changeProgress", e => {
        const progress = e.getData();
        if (progress > 0 && progress < 100) {
          this.getChildControl("label").setValue(this.tr("Uploading..."));
        }
      });
    }
  }
});

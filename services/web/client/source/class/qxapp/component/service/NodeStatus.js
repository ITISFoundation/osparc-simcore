/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.service.NodeStatus", {
  extend: qx.ui.basic.Atom,

  construct: function(node) {
    this.base(arguments, this.tr("Idle"), "@FontAwesome5Solid/clock/12");

    this.__node = node;
    this.__label = this.getChildControl("label");
    this.__icon = this.getChildControl("icon");

    if (node.isInKey("file-picker")) {
      this.__setupFilepicker();
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

    __setupInteractive: function() {
      this.__node.bind("serviceUrl", this.__label, "value", {
        converter: url => {
          if (url) {
            return this.tr("Ready");
          }
          return this.tr("Loading...");
        }
      });

      this.__node.bind("serviceUrl", this.__icon, "source", {
        converter: url => {
          if (url) {
            return "@FontAwesome5Solid/check/12";
          }
          return "@FontAwesome5Solid/circle-notch/12";
        },
        onUpdate: (source, target) => {
          if (source.getServiceUrl()) {
            this.__removeClass(this.__icon.getContentElement(), "rotate");
            target.setTextColor("ready-green");
          } else {
            this.__addClass(this.__icon.getContentElement(), "rotate");
            target.resetTextColor();
          }
        }
      });
    },

    __setupFilepicker: function() {
      const node = this.__node;
      this.__node.bind("progress", this.__icon, "source", {
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

      this.__node.bind("progress", this.__label, "value", {
        converter: progress => {
          if (progress === 100) {
            const outInfo = node.getOutputValues().outFile;
            if ("label" in outInfo) {
              return outInfo.label;
            }
            const splitFilename = outInfo.path.split("/");
            return splitFilename[splitFilename.length-1];
          }
          return this.tr("Select a file");
        }
      });
    }
  }
});

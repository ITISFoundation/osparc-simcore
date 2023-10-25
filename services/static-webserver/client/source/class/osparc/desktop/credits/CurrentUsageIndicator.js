/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CurrentUsageIndicator", {
  extend: qx.ui.core.Widget,

  construct: function(currentUsage) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    this._createChildControlImpl("credits-label");

    if (currentUsage) {
      this.set({
        currentUsage
      });
    }
  },

  properties: {
    currentUsage: {
      check: "osparc.desktop.credits.CurrentUsage",
      init: null,
      nullable: false,
      apply: "__applyCurrentUsage"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credits-label":
          control = new qx.ui.basic.Label().set({
            font: "text-16"
          });
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __animate: function() {
      const desc = {
        duration: 500,
        timing: "ease-out",
        keyFrames: {
          0: {
            "opacity": 1
          },
          70: {
            "opacity": 0.8
          },
          100: {
            "opacity": 1
          }
        }
      };
      const label = this.getChildControl("credits-label");
      qx.bom.element.Animation.animate(label.getContentElement().getDomElement(), desc);
    },

    __applyCurrentUsage: function(currentUsage) {
      currentUsage.bind("usedCredits", this, "visibility", {
        converter: usedCredits => usedCredits === null ? "excluded" : "visible"
      });
      const label = this.getChildControl("credits-label");
      currentUsage.bind("usedCredits", label, "value", {
        converter: usedCredits => usedCredits + this.tr(" used")
      });
      currentUsage.addListener("changeUsedCredits", e => {
        if (e.getData() !== null) {
          setTimeout(() => this.__animate(), 100);
        }
      });
    }
  }
});

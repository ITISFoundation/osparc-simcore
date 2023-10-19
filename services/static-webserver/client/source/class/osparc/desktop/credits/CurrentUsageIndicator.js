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
  extend: qx.ui.form.Button,

  construct: function(currentUsage) {
    this.base(arguments);

    this.set({
      font: "text-16"
    });

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
    __animate: function() {
      const desc = {
        duration: 500,
        timing: "ease-out",
        keyFrames: {
          0: {
            // "opacity": 1,
            "translate": [null, "0px"]
          },
          30: {
            // "opacity": 1,
            "translate": [null, "10px"]
          },
          100: {
            // "opacity": 0,
            "translate": [null, "-50px"]
          }
        }
      };
      qx.bom.element.Animation.animate(this.getContentElement().getDomElement(), desc);
    },

    __applyCurrentUsage: function(currentUsage) {
      currentUsage.bind("usedCredits", this, "visibility", {
        converter: usedCredits => usedCredits === null ? "excluded" : "visible"
      });
      currentUsage.bind("usedCredits", this, "label", {
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

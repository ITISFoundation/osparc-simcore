/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.Panddy", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      zIndex: 100000
    });
  },

  statics: {
    INTRO_STEPS: [{
      target: null,
      message: qx.locale.Manager.tr("Grüezi!<br>This is Panddy. I'm here to give you hints on how to use oSPARC.")
    }]
  },

  properties: {
    steps: {
      check: "Array",
      init: [],
      nullable: true
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      const pandiSize = 80;
      let control;
      switch (id) {
        case "panddy": {
          control = new qx.ui.basic.Image("osparc/panda.gif").set({
            width: pandiSize,
            height: pandiSize,
            scale: true,
            cursor: "pointer"
          });
          control.addListener("tap", () => this.stop(), this);
          this._add(control, {
            bottom: 0,
            right: 0
          });
          break;
        }
        case "bubble-text":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            backgroundColor: "c05",
            padding: 10,
            rich: true,
            maxWidth: 300
          });
          control.getContentElement().setStyles({
            "border-radius": "8px"
          });
          this._add(control, {
            bottom: pandiSize-20,
            right: pandiSize-20
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    start: function() {
      this.getChildControl("panddy").show();
      this.getChildControl("bubble-text").show();

      this.__toStep(0);

      osparc.product.panddy.Utils.getSteps();
    },

    stop: function() {
      this.getChildControl("panddy").exclude();
      this.getChildControl("bubble-text").exclude();
    },

    __toStep: function(idx = 0) {
      let steps = this.self().INTRO_STEPS;
      if (this.isPropertyInitialized("steps") && this.getSteps() && this.getSteps().length) {
        steps = this.getSteps();
      }
      if (idx >= steps.length) {
        idx = 0;
      }

      this.getChildControl("bubble-text").setValue(steps[idx].message);
    },

    __highlightWidget: function(widget) {
      const thisDom = widget.getContentElement().getDomElement();
      const thisZIndex = parseInt(thisDom.style.zIndex);
      const modalFrame = qx.dom.Hierarchy.getSiblings(thisDom).find(el =>
        // Hack: Qx inserts the modalFrame as a sibling of the window with a -1 zIndex
        parseInt(el.style.zIndex) === thisZIndex - 1
      );
      if (modalFrame) {
        modalFrame.addEventListener("click", () => {
          if (this.isModal() && this.isClickAwayClose() &&
            parseInt(modalFrame.style.zIndex) === parseInt(thisDom.style.zIndex) - 1) {
            this.close();
          }
        });
        modalFrame.style.backgroundColor = "black";
        modalFrame.style.opacity = 0.4;
      }
    }
  }
});

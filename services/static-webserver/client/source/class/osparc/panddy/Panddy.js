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

qx.Class.define("osparc.panddy.Panddy", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      zIndex: 100000
    });

    this.__currentIdx = 0;
  },

  statics: {
    INTRO_STEPS: [{
      target: null,
      message: qx.locale.Manager.tr("Grüezi! This is Panddy. I'm here to give you hints on how to use oSPARC.")
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
    __currentStep: null,
    __currentIdx: null,

    _createChildControlImpl: function(id) {
      const pandiSize = 100;
      let control;
      switch (id) {
        case "panddy": {
          control = new qx.ui.basic.Image("osparc/panda.gif").set({
            width: pandiSize,
            height: pandiSize,
            scale: true
          });
          this._add(control, {
            bottom: 0,
            right: 0
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __createStep: function(element, text) {
      const stepWidget = new osparc.panddy.Step(element, text).set({
        maxWidth: 300
      });
      stepWidget.addListener("closePressed", () => this.stop(), this);
      stepWidget.addListener("nextPressed", () => this.__toStep(this.__currentIdx+1), this);
      return stepWidget;
    },

    start: function() {
      this.getChildControl("panddy").show();

      this.__toStep(0);
    },

    stop: function() {
      this.getChildControl("panddy").exclude();
      if (this.__currentStep) {
        this.__currentStep.exclude();
        this.__currentStep = null;
      }
    },

    __toStep: function(idx = 0) {
      let steps = this.self().INTRO_STEPS;
      if (this.isPropertyInitialized("steps") && this.getSteps() && this.getSteps().length) {
        steps = this.getSteps();
      }
      if (idx >= steps.length) {
        idx = 0;
      }

      this.__currentIdx = idx;
      const step = steps[idx];
      if (this.__currentStep) {
        this.__currentStep.exclude();
        this.__currentStep = null;
      }
      const stepWidget = this.__currentStep = this.__createStep();
      if (step.target) {
        const domEl = document.querySelector(`[osparc-test-id=${step.target}]`);
        const el = qx.ui.core.Widget.getWidgetByElement(domEl);
        stepWidget.setElement(el);
      } else {
        const el = this.getChildControl("panddy");
        stepWidget.setElement(el);
        stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
      }
      if (step.message) {
        stepWidget.setText(step.message);
      }
      stepWidget.show();
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

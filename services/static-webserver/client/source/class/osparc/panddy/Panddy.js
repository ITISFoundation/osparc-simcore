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
      title: qx.locale.Manager.tr("Grüezi!"),
      message: qx.locale.Manager.tr("This is Panddy. I'm here to give you hints on how to use oSPARC.")
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
        maxWidth: 400
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
        const widget = qx.ui.core.Widget.getWidgetByElement(domEl);
        if (step.action === "execute") {
          widget.execute();
        }
        stepWidget.setElement(widget);
      } else {
        const widget = this.getChildControl("panddy");
        if (widget) {
          stepWidget.setElement(widget);
          stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
        } else {
          stepWidget.setElement(widget);
          stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
        }
      }
      if (step.title) {
        stepWidget.setTitle(step.title);
      }
      if (step.message) {
        stepWidget.setText(step.message);
      }
      if (steps.length > 1) {
        stepWidget.set({
          stepIndex: idx+1,
          nSteps: steps.length
        });
      }
      stepWidget.show();
    }
  }
});

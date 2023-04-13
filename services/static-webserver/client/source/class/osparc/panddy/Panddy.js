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
    this.setSequences(this.self().INTRO_SEQUENCES);
  },

  statics: {
    INTRO_SEQUENCES: [{
      id: "panddyIntro",
      name: "Panddy intro",
      description: "Introduction to Panddy",
      steps: [{
        target: null,
        title: qx.locale.Manager.tr("Grüezi!"),
        message: qx.locale.Manager.tr("This is Panddy. I'm here to give you hints on how to use oSPARC.")
      }, {
        preStep: {
          target: "osparc-test-id=userMenuBtn",
          action: "execute"
        },
        target: "osparc-test-id=userMenuMenu",
        message: qx.locale.Manager.tr("You can always find me in the User Menu.")
      }]
    }]
  },

  properties: {
    sequences: {
      check: "Array",
      init: [],
      nullable: true
    },

    steps: {
      check: "Array",
      init: [],
      nullable: true
    }
  },

  members: {
    __currentSequence: null,
    __currentStep: null,
    __currentIdx: null,

    _createChildControlImpl: function(id) {
      const pandiSize = 120;
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

    start: function() {
      this.getChildControl("panddy");
      setTimeout(() => this.__toSequences(), 1000);
    },

    stop: function() {
      this.getChildControl("panddy").exclude();
      if (this.__currentStep) {
        this.__currentStep.exclude();
        this.__currentStep = null;
      }
    },

    __toSequences: function() {
      const sequences = this.getSequences();
      if (sequences.length === 0) {
        this.stop();
      } else if (sequences.length === 1) {
        this.__selectSequence(sequences[0]);
      } else {
        this.__showSequences();
      }
    },

    __showSequences: function(sequences) {
      const seqsWidget = new osparc.panddy.Sequences(sequences);
      const panddy = this.getChildControl("panddy");
      seqsWidget.setElement(panddy);
      seqsWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
      seqsWidget.addListener("sequenceSelected", e => this.__selectSequence(e.getData()));
    },

    __selectSequence: function(sequence) {
      if ("steps" in sequence) {
        this.setSteps(sequence.steps);
        this.__toStepCheck(0);
      }
    },

    __createStep: function(element, text) {
      const stepWidget = new osparc.panddy.Step(element, text).set({
        maxWidth: 400
      });
      stepWidget.addListener("closePressed", () => this.stop(), this);
      stepWidget.addListener("nextPressed", () => this.__toStepCheck(this.__currentIdx+1), this);
      return stepWidget;
    },

    __toStepCheck: function(idx = 0) {
      const steps = this.getSteps();
      if (idx >= steps.length) {
        idx = 0;
      }

      this.__currentIdx = idx;
      const step = steps[idx];
      if (this.__currentStep) {
        this.__currentStep.exclude();
        this.__currentStep = null;
      }

      if (step.preStep) {
        const preStep = step.preStep;
        if (preStep.target) {
          const domEl = document.querySelector(`[${preStep.target}]`);
          const widget = qx.ui.core.Widget.getWidgetByElement(domEl);
          if (preStep.action === "execute") {
            widget.execute();
          }
          setTimeout(() => this.__toStep(steps, idx), 1000);
        }
      } else {
        this.__toStep(steps, idx);
      }
    },

    __toStep: function(steps, idx) {
      const step = steps[idx];
      const stepWidget = this.__currentStep = this.__createStep();
      let targetWidget = null;
      if (step.target) {
        const domEl = document.querySelector(`[${step.target}]`);
        targetWidget = qx.ui.core.Widget.getWidgetByElement(domEl);
      }
      if (targetWidget) {
        if (step.action === "execute") {
          targetWidget.execute();
        }
        stepWidget.setElement(targetWidget);
      } else {
        const panddy = this.getChildControl("panddy");
        stepWidget.setElement(panddy);
        stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
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
      setTimeout(() => {
        stepWidget.exclude();
        stepWidget.show();
      }, 50); // Hacky: Execute async and give some time for the relevant properties to be set
    }
  }
});

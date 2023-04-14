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
      name: "Panddy intro",
      description: "Introduction to Panddy",
      steps: [{
        target: null,
        title: qx.locale.Manager.tr("Grüezi!"),
        message: qx.locale.Manager.tr("This is Panddy. I'm here to give you hints on how to use the application.")
      }, {
        preStep: {
          target: "osparc-test-id=userMenuBtn",
          action: "open"
        },
        target: "osparc-test-id=userMenuMenu",
        orientation: "left",
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
    __currentBuble: null,
    __currentIdx: null,

    _createChildControlImpl: function(id) {
      const pandiSize = 140;
      let control;
      switch (id) {
        case "panddy": {
          control = new qx.ui.basic.Image("osparc/panda.gif").set({
            width: pandiSize,
            height: pandiSize,
            scale: true,
            cursor: "pointer"
          });
          control.addListener("tap", () => this.stop());
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
      this.getChildControl("panddy").show();
      setTimeout(() => this.__toSequences(), 200);
    },

    stop: function() {
      this.getChildControl("panddy").exclude();
      this.__removeCurrentBuble();
    },

    __removeCurrentBuble: function() {
      if (this.__currentBuble) {
        qx.core.Init.getApplication().getRoot().remove(this.__currentBuble);
        this.__currentBuble = null;
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

    __showSequences: function() {
      const panddy = this.getChildControl("panddy");
      panddy.show();
      setTimeout(() => {
        const sequences = this.getSequences();
        const seqsWidget = new osparc.panddy.Sequences(panddy, sequences);
        seqsWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
        seqsWidget.addListener("sequenceSelected", e => {
          seqsWidget.exclude();
          this.__selectSequence(e.getData());
        });
        seqsWidget.show();
      }, 200);
    },

    __selectSequence: function(sequence) {
      if ("steps" in sequence) {
        this.setSteps(sequence.steps);
        this.__toStepCheck(0);
      }
    },

    __toStepCheck: function(idx = 0) {
      const steps = this.getSteps();
      if (idx >= steps.length) {
        idx = 0;
      }

      this.__removeCurrentBuble();
      this.__currentIdx = idx;
      const step = steps[idx];
      if (step.preStep) {
        const preStep = step.preStep;
        if (preStep.target) {
          const el = document.querySelector(`[${preStep.target}]`);
          const widget = qx.ui.core.Widget.getWidgetByElement(el);
          if (widget && preStep.action) {
            widget[preStep.action]();
          }
          setTimeout(() => this.__toStep(steps, idx), 200);
        }
      } else {
        this.__toStep(steps, idx);
      }
    },

    __createStep: function(element, text) {
      const stepWidget = new osparc.panddy.Step(element, text).set({
        maxWidth: 400
      });
      [
        "skipPressed",
        "endPressed"
      ].forEach(evName => stepWidget.addListener(evName, () => this.stop(), this));
      stepWidget.addListener("nextPressed", () => this.__toStepCheck(this.__currentIdx+1), this);
      return stepWidget;
    },

    __toStep: async function(steps, idx) {
      const step = steps[idx];
      const stepWidget = this.__currentBuble = this.__createStep();
      let targetWidget = null;
      if (step.target) {
        const el = document.querySelector(`[${step.target}]`);
        targetWidget = qx.ui.core.Widget.getWidgetByElement(el);
      }
      if (targetWidget) {
        if (step.action) {
          targetWidget[step.action]();
        }
        stepWidget.setElement(targetWidget);
        if (step.orientation) {
          stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.textToOrientation(step.orientation));
        }
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
      // eslint-disable-next-line no-underscore-dangle
      setTimeout(() => stepWidget.__updatePosition(), 10); // Hacky: Execute async and give some time for the relevant properties to be set
    }
  }
});

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

    this.setTours(this.self().INTRO_TOUR);
  },

  statics: {
    INTRO_TOUR: [{
      name: "Panddy intro",
      description: "Introduction to Panddy",
      steps: [{
        anchorEl: null,
        title: qx.locale.Manager.tr("Grüezi!"),
        text: qx.locale.Manager.tr("This is Panddy. I'm here to give you hints on how to use the application.")
      }, {
        preStep: {
          anchorEl: "osparc-test-id=userMenuBtn",
          action: "open"
        },
        anchorEl: "osparc-test-id=userMenuMenu",
        placement: "left",
        text: qx.locale.Manager.tr("You can always find me in the User Menu.")
      }]
    }]
  },

  properties: {
    tours: {
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
      const pandiSize = 150;
      let control;
      switch (id) {
        case "panddy": {
          control = new qx.ui.basic.Image("osparc/panda.gif").set({
            width: pandiSize,
            height: pandiSize,
            scale: true,
            cursor: "pointer"
          });
          control.addListener("tap", () => {
            if (control.getSource().includes("pand")) {
              control.setSource("osparc/crocky.gif");
            } else {
              control.setSource("osparc/panda.gif");
            }
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
      this.getChildControl("panddy").show();
      setTimeout(() => this.__toSequences(), 200);
    },

    stop: function() {
      this.__removeCurrentBuble();
      this.getChildControl("panddy").exclude();
    },

    __removeCurrentBuble: function() {
      if (this.__currentBuble) {
        qx.core.Init.getApplication().getRoot().remove(this.__currentBuble);
        this.__currentBuble.exclude();
        this.__currentBuble = null;
      }
    },

    __toSequences: function() {
      const tours = this.getTours();
      const dontShow = osparc.utils.Utils.localCache.getLocalStorageItem("panddyDontShow");
      if (tours.length === 0 || (tours === this.self().INTRO_TOUR && dontShow === "true")) {
        this.stop();
        return;
      }

      if (tours.length === 1) {
        this.__selectTour(tours[0]);
      } else {
        this.__showTours();
      }
    },

    __showTours: function() {
      const panddy = this.getChildControl("panddy");
      panddy.show();
      setTimeout(() => {
        const tours = this.getTours();
        const toursWidget = new osparc.panddy.Tours(panddy, tours);
        toursWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
        toursWidget.addListener("tourSelected", e => {
          toursWidget.exclude();
          this.__selectTour(e.getData());
        });
        toursWidget.show();
      }, 200);
    },

    __selectTour: function(tour) {
      if ("steps" in tour) {
        this.setSteps(tour.steps);
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
        if (preStep.anchorEl) {
          const el = document.querySelector(`[${preStep.anchorEl}]`);
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
      if (step.anchorEl) {
        const el = document.querySelector(`[${step.anchorEl}]`);
        targetWidget = qx.ui.core.Widget.getWidgetByElement(el);
      }
      if (targetWidget) {
        if (step.action) {
          targetWidget[step.action]();
        }
        stepWidget.setElement(targetWidget);
        if (step.placement) {
          stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.textToOrientation(step.placement));
        }
      } else {
        const panddy = this.getChildControl("panddy");
        stepWidget.setElement(panddy);
        stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.ORIENTATION.LEFT);
      }
      if (step.title) {
        stepWidget.setTitle(step.title);
      }
      if (step.text) {
        stepWidget.setText(step.text);
      }
      if (steps.length > 1) {
        stepWidget.set({
          stepIndex: idx+1,
          nSteps: steps.length
        });
      }

      if (this.getTours() === this.self().INTRO_TOUR) {
        const dontShowCB = osparc.product.tutorial.Utils.createDontShowAgain("panddyDontShow");
        stepWidget.add(dontShowCB);
      }

      stepWidget.show();
      // eslint-disable-next-line no-underscore-dangle
      setTimeout(() => stepWidget.__updatePosition(), 10); // Hacky: Execute async and give some time for the relevant properties to be set
    }
  }
});

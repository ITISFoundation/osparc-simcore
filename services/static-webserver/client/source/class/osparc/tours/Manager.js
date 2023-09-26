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

qx.Class.define("osparc.tours.Manager", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "guided-torus", this.tr("Guided Tours"));

    this.set({
      layout: new qx.ui.layout.VBox(20),
      contentPadding: 15,
      modal: true,
      width: 300,
      height: 300,
      showMaximize: false,
      showMinimize: false
    });

    this.__buildLayout();
  },

  properties: {
    tours: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeTours"
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
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("This collection of Guided Tours will show you how to use the framework:"),
            rich: true,
            wrap: true,
            font: "text-14"
          });
          this.add(control);
          break;
        case "guided-tours-list": {
          control = new osparc.tours.List();
          control.addListener("tourSelected", e => this.__selectTour(e.getData()));
          this.bind("tours", control, "tours");
          this.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("intro-text");
      this.getChildControl("guided-tours-list");
    },

    start: function() {
      this.center();
      this.open();
    },

    stop: function() {
      this.__removeCurrentBuble();
    },

    __removeCurrentBuble: function() {
      if (this.__currentBuble) {
        qx.core.Init.getApplication().getRoot().remove(this.__currentBuble);
        this.__currentBuble.exclude();
        this.__currentBuble = null;
      }
    },

    __selectTour: function(tour) {
      this.close();
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
      if (step.beforeClick && step.beforeClick.selector) {
        const element = document.querySelector(`[${step.beforeClick.selector}]`);
        const widget = qx.ui.core.Widget.getWidgetByElement(element);
        if (step.beforeClick.action) {
          widget[step.beforeClick.action]();
        } else {
          widget.execute();
        }
        setTimeout(() => this.__toStep(steps, idx), 100);
      } else {
        this.__toStep(steps, idx);
      }
    },

    __createStep: function(element, text) {
      const stepWidget = new osparc.tours.Step(element, text).set({
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
      if (step.anchorEl) {
        const el = document.querySelector(`[${step.anchorEl}]`);
        const targetWidget = qx.ui.core.Widget.getWidgetByElement(el);
        if (targetWidget) {
          stepWidget.setElement(targetWidget);
          if (step.placement) {
            stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.textToOrientation(step.placement));
          }
        } else {
          // target not found, move to the next step
          this.__toStepCheck(this.__currentIdx+1);
        }
      } else {
        stepWidget.getChildControl("caret").exclude();
        stepWidget.moveToTheCenter();
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

      stepWidget.show();
      // eslint-disable-next-line no-underscore-dangle
      setTimeout(() => stepWidget.__updatePosition(), 10); // Hacky: Execute async and give some time for the relevant properties to be set
    }
  }
});

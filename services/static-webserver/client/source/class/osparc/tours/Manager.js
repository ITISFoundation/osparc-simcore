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
      width: 400,
      height: 300,
      showMaximize: false,
      showMinimize: false
    });

    this.__blankets = [];
    this.__buildLayout();
  },

  properties: {
    tours: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeTours"
    },

    tour: {
      check: "Object",
      init: null,
      nullable: true
    },

    steps: {
      check: "Array",
      init: [],
      nullable: true
    }
  },

  members: {
    __currentBubble: null,
    __currentIdx: null,
    __blankets: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("This collection of Guided Tours will show you how to use the platform:"),
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
      this.setTour(null);
      this.__removeCurrentBubble();
      this.__removeBlankets();
    },

    __removeCurrentBubble: function() {
      if (this.__currentBubble) {
        qx.core.Init.getApplication().getRoot().remove(this.__currentBubble);
        this.__currentBubble.exclude();
        this.__currentBubble = null;
      }
    },

    __addBlankets: function(targetWidget) {
      // the plan is to surround the targetWidget with dark blankets so it gets highlighted
      const element = targetWidget.getContentElement().getDomElement();
      const {
        top,
        left
      } = qx.bom.element.Location.get(element);
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(element);
      const windowW = window.innerWidth;
      const windowH = window.innerHeight;

      const addBlanket = (w, h, l, t) => {
        const blanket = new qx.ui.core.Widget().set({
          width: w,
          height: h,
          backgroundColor: "black",
          opacity: 0.4,
          zIndex: osparc.utils.Utils.FLOATING_Z_INDEX-1
        });
        qx.core.Init.getApplication().getRoot().add(blanket, {
          left: l,
          top: t
        });
        return blanket;
      };
      this.__blankets.push(addBlanket(left, windowH, 0, 0)); // left
      this.__blankets.push(addBlanket(width, top, left, 0)); // top
      this.__blankets.push(addBlanket(windowW-left-width, windowH, left+width, 0)); // right
      this.__blankets.push(addBlanket(width, windowH-top-height, left, top+height)); // bottom
    },

    __removeBlankets: function() {
      const nBlankets = this.__blankets.length;
      for (let i=nBlankets-1; i>=0; i--) {
        const blanket = this.__blankets[i];
        qx.core.Init.getApplication().getRoot().remove(blanket);
        this.__blankets.splice(i, 1);
      }
    },

    __selectTour: function(tour) {
      this.close();
      if ("steps" in tour) {
        this.setTour(tour);
        this.setSteps(tour.steps);
        this.__toStepCheck(0);
      }
    },

    __getVisibleElement: function(selector) {
      // get all elements...
      const elements = document.querySelectorAll(`[${selector}]`);
      // ...and use the first on screen match
      const element = [...elements].find(el => osparc.utils.Utils.isElementOnScreen(el));
      return element;
    },

    __toStepCheck: function(idx = 0) {
      const steps = this.getSteps();
      if (idx >= steps.length) {
        return;
      }

      this.__removeCurrentBubble();
      this.__removeBlankets();
      this.__currentIdx = idx;
      const step = steps[idx];
      if (step.beforeClick && step.beforeClick.selector) {
        let targetWidget = null;
        const element = this.__getVisibleElement(step.beforeClick.selector);
        if (element) {
          targetWidget = qx.ui.core.Widget.getWidgetByElement(element);
        }
        if (targetWidget) {
          if (step.beforeClick.action) {
            targetWidget[step.beforeClick.action]();
          } else if (step.beforeClick.event) {
            targetWidget.fireEvent(step.beforeClick.event);
          } else {
            targetWidget.execute();
          }
          setTimeout(() => this.__toStep(steps, idx), 150);
        } else {
          // target not found, move to the next step
          this.__toStepCheck(this.__currentIdx+1);
          return;
        }
      } else {
        this.__toStep(steps, idx);
      }
    },

    __createStep: function() {
      const tour = this.getTour();
      const stepWidget = new osparc.tours.Step(tour["name"]).set({
        maxWidth: 400
      });
      [
        "skipPressed",
        "endPressed"
      ].forEach(evName => stepWidget.addListener(evName, () => this.stop(), this));
      stepWidget.addListener("nextPressed", () => this.__toStepCheck(this.__currentIdx+1), this);
      stepWidget.addListener("toTours", () => {
        this.stop();
        this.start();
      }, this);
      return stepWidget;
    },

    __toStep: async function(steps, idx) {
      const step = steps[idx];
      const stepWidget = this.__currentBubble = this.__createStep();
      if (step.anchorEl) {
        let targetWidget = null;
        const element = this.__getVisibleElement(step.anchorEl);
        if (element) {
          targetWidget = qx.ui.core.Widget.getWidgetByElement(element);
        }
        if (targetWidget) {
          stepWidget.setElement(targetWidget);
          if (step.placement) {
            stepWidget.setOrientation(osparc.ui.basic.FloatingHelper.textToOrientation(step.placement));
          }
          this.__addBlankets(targetWidget);
        } else {
          // target not found, move to the next step
          this.__toStepCheck(this.__currentIdx+1);
          return;
        }
      } else {
        // intro text, it will be centered
        stepWidget.getChildControl("caret").exclude();
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
      setTimeout(() => {
        if (stepWidget.getElement()) {
          stepWidget.updatePosition();
        } else {
          stepWidget.moveToTheCenter();
        }
      }, 10);
    }
  }
});

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

qx.Class.define("osparc.product.landingPage.Chat", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      zIndex: 100000
    });

    this.getChildControl("chat-button");
  },

  members: {
    __chatBuble: null,

    _createChildControlImpl: function(id) {
      const iconSize = 72;
      let control;
      switch (id) {
        case "chat-button": {
          const imgSize = 30;
          const imgClosed = "@FontAwesome5Solid/envelope/"+imgSize;
          const imgOpened = "@FontAwesome5Solid/chevron-down/"+imgSize;
          control = new qx.ui.basic.Image(imgClosed).set({
            backgroundColor: "strong-main",
            textColor: "text",
            width: iconSize,
            height: iconSize,
            scale: true,
            paddingTop: parseInt(iconSize/2 - imgSize/2),
            cursor: "pointer"
          });
          control.addListener("tap", () => {
            if (control.getSource().includes("message")) {
              control.setSource(imgOpened);
              this.__openChat();
            } else {
              control.setSource(imgClosed);
              this.__closeChat();
            }
          }, this);
          control.getContentElement().setStyles({
            "border-radius": "48px"
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

    stop: function() {
      this.__closeChat();
    },

    __closeChat: function() {
      this.__removeChat();
    },

    __removeChat: function() {
      if (this.__chatBuble) {
        qx.core.Init.getApplication().getRoot().remove(this.__chatBuble);
        this.__chatBuble.exclude();
      }
    },

    __createChat: function() {
      const chatLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        maxWidth: 400
      });
      chatLayout.getContentElement().setStyles({
        "border-radius": "8px"
      });

      const introLabel = new qx.ui.basic.Label().set({
        value: this.tr("Hi there, this is the App Team. How can we help you?"),
        font: "text-24",
        rich: true,
        wrap: true
      });
      chatLayout.add(introLabel);

      const appTeamLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignX: "center",
        alignY: "middle"
      }));

      const size = 48;
      [{
        user: "https://github.com/drniiken",
        avatar: "https://avatars.githubusercontent.com/u/32800795"
      }, {
        user: "https://github.com/eofli",
        avatar: "https://avatars.githubusercontent.com/u/40888440"
      }].forEach(user => {
        const link = user.avatar + "?s=" + size;
        const image = new qx.ui.basic.Image().set({
          source: link,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(user.user, "_blank"));
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        appTeamLayout.add(image);
      });
      chatLayout.add(appTeamLayout);

      const root = qx.core.Init.getApplication().getRoot();
      root.add(chatLayout, {
        bottom: 20,
        right: 72
      });
    },

    __openChat: function() {
      this.getChildControl("chat-layout").show();
    },

    __toSequences: function() {
      const sequences = this.getSequences();
      const dontShow = osparc.utils.Utils.localCache.getLocalStorageItem("panddyDontShow");
      if (sequences.length === 0 || (sequences === this.self().INTRO_SEQUENCE && dontShow === "true")) {
        this.stop();
        return;
      }

      if (sequences.length === 1) {
        this.__selectSequence(sequences[0]);
      } else {
        this.__showSequences();
      }
    },

    __showSequences: function() {
      const panddy = this.getChildControl("chat-button");
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

      this.__removeChat();
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
        const panddy = this.getChildControl("chat-button");
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

      if (this.getSequences() === this.self().INTRO_SEQUENCE) {
        const dontShowCB = osparc.product.tutorial.Utils.createDontShowAgain("panddyDontShow");
        stepWidget.add(dontShowCB);
      }

      stepWidget.show();
      // eslint-disable-next-line no-underscore-dangle
      setTimeout(() => stepWidget.__updatePosition(), 10); // Hacky: Execute async and give some time for the relevant properties to be set
    }
  }
});

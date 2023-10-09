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

qx.Class.define("osparc.tours.Step", {
  extend: osparc.ui.basic.FloatingHelper,

  construct: function(tourTitle) {
    this.base(arguments, null, "large");

    this.setLayout(new qx.ui.layout.VBox(10));

    const hintContainer = this.getChildControl("hint-container");
    hintContainer.setPadding(15);
    hintContainer.getContentElement().setStyles({
      "border-radius": "8px"
    });

    this.getChildControl("title");
    this.getChildControl("message");
    this.getChildControl("skip-button");
    const titleLabel = this.getChildControl("tour-title");
    if (tourTitle) {
      titleLabel.setValue(tourTitle);
    }
    this.getChildControl("step-label");
  },

  events: {
    "skipPressed": "qx.event.type.Event",
    "nextPressed": "qx.event.type.Event",
    "endPressed": "qx.event.type.Event"
  },

  properties: {
    title: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeTitle"
    },

    text: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeText"
    },

    stepIndex: {
      check: "Integer",
      nullable: true,
      init: 0,
      apply: "__updateNextButton"
    },

    nSteps: {
      check: "Integer",
      nullable: true,
      init: 0,
      apply: "__updateNextButton"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-16"
          });
          this.bind("title", control, "value");
          this.bind("title", control, "visibility", {
            converter: title => title ? "visible" : "excluded"
          });
          this.add(control);
          break;
        case "message":
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-14"
          });
          this.bind("text", control, "value");
          this.bind("text", control, "visibility", {
            converter: text => text ? "visible" : "excluded"
          });
          this.add(control);
          break;
        case "bottom-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "center"
          }));
          this.add(control);
          break;
        case "skip-button": {
          control = new qx.ui.form.Button().set({
            label: this.tr("Skip"),
            allowGrowX: false,
            alignX: "left"
          });
          control.addListener("execute", () => this.fireEvent("skipPressed"), this);
          const bottomLayout = this.getChildControl("bottom-layout");
          bottomLayout.add(control);
          break;
        }
        case "bottom-center-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(3).set({
            alignX: "center"
          }));
          const bottomLayout = this.getChildControl("bottom-layout");
          bottomLayout.add(control, {
            flex: 1
          });
          break;
        }
        case "tour-title": {
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            alignY: "middle",
            textAlign: "center",
            allowGrowX: true
          });
          const bottomLayout = this.getChildControl("bottom-center-layout");
          bottomLayout.add(control);
          break;
        }
        case "step-label": {
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            alignY: "middle",
            textAlign: "center",
            allowGrowX: true
          });
          const bottomLayout = this.getChildControl("bottom-center-layout");
          bottomLayout.add(control);
          break;
        }
        case "next-button": {
          control = new qx.ui.form.Button().set({
            label: this.tr("Next"),
            icon: "@FontAwesome5Solid/arrow-right/16",
            iconPosition: "right",
            appearance: "strong-button",
            allowGrowX: false,
            alignX: "right"
          });
          control.addListener("execute", () => this.__nextRequested(), this);
          const bottomLayout = this.getChildControl("bottom-layout");
          bottomLayout.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    // override
    _elementAppearDisappearHandler: function(e) {
      // If the element is a floating view, when clicking away it will disappear
      // Treat that event as a "nextPressed"
      switch (e.getType()) {
        case "disappear":
          if (this.isVisible()) {
            this.__nextRequested();
          }
          break;
      }

      this.base(arguments, e);
    },

    __nextRequested: function() {
      if (this.getStepIndex() === this.getNSteps()) {
        this.fireEvent("endPressed");
      } else {
        this.fireEvent("nextPressed");
      }
    },

    __updateNextButton: function() {
      const stepLabel = this.getChildControl("step-label");
      stepLabel.setValue(this.tr("Step: ") + this.getStepIndex() + "/" + this.getNSteps());

      const nextButton = this.getChildControl("next-button");
      if (this.getStepIndex() === this.getNSteps()) {
        nextButton.set({
          label: this.tr("End"),
          icon: null
        });
      }
    }
  }
});

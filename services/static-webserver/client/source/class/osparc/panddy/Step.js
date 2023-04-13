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

qx.Class.define("osparc.panddy.Step", {
  extend: osparc.ui.basic.FloatingHelper,

  construct: function(element, title, message) {
    this.base(arguments, element);

    this.setLayout(new qx.ui.layout.VBox(8));

    const hintContainer = this.getChildControl("hint-container");
    hintContainer.setPadding(15);
    hintContainer.getContentElement().setStyles({
      "border-radius": "8px"
    });

    this.getChildControl("title");
    this.getChildControl("message");
    this.getChildControl("skip-button");
    this.getChildControl("step-label");

    if (title) {
      this.setTitle(title);
    }

    if (message) {
      this.setMessage(message);
    }
  },

  events: {
    "closePressed": "qx.event.type.Event",
    "nextPressed": "qx.event.type.Event"
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
          this.add(control);
          break;
        case "message":
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-14"
          });
          this.bind("text", control, "value");
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
          control.addListener("execute", () => this.fireEvent("closePressed"), this);
          const bottomLayout = this.getChildControl("bottom-layout");
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
          const bottomLayout = this.getChildControl("bottom-layout");
          bottomLayout.add(control, {
            flex: 1
          });
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
          control.addListener("tap", () => this.fireEvent("nextPressed"), this);
          const bottomLayout = this.getChildControl("bottom-layout");
          bottomLayout.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __updateNextButton: function() {
      const stepLabel = this.getChildControl("step-label");
      stepLabel.setValue(this.tr("Step: ") + this.getStepIndex() + "/" + this.getNSteps());

      const nextButton = this.getChildControl("next-button");
      if (this.getStepIndex() === this.getNSteps()) {
        nextButton.setLabel(this.tr("End"));
        nextButton.addListener("execute", () => this.fireEvent("closePressed"), this);
      }
    }
  }
});

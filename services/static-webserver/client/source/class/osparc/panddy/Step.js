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

  construct: function(element, text) {
    this.base(arguments, element);

    this.setLayout(new qx.ui.layout.VBox(10));

    const hintContainer = this.getChildControl("hint-container");
    hintContainer.setPadding(10);
    hintContainer.getContentElement().setStyles({
      "border-radius": "8px"
    });

    const closeButton = this.getChildControl("close-button");
    this.add(closeButton);

    const message = this.getChildControl("message");
    this.add(message);
    if (text === undefined) {
      text = "";
    }
    message.setValue(text);

    const nextButton = this.getChildControl("next-button");
    this.add(nextButton);
  },

  events: {
    "closePressed": "qx.event.type.Event",
    "nextPressed": "qx.event.type.Event"
  },

  properties: {
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
        case "close-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/times/16",
            allowGrowX: false,
            alignX: "right"
          });
          control.addListener("execute", () => this.fireEvent("closePressed"), this);
          break;
        case "message":
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-16"
          });
          this.bind("text", control, "value");
          break;
        case "next-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/arrow-right/16",
            iconPosition: "right",
            appearance: "strong-button",
            font: "text-16",
            allowGrowX: false,
            alignX: "right"
          });
          control.exclude();
          control.addListener("tap", () => this.fireEvent("nextPressed"), this);
          break;
      }
      return control || this.base(arguments, id);
    },

    __updateNextButton: function() {
      this.getChildControl("next-button").set({
        label: this.getStepIndex() + "/" + this.getNSteps(),
        visibility: "visible"
      });
    }
  }
});

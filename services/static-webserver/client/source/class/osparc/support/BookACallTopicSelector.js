/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.support.BookACallTopicSelector", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.set({
      padding: 10,
      font: "text-14",
    });

    this.__buildLayout();
  },

  events: {
    "callTopicSelected": "qx.event.type.Data",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "content-box":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            decorator: "rounded",
            backgroundColor: "background-main-2",
            padding: 10,
          });
          this._add(control);
          break;
        case "intro-label":
          control = new qx.ui.basic.Label().set({
            value: this.tr("I would like..."),
            font: "text-14",
          });
          this.getChildControl("content-box").add(control);
          break;
        case "generic-intro-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("a generic introduction"),
            value: false,
            paddingTop: 10,
          });
          this.getChildControl("content-box").add(control);
          break;
        case "specific-intro-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("a specific introduction for"),
            value: false,
            paddingTop: 10,
          });
          this.getChildControl("content-box").add(control);
          break;
        case "specific-intro-select-box":
          control = new qx.ui.form.SelectBox().set({
            marginLeft: 20,
          });
          control.getChildControl("arrow").syncAppearance(); // force sync to show the arrow
          this.getChildControl("content-box").add(control);
          this.getChildControl("specific-intro-button").bind("value", control, "visibility", {
            converter: val => val ? "visible" : "excluded"
          });
          break;
        case "help-with-project-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("some help with my project"),
            value: false,
            paddingTop: 10,
          });
          this.getChildControl("content-box").add(control);
          break;
        case "share-project-checkbox": {
          control = new qx.ui.form.CheckBox().set({
            value: true,
            label: this.tr("share current project with support team (optional)"),
            marginLeft: 20,
          });
          this.getChildControl("content-box").add(control);
          this.getChildControl("help-with-project-button").bind("value", control, "visibility", {
            converter: val => val ? "visible" : "excluded"
          });
          const store = osparc.store.Store.getInstance();
          store.bind("currentStudy", control, "enabled", {
            converter: study => {
              if (!study) {
                control.setValue(false);
              }
              return Boolean(study);
            }
          });
          break;
        }
        case "specific-topic-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("to discuss a specific topic"),
            value: false,
            paddingTop: 10,
          });
          this.getChildControl("content-box").add(control);
          break;
        case "specific-topic-textfield":
          control = new qx.ui.form.TextArea().set({
            placeholder: this.tr("please provide any background information that could help us make this meeting more productive"),
            marginLeft: 20,
          });
          this.getChildControl("content-box").add(control);
          this.getChildControl("specific-topic-button").bind("value", control, "visibility", {
            converter: val => val ? "visible" : "excluded"
          });
          break;
        case "next-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Next"),
            appearance: "strong-button",
            center: true,
            allowGrowX: false,
            alignX: "right",
            marginTop: 20,
          });
          control.addListener("execute", () => this.__nextPressed());
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("intro-label");
      const genericIntroButton = this.getChildControl("generic-intro-button");
      const specificIntroButton = this.getChildControl("specific-intro-button");
      const selectBox = this.getChildControl("specific-intro-select-box");
      osparc.product.Utils.S4L_TOPICS.forEach(topic => {
        const lItem = new qx.ui.form.ListItem(topic.label, null, topic.id).set({
          rich: true
        });
        selectBox.add(lItem);
      });
      const helpWithProjectButton = this.getChildControl("help-with-project-button");
      this.getChildControl("share-project-checkbox");
      const specificTopicButton = this.getChildControl("specific-topic-button");
      this.getChildControl("specific-topic-textfield");
      this.getChildControl("next-button");

      // make them act as radio buttons
      [
        genericIntroButton,
        specificIntroButton,
        helpWithProjectButton,
        specificTopicButton,
      ].forEach(rb => {
        rb.addListener("changeValue", () => {
          if (rb.getValue()) {
            [genericIntroButton, specificIntroButton, helpWithProjectButton, specificTopicButton].forEach(otherRb => {
              if (otherRb !== rb) {
                otherRb.setValue(false);
              }
            });
          }
        });
      });
    },

    __nextPressed: function() {
      const topicData = {};
      if (this.getChildControl("generic-intro-button").getValue()) {
        topicData["topic"] = "Generic Introduction";
      } else if (this.getChildControl("specific-intro-button").getValue()) {
        topicData["topic"] = "Specific Introduction";
        const selectBox = this.getChildControl("specific-intro-select-box");
        const selectedItem = selectBox.getSelection()[0];
        topicData["extraInfo"] = selectedItem ? selectedItem.getModel() : "";
      } else if (this.getChildControl("help-with-project-button").getValue()) {
        topicData["topic"] = "Help with Project";
        if (this.getChildControl("share-project-checkbox").getValue()) {
          topicData["share-project"] = true;
        }
      } else if (this.getChildControl("specific-topic-button").getValue()) {
        topicData["topic"] = "Specific Topic";
        topicData["extraInfo"] = this.getChildControl("specific-topic-textfield").getValue();
      }

      this.fireDataEvent("callTopicSelected", topicData);
    },
  }
});

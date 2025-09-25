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


qx.Class.define("osparc.support.CallTopicSelector", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.setPadding(10);

    this.__buildLayout();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-label":
          control = new qx.ui.basic.Label().set({
            value: this.tr("I would like..."),
            font: "text-14",
          });
          this._add(control);
          break;
        case "generic-intro-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("a generic introduction"),
            value: false,
            paddingTop: 10,
          });
          this._add(control);
          break;
        case "specific-intro-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("a specific introduction for"),
            value: false,
            paddingTop: 10,
          });
          this._add(control);
          break;
        case "specific-intro-select-box":
          control = new qx.ui.form.SelectBox().set({
            paddingLeft: 20,
          });
          this._add(control);
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
          this._add(control);
          break;
        case "share-project-checkbox":
          control = new qx.ui.form.CheckBox().set({
            value: true,
            label: this.tr("share current project with support team (optional)"),
            paddingLeft: 20,
          });
          this._add(control);
          this.getChildControl("help-with-project-button").bind("value", control, "visibility", {
            converter: val => val ? "visible" : "excluded"
          });
          break;
        case "specific-topic-button":
          control = new qx.ui.form.RadioButton().set({
            label: this.tr("to discuss a specific topic"),
            value: false,
            paddingTop: 10,
          });
          this._add(control);
          break;
        case "specific-topic-textfield":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("please provide any background information that could help us make this meeting more productive"),
            paddingLeft: 20,
          });
          this._add(control);
          this.getChildControl("specific-topic-button").bind("value", control, "visibility", {
            converter: val => val ? "visible" : "excluded"
          });
          break;
        case "next-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Next"),
            alignX: "right",
            marginTop: 10,
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.__nextPressed());
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("intro-label");
      this.getChildControl("generic-intro-button");
      this.getChildControl("specific-intro-button");
      const selectBox = this.getChildControl("specific-intro-select-box");
      const topics = [
        this.tr("How to use osparc"),
        this.tr("How to create and manage projects"),
        this.tr("How to use the Workbench"),
        this.tr("How to use the Data Manager"),
        this.tr("How to use the App Store"),
        this.tr("How to use the Dashboard"),
        this.tr("How to use Teams"),
        this.tr("Billing and Subscription"),
        this.tr("Other"),
      ];
      topics.forEach(topic => {
        const item = new qx.ui.form.ListItem(topic);
        selectBox.add(item);
      });
      this.getChildControl("help-with-project-button");
      this.getChildControl("share-project-checkbox");
      this.getChildControl("specific-topic-button");
      this.getChildControl("specific-topic-textfield");
      this.getChildControl("next-button");
    },

    __nextPressed: function() {
      const topicData = {};
      if (this.getChildControl("generic-intro-button").getValue()) {
        topicData["topic"] = "specific-topic";
      } else if (this.getChildControl("specific-topic-button").getValue()) {
        topicData["topic"] = "specific-topic";
        const selectBox = this.getChildControl("specific-topic-select-box");
        const selectedItem = selectBox.getSelection()[0];
        topicData["extraInfo"] = selectedItem ? selectedItem.getLabel() : "";
      } else if (this.getChildControl("help-with-project-button").getValue()) {
        topicData["topic"] = "help-with-project";
        if (this.getChildControl("share-project-checkbox").getValue()) {
          topicData["extraInfo"] = "share-project";
        }
      } else if (this.getChildControl("specific-topic-button").getValue()) {
        topicData["topic"] = "specific-topic";
        topicData["extraInfo"] = this.getChildControl("specific-topic-textfield").getValue();
      }

      this.fireDataEvent("callTopicSelected", topicData);
    },
  }
});

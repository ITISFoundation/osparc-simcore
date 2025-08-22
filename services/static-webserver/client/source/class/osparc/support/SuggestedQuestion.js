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


qx.Class.define("osparc.support.SuggestedQuestion", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(12, 4);
    layout.setColumnFlex(1, 1); // content
    this._setLayout(layout);
    this.setPadding(5);
  },

  events: {
    "questionAnswered": "qx.event.type.Data",
  },

  members: {
    __addProductThumbnail: function() {
      const thumbnail = osparc.utils.Utils.createThumbnail(32).set({
        source: osparc.product.Utils.getIconUrl(),
      });
      this._add(thumbnail, {
        row: 0,
        column: 0,
      });
    },

    __addQuestionLabel: function(text) {
      const question = new qx.ui.basic.Label(text);
      this._add(question, {
        row: 0,
        column: 1,
      });
    },

    __addAnswers: function(answers) {
      const answersContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      answers.forEach(answer => {
        const button = new qx.ui.form.Button(answer.label).set({
          appearance: "strong-button",
          allowGrowX: false,
        });
        button.addListener("execute", () => this.fireDataEvent("questionAnswered", answer.key));
        answersContainer.add(button);
      });
      this._add(answersContainer, {
        row: 1,
        column: 1,
      });
    },

    isProjectRelated: function(answers) {
      this._removeAll();
      this.__addProductThumbnail();
      this.__addQuestionLabel(this.tr("Is your question related to the current project?"));
      this.__addAnswers(answers);
    },

    shareProject: function() {
      this._removeAll();
      this.__addProductThumbnail();
      this.__addQuestionLabel(this.tr("Do you want to share this project with Support?"));
      this.__addAnswers(answers);
    },
  }
});

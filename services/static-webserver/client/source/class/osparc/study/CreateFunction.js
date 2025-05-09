/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.study.CreateFunction", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__studyDataClone = osparc.data.model.Study.deepCloneStudyObject(studyData);

    this.__buildLayout();
  },

  members: {
    __studyDataClone: null,
    __form: null,
    __createFunctionBtn: null,

    __buildLayout: function() {
      const form = this.__form = new qx.ui.form.Form();
      this._add(new qx.ui.form.renderer.Single(form));

      const title = new qx.ui.form.TextField().set({
        required: true,
        value: this.__studyDataClone.name,
      });
      this.addListener("appear", () => {
        title.focus();
        title.activate();
      });
      form.add(title, this.tr("Name"), null, "name");

      const description = new qx.ui.form.TextField().set({
        required: false,
      });
      form.add(description, this.tr("Description"), null, "description");

      const createFunctionBtn = this.__createFunctionBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("Create"),
        allowGrowX: false,
        alignX: "right"
      });
      createFunctionBtn.addListener("execute", () => this.__createFunction(), this);
      this._add(createFunctionBtn);
    },

    __createFunction: function() {
      const name = this.__form.getItem("name");
      const description = this.__form.getItem("description");

      console.log("Creating function with name: ", name.getValue());
      console.log("Creating function with description: ", description.getValue());
    },

    getCreateFunctionButton: function() {
      return this.__createFunctionBtn;
    }
  }
});

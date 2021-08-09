/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.sweeper.Sweeper", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    if (study.isSnapshot()) {
      const primaryStudyId = study.getSweeper().getPrimaryStudyId();
      const openPrimaryStudyParamBtn = new qx.ui.form.Button(this.tr("Open Main Study")).set({
        allowGrowX: false
      });
      openPrimaryStudyParamBtn.addListener("execute", () => {
        this.fireDataEvent("openPrimaryStudy", primaryStudyId);
      });
      this._add(openPrimaryStudyParamBtn);
    } else {
      this.__primaryStudy = study;
      const parametersSection = this.__buildParametersSection();
      this._add(parametersSection, {
        flex: 1
      });
    }
  },

  events: {
    "openPrimaryStudy": "qx.event.type.Data"
  },

  members: {
    __primaryStudy: null,
    __parametersTable: null,

    __buildParametersSection: function() {
      const parametersSection = new qx.ui.groupbox.GroupBox(this.tr("Parameters")).set({
        layout: new qx.ui.layout.VBox(5)
      });
      const newParamBtn = this.__createNewParamBtn();
      parametersSection.add(newParamBtn);

      const parametersTable = this.__parametersTable = new osparc.component.sweeper.Parameters(this.__primaryStudy);
      parametersSection.add(parametersTable, {
        flex: 1
      });
      return parametersSection;
    },

    __createNewParamBtn: function() {
      const label = this.tr("Create new Parameter");
      const newParamBtn = new qx.ui.form.Button(label).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const newParamName = new osparc.component.widget.Renamer(null, null, label);
        newParamName.addListener("labelChanged", e => {
          const primaryStudy = this.__primaryStudy;
          let newParameterLabel = e.getData()["newLabel"];
          newParameterLabel = newParameterLabel.replace(" ", "_");
          if (primaryStudy.getSweeper().parameterLabelExists(newParameterLabel)) {
            const msg = this.tr("Parameter name already exists");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
          } else {
            primaryStudy.getSweeper().addNewParameter(newParameterLabel);
            this.__parametersTable.updateTable();
            newParamName.close();
          }
        }, this);
        newParamName.center();
        newParamName.open();
      }, this);
      return newParamBtn;
    }
  }
});

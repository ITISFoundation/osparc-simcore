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

qx.Class.define("osparc.component.iteration.Parameters", {
  extend: qx.ui.core.Widget,

  construct: function(primaryStudy) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout(primaryStudy);
  },

  statics: {
    popUpInWindow: function(parametersWidget) {
      const window = new osparc.ui.window.Window(qx.locale.Manager.tr("Parameters")).set({
        autoDestroy: true,
        layout: new qx.ui.layout.VBox(),
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        width: 500,
        height: 600,
        modal: true,
        clickAwayClose: true
      });
      window.add(parametersWidget);
      window.center();
      window.open();
      return window;
    }
  },

  members: {
    __paramSpecs: null,
    __paramCombinations: null,

    __buildLayout: function(primaryStudy) {
      const newParamBtn = this.__createNewParamBtn(primaryStudy);
      this._add(newParamBtn);
      const paramSpecs = this.__paramSpecs = this.__createParamSpecs(primaryStudy).set({
        maxHeight: 200
      });
      this._add(paramSpecs);

      this._add(new qx.ui.core.Spacer(null, 10));

      const updateParamParamBtn = this.__updateParamParamBtn();
      this._add(updateParamParamBtn);
      const paramCombinations = this.__paramCombinations = this.__createParamCombinations(primaryStudy).set({
        maxHeight: 400
      });
      this._add(paramCombinations);
    },

    __createNewParamBtn: function(primaryStudy) {
      const newParamBtn = new qx.ui.form.Button(this.tr("Create new parameter")).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const newParamName = new osparc.component.widget.Renamer();
        newParamName.addListener("labelChanged", e => {
          const newLabel = e.getData()["newLabel"];
          if (primaryStudy.parameterExists(newLabel)) {
            const msg = this.tr("Parameter name already exists");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
          } else {
            primaryStudy.addParameter(newLabel);
            this.__paramSpecs.updateTable();
            newParamName.close();
          }
        }, this);
        newParamName.center();
        newParamName.open();
      }, this);
      return newParamBtn;
    },

    __createParamSpecs: function(primaryStudy) {
      const paramSpecs = new osparc.component.iteration.ParametersSpecs(primaryStudy);
      return paramSpecs;
    },

    __updateParamParamBtn: function() {
      const updateParamParamBtn = new qx.ui.form.Button(this.tr("Recalculate Combinations")).set({
        allowGrowX: false
      });
      updateParamParamBtn.addListener("execute", () => {
      }, this);
      return updateParamParamBtn;
    },

    __createParamCombinations: function(primaryStudy) {
      const paramCombinations = new osparc.component.iteration.ParametersCombination(primaryStudy);
      return paramCombinations;
    }
  }
});

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
        clickAwayClose: true
      });
      window.add(parametersWidget);
      window.center();
      window.open();
      return window;
    }
  },

  members: {
    __buildLayout: function(primaryStudy) {
      const newParamBtn = this.__createNewParamBtn();
      this._add(newParamBtn);
      const paramSpecs = this.__createParamSpecs(primaryStudy);
      this._add(paramSpecs);

      this._add(new qx.ui.core.Spacer(null, 10));

      const updateParamParamBtn = this.__updateParamParamBtn();
      this._add(updateParamParamBtn);
      const paramCombinations = this.__createParamCombinations(primaryStudy);
      this._add(paramCombinations);
    },

    __createNewParamBtn: function() {
      const newParamBtn = new qx.ui.form.Button(this.tr("Create new parameter")).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
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

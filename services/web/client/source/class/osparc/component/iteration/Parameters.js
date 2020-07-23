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

    this.__primaryStudy = primaryStudy;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
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
        modal: true
      });
      window.add(parametersWidget);
      window.center();
      window.open();
      return window;
    }
  },

  members: {
    __primaryStudy: null,
    __paramSpecs: null,
    __paramCombinations: null,

    __buildLayout: function() {
      const newParamBtn = this.__createNewParamBtn();
      this._add(newParamBtn);
      const paramSpecs = this.__paramSpecs = this.__createParamSpecs().set({
        maxHeight: 200
      });
      this._add(paramSpecs);

      this._add(new qx.ui.core.Spacer(null, 10));

      const updateParamParamBtn = this.__updateParamParamBtn();
      this._add(updateParamParamBtn);
      const paramCombinations = this.__paramCombinations = this.__createParamCombinations().set({
        maxHeight: 400
      });
      this._add(paramCombinations);
    },

    __createNewParamBtn: function() {
      const label = this.tr("Create new parameter");
      const newParamBtn = new qx.ui.form.Button(label).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const subtitle = this.tr("Do not use whitespaces");
        const newParamName = new osparc.component.widget.Renamer(null, subtitle, label);
        newParamName.addListener("labelChanged", e => {
          const primaryStudy = this.__primaryStudy;
          let newParameterLabel = e.getData()["newLabel"];
          newParameterLabel = newParameterLabel.replace(" ", "_");
          if (primaryStudy.getSweeper().parameterLabelExists(newParameterLabel)) {
            const msg = this.tr("Parameter name already exists");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
          } else {
            primaryStudy.getSweeper().addParameter(newParameterLabel);
            this.__paramSpecs.updateTable();
            newParamName.close();
          }
        }, this);
        newParamName.center();
        newParamName.open();
      }, this);
      return newParamBtn;
    },

    __createParamSpecs: function() {
      const paramSpecs = new osparc.component.iteration.ParametersSpecs(this.__primaryStudy);
      return paramSpecs;
    },

    __updateParamParamBtn: function() {
      const updateParamParamBtn = new qx.ui.form.Button(this.tr("Recreate Iterations")).set({
        allowGrowX: false
      });
      updateParamParamBtn.addListener("execute", () => {
        // recreate table
        if (this.__paramCombinations) {
          this._remove(this.__paramCombinations);
        }

        this.__recreateIterations();

        const paramCombinations = this.__paramCombinations = this.__createParamCombinations().set({
          maxHeight: 400
        });
        this._add(paramCombinations);
      }, this);
      return updateParamParamBtn;
    },

    __recreateIterations: function() {
      const secondaryStudiesData = this.__primaryStudy.getSweeper().recreateIterations();

      const msg = secondaryStudiesData.length + this.tr(" iterations created");
      osparc.component.message.FlashMessenger.getInstance().logAs(msg);
    },

    __createParamCombinations: function() {
      const paramCombinations = new osparc.component.iteration.ParametersCombination(this.__primaryStudy);
      return paramCombinations;
    }
  }
});

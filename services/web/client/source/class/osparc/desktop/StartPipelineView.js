/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.desktop.StartPipelineView", {
  extend: qx.ui.core.Widget,

  construct: function(partialPipeline = [], forceRestart = false) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__buildOptions(partialPipeline, forceRestart);
  },

  members: {
    __buildOptions: function(partialPipeline, forceRestart) {
      const partialBox = new qx.ui.groupbox.GroupBox(this.tr("Partial running"));
      const runPipeline = new qx.ui.form.RadioButton(this.tr("Run entire pipeline"));
      const runPartialPipeline = new qx.ui.form.RadioButton(this.tr("Run partial pipeline"));
      const rbManager = new qx.ui.form.RadioGroup(runPipeline, runPartialPipeline).set({
        allowEmptySelection: false
      });
      partialBox.add(runPipeline);
      partialBox.add(runPartialPipeline);
      rbManager.add(runPipeline);
      rbManager.add(runPartialPipeline);
      rbManager.setSelection(partialPipeline.length ? [runPartialPipeline] : [runPipeline]);
      this._add(partialBox);

      const cacheBox = new qx.ui.groupbox.GroupBox(this.tr("Caching"));
      const useCacheCB = this.__useCacheCB = new qx.ui.form.CheckBox(this.tr("Use cache")).set({
        value: !forceRestart
      });
      cacheBox.add(useCacheCB);
      this._add(cacheBox);
    },

    getUseCache: function() {
      return this.__useCacheCB.getValue();
    }
  }
});

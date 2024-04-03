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

  events: {
    "startPipeline": "qx.event.type.Data",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __buildOptions: function(partialPipeline, forceRestart) {
      const partialBox = new qx.ui.groupbox.GroupBox(this.tr("Partial Running"));
      partialBox.set({
        layout: new qx.ui.layout.VBox(),
        enabled: false
      });
      const runPipeline = new qx.ui.form.RadioButton(this.tr("Run Entire pipeline"));
      const runPartialPipeline = new qx.ui.form.RadioButton(this.tr("Run Partial pipeline"));
      const rbManager = new qx.ui.form.RadioGroup(runPipeline, runPartialPipeline).set({
        allowEmptySelection: false
      });
      partialBox.add(runPipeline);
      partialBox.add(runPartialPipeline);
      rbManager.add(runPipeline);
      rbManager.add(runPartialPipeline);
      rbManager.setSelection(partialPipeline.length ? [runPartialPipeline] : [runPipeline]);
      this._add(partialBox);

      const reRunBox = new qx.ui.groupbox.GroupBox(this.tr("Re-Run"));
      reRunBox.set({
        layout: new qx.ui.layout.VBox(),
        enabled: false
      });
      const reRunCB = new qx.ui.form.CheckBox(this.tr("Re-run")).set({
        value: forceRestart
      });
      reRunBox.add(reRunCB);
      this._add(reRunBox);

      const cacheBox = new qx.ui.groupbox.GroupBox(this.tr("Caching"));
      cacheBox.setLayout(new qx.ui.layout.VBox());
      const useCacheCB = new qx.ui.form.CheckBox(this.tr("Use cache")).set({
        value: true
      });
      cacheBox.add(useCacheCB);
      this._add(cacheBox);

      const btnsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignX: "right"
      }));
      const cancelBtn = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "form-button-text",
        allowGrowX: false
      });
      cancelBtn.addListener("execute", () => this.fireEvent("cancel"));
      btnsLayout.add(cancelBtn);
      const startBtn = new qx.ui.form.Button(this.tr("Start")).set({
        appearance: "form-button",
        allowGrowX: false
      });
      btnsLayout.add(startBtn);
      startBtn.addListener("execute", () => {
        this.fireDataEvent("startPipeline", {
          "useCache": useCacheCB.getValue()
        });
      });
      this._add(btnsLayout);
    }
  }
});
